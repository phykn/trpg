import secrets
from collections.abc import AsyncIterator
from typing import Any, Literal

from src.db.repo import GraphRepo, ScenarioRepo
from src.game.domain.action import Action
from src.game.domain.content import node_label, node_text
from src.game.domain.graph import Graph, GraphNode
from src.game.domain.graph.character import can_character_fight
from src.game.domain.graph.query import location_of
from src.llm.client import LLMClient
from src.llm.diag import engine_diag, set_diag_context
from src.locale.render import render
from src.wire.graph.to_front import graph_to_front_state

from ..load import load_runtime_state
from ..request_result import (
    GraphActionRequestResult,
    cancelled_result,
    confirmation_required_result,
    executed_result,
)
from ..pending_action import build_pending_action_payload, load_pending_action
from ..state import GameRuntimeState
from .turn import (
    GraphActionTurnError,
    run_graph_action_turn,
    run_graph_action_turn_from_runtime,
    run_graph_action_turn_from_runtime_stream,
)


Decision = Literal["confirm", "cancel"]


class GraphConfirmationError(ValueError):
    pass


class GraphConfirmationActive(GraphConfirmationError):
    pass


class GraphConfirmationExpected(GraphConfirmationError):
    pass


# Public flow


async def run_graph_action_request(
    repo: GraphRepo,
    game_id: str,
    action: Action,
    *,
    llm: LLMClient | None = None,
    scenario_repo: ScenarioRepo | None = None,
) -> GraphActionRequestResult:
    runtime = await load_runtime_state(repo, game_id, scenario_repo)
    set_diag_context(game_id, runtime.progress.turn_count)
    engine_diag("action:start", action=action.verb)
    if runtime.progress.pending_confirmation is not None:
        raise GraphConfirmationActive(
            "a pending_confirmation is already active; call graph confirm instead"
        )
    if runtime.progress.pending_roll is not None:
        raise GraphConfirmationActive(
            "a pending_roll is already active; call graph roll instead"
        )

    if should_start_graph_roll(runtime, action):
        from .roll import start_graph_roll

        engine_diag("action:roll_required", action=action.verb)
        return await start_graph_roll(
            repo, game_id, action, scenario_repo=scenario_repo
        )

    pending = build_graph_action_confirmation(runtime, action)
    if pending is None:
        result = await run_graph_action_turn(
            repo,
            game_id,
            action,
            llm=llm,
            scenario_repo=scenario_repo,
        )
        engine_diag("action:done", status="executed", action=action.verb)
        return executed_result(
            result.runtime,
            result.front_state,
            dispatch=result.dispatch,
            suggestions=result.suggestions,
        )

    next_progress = runtime.progress.model_copy(
        update={"pending_confirmation": pending}
    )
    next_runtime = runtime.model_copy(update={"progress": next_progress})
    await repo.save_progress(next_progress)
    engine_diag(
        "action:done",
        status="confirmation_required",
        action=action.verb,
        confirmation=pending.get("kind"),
    )
    return confirmation_required_result(
        next_runtime,
        graph_to_front_state(next_runtime),
        pending,
    )


async def run_graph_action_request_stream(
    repo: GraphRepo,
    game_id: str,
    action: Action,
    *,
    llm: LLMClient | None = None,
    scenario_repo: ScenarioRepo | None = None,
) -> AsyncIterator[dict[str, object]]:
    runtime = await load_runtime_state(repo, game_id, scenario_repo)
    set_diag_context(game_id, runtime.progress.turn_count)
    engine_diag("action:start", action=action.verb)
    if runtime.progress.pending_confirmation is not None:
        raise GraphConfirmationActive(
            "a pending_confirmation is already active; call graph confirm instead"
        )
    if runtime.progress.pending_roll is not None:
        raise GraphConfirmationActive(
            "a pending_roll is already active; call graph roll instead"
        )

    if should_start_graph_roll(runtime, action):
        from .roll import run_graph_preroll_stream

        engine_diag("action:roll_required", action=action.verb)
        async for event in run_graph_preroll_stream(
            llm,
            repo,
            game_id,
            action,
            scenario_repo=scenario_repo,
        ):
            yield event
        return

    pending = build_graph_action_confirmation(runtime, action)
    if pending is None:
        async for event in run_graph_action_turn_from_runtime_stream(
            repo,
            game_id,
            runtime,
            action,
            llm=llm,
        ):
            if event["type"] == "final":
                engine_diag("action:done", status="executed", action=action.verb)
            yield event
        return

    next_progress = runtime.progress.model_copy(
        update={"pending_confirmation": pending}
    )
    next_runtime = runtime.model_copy(update={"progress": next_progress})
    await repo.save_progress(next_progress)
    engine_diag(
        "action:done",
        status="confirmation_required",
        action=action.verb,
        confirmation=pending.get("kind"),
    )
    result = confirmation_required_result(
        next_runtime,
        graph_to_front_state(next_runtime),
        pending,
    )
    yield {"type": "result", "result": result}
    yield {"type": "final", "result": result}


async def run_graph_confirm(
    repo: GraphRepo,
    game_id: str,
    confirmation_id: str,
    decision: Decision,
    *,
    llm: LLMClient | None = None,
    scenario_repo: ScenarioRepo | None = None,
) -> GraphActionRequestResult:
    runtime = await load_runtime_state(repo, game_id, scenario_repo)
    set_diag_context(game_id, runtime.progress.turn_count)
    pending = runtime.progress.pending_confirmation
    engine_diag(
        "confirm:start",
        decision=decision,
        pending=pending.get("kind") if isinstance(pending, dict) else None,
    )
    if pending is None:
        raise GraphConfirmationExpected("no pending_confirmation")
    if pending.get("id") != confirmation_id:
        raise GraphConfirmationExpected("confirmation id mismatch")

    cleared_progress = runtime.progress.model_copy(
        update={"pending_confirmation": None}
    )
    cleared_runtime = runtime.model_copy(update={"progress": cleared_progress})
    if decision == "cancel":
        await repo.save_progress(cleared_progress)
        engine_diag("confirm:done", status="cancelled")
        return cancelled_result(
            cleared_runtime,
            graph_to_front_state(cleared_runtime),
        )

    action = load_pending_action(pending, error_type=GraphConfirmationExpected)
    if _requires_roll_after_confirmation(action):
        await repo.save_progress(cleared_progress)
        from .roll import start_graph_roll

        result = await start_graph_roll(
            repo,
            game_id,
            action,
            scenario_repo=scenario_repo,
        )
        engine_diag("confirm:done", status="roll_required")
        return result

    try:
        result = await run_graph_action_turn_from_runtime(
            repo,
            game_id,
            cleared_runtime,
            action,
            llm=llm,
        )
    except GraphActionTurnError as exc:
        raise GraphConfirmationError(str(exc)) from exc

    engine_diag("confirm:done", status="executed")
    return executed_result(
        result.runtime,
        result.front_state,
        dispatch=result.dispatch,
        suggestions=result.suggestions,
    )


async def run_graph_confirm_stream(
    repo: GraphRepo,
    game_id: str,
    confirmation_id: str,
    decision: Decision,
    *,
    llm: LLMClient | None = None,
    scenario_repo: ScenarioRepo | None = None,
) -> AsyncIterator[dict[str, object]]:
    runtime = await load_runtime_state(repo, game_id, scenario_repo)
    set_diag_context(game_id, runtime.progress.turn_count)
    pending = runtime.progress.pending_confirmation
    engine_diag(
        "confirm:start",
        decision=decision,
        pending=pending.get("kind") if isinstance(pending, dict) else None,
    )
    if pending is None:
        raise GraphConfirmationExpected("no pending_confirmation")
    if pending.get("id") != confirmation_id:
        raise GraphConfirmationExpected("confirmation id mismatch")

    cleared_progress = runtime.progress.model_copy(
        update={"pending_confirmation": None}
    )
    cleared_runtime = runtime.model_copy(update={"progress": cleared_progress})
    if decision == "cancel":
        await repo.save_progress(cleared_progress)
        engine_diag("confirm:done", status="cancelled")
        result = cancelled_result(
            cleared_runtime,
            graph_to_front_state(cleared_runtime),
        )
        yield {"type": "result", "result": result}
        yield {"type": "final", "result": result}
        return

    action = load_pending_action(pending, error_type=GraphConfirmationExpected)
    if _requires_roll_after_confirmation(action):
        await repo.save_progress(cleared_progress)
        from .roll import run_graph_preroll_stream

        engine_diag("confirm:done", status="roll_required")
        async for event in run_graph_preroll_stream(
            llm,
            repo,
            game_id,
            action,
            scenario_repo=scenario_repo,
        ):
            yield event
        return

    try:
        async for event in run_graph_action_turn_from_runtime_stream(
            repo,
            game_id,
            cleared_runtime,
            action,
            llm=llm,
        ):
            if event["type"] == "final":
                engine_diag("confirm:done", status="executed")
            yield event
    except GraphActionTurnError as exc:
        raise GraphConfirmationError(str(exc)) from exc


# Confirmation builders


def build_graph_action_confirmation(
    runtime: GameRuntimeState,
    action: Action,
) -> dict[str, Any] | None:
    if runtime.progress.graph_combat_state is None and action.verb == "attack":
        return _build_attack_start_confirmation(runtime, action)

    if action.verb == "transfer" and action.how == "steal":
        return _build_steal_confirmation(runtime, action)

    if action.verb == "transfer" and action.how in ("accept", "abandon"):
        return _build_quest_confirmation(runtime, action)

    return None


def _build_attack_start_confirmation(
    runtime: GameRuntimeState,
    action: Action,
) -> dict[str, Any] | None:
    target_ref = _attack_target(runtime.graph, runtime.progress.player_id, action)
    if target_ref is None:
        return None

    target = runtime.graph.nodes[target_ref]
    target_label = node_label(runtime.content, target)
    locale = runtime.progress.locale
    return _pending(
        kind="attack_start",
        title=render("runtime.confirmation.attack.title", locale),
        body=render("runtime.confirmation.attack.body", locale, target=target_label),
        confirm_label=render("runtime.confirmation.attack.confirm", locale),
        target_label=target_label,
        action=_normalize_attack_action(action, target_ref),
        locale=locale,
    )


def _build_quest_confirmation(
    runtime: GameRuntimeState,
    action: Action,
) -> dict[str, Any] | None:
    quest_id = _single(action.what) or _single(action.to)
    if quest_id is None:
        return None
    quest = runtime.graph.nodes.get(quest_id)
    if quest is None or quest.type != "quest":
        return None

    locale = runtime.progress.locale
    quest_label = node_label(runtime.content, quest)
    if action.how == "accept":
        return _pending(
            kind="quest_accept",
            title=render("runtime.confirmation.quest_accept.title", locale),
            body=render(
                "runtime.confirmation.quest_accept.body", locale, quest=quest_label
            ),
            confirm_label=render("runtime.confirmation.quest_accept.confirm", locale),
            target_label=quest_label,
            action=action,
            locale=locale,
        )

    return _pending(
        kind="quest_abandon",
        title=render("runtime.confirmation.quest_abandon.title", locale),
        body=render(
            "runtime.confirmation.quest_abandon.body", locale, quest=quest_label
        ),
        confirm_label=render("runtime.confirmation.quest_abandon.confirm", locale),
        target_label=quest_label,
        action=action,
        locale=locale,
    )


def _build_steal_confirmation(
    runtime: GameRuntimeState,
    action: Action,
) -> dict[str, Any] | None:
    item_id = _single(action.what) or _single(action.with_)
    target = _single(action.from_) or _single(action.to)
    if item_id is None or target is None:
        return None
    item = runtime.graph.nodes.get(item_id)
    target = runtime.graph.nodes.get(target)
    if item is None or target is None:
        return None

    locale = runtime.progress.locale
    item_label = node_label(runtime.content, item)
    target_label = node_label(runtime.content, target)
    return _pending(
        kind="steal",
        title=render("runtime.confirmation.steal.title", locale),
        body=render(
            "runtime.confirmation.steal.body",
            locale,
            item=item_label,
            target=target_label,
        ),
        confirm_label=render("runtime.confirmation.steal.confirm", locale),
        target_label=target_label,
        action=action,
        locale=locale,
    )


def _pending(
    *,
    kind: str,
    title: str,
    body: str,
    confirm_label: str,
    target_label: str,
    action: Action,
    locale: str,
) -> dict[str, Any]:
    return {
        "id": f"confirm_{secrets.token_hex(4)}",
        "kind": kind,
        "title": title,
        "body": body,
        "confirm_label": confirm_label,
        "cancel_label": render("runtime.confirmation.cancel", locale),
        "target_label": target_label,
        "payload": build_pending_action_payload(action),
    }


def _requires_roll_after_confirmation(action: Action) -> bool:
    return action.verb == "transfer" and action.how == "steal"


def should_start_graph_roll(
    runtime: GameRuntimeState,
    action: Action,
    *,
    check_required: bool = False,
    player_input: str | None = None,
) -> bool:
    if _roll_forbidden(runtime, action):
        return False
    if runtime.progress.graph_combat_state is not None:
        return False
    if _roll_required_by_server(runtime, action, player_input=player_input):
        return True
    if not check_required:
        return False
    return _roll_allowed_from_check_hint(runtime, action)


def _roll_forbidden(runtime: GameRuntimeState, action: Action) -> bool:
    if action.verb in {"attack", "rest", "pass"}:
        return True
    if action.verb != "transfer":
        return False
    if action.how in {"accept", "abandon", "equip", "unequip", "steal", "trade"}:
        return True
    return _is_public_pickup(runtime, action)


def _roll_required_by_server(
    runtime: GameRuntimeState,
    action: Action,
    *,
    player_input: str | None = None,
) -> bool:
    if action.verb == "perceive":
        return True
    if action.verb == "move":
        return _is_risky_move(runtime, action)
    if action.verb == "speak":
        return action.how in {"hostile", "deceptive", "recruit"} or _matches_active_social_check(
            runtime,
            action,
            player_input=player_input,
        )
    return False


def _matches_active_social_check(
    runtime: GameRuntimeState,
    action: Action,
    *,
    player_input: str | None = None,
) -> bool:
    target = _single(action.what) or _single(action.to)
    if target is None:
        return False
    active_id = runtime.progress.active_quest_id
    if active_id is None:
        return False
    quest = runtime.graph.nodes.get(active_id)
    if quest is None or quest.type != "quest":
        return False
    triggers = quest.properties.get("triggers", [])
    if not isinstance(triggers, list):
        return False
    for trigger in triggers:
        if not isinstance(trigger, dict):
            continue
        if trigger.get("type") != "social_check" or trigger.get("target") != target:
            continue
        if not _social_check_input_matches(runtime, quest, trigger, player_input):
            continue
        return True
    return False


def _social_check_input_matches(
    runtime: GameRuntimeState,
    quest: GraphNode,
    trigger: dict,
    player_input: str | None,
) -> bool:
    if player_input is None:
        return True
    input_text = _normalize_match_text(player_input)
    if not input_text:
        return False
    target = trigger.get("target")
    target_refs = _target_match_refs(runtime, target if isinstance(target, str) else None)
    for text in _social_check_match_texts(runtime, quest, trigger):
        for token in _match_tokens(text):
            normalized = _normalize_match_text(token)
            if not normalized or normalized in target_refs:
                continue
            if normalized in input_text:
                return True
    return False


def _social_check_match_texts(
    runtime: GameRuntimeState,
    quest: GraphNode,
    trigger: dict,
) -> list[str]:
    out: list[str] = []
    for value in (
        trigger.get("name"),
        node_label(runtime.content, quest),
        node_text(runtime.content, quest, "description"),
        quest.properties.get("title"),
        quest.properties.get("name"),
        quest.properties.get("description"),
    ):
        if isinstance(value, str) and value.strip():
            out.append(value)
    return out


def _target_match_refs(runtime: GameRuntimeState, target: str | None) -> set[str]:
    if target is None:
        return set()
    refs = {_normalize_match_text(target)}
    node = runtime.graph.nodes.get(target)
    if node is not None:
        label = node_label(runtime.content, node)
        refs.add(_normalize_match_text(label))
        refs.update(_normalize_match_text(token) for token in _match_tokens(label))
    return {ref for ref in refs if ref}


def _match_tokens(text: str) -> list[str]:
    return [
        token
        for token in text.replace(",", " ").replace(".", " ").split()
        if len(token) >= 2 and not token.endswith((_ko_to_person(), _ko_honorific_to_person()))
    ]


def _normalize_match_text(text: str) -> str:
    return "".join(ch for ch in text.lower() if ch.isalnum())


def _ko_to_person() -> str:
    return chr(0xC5D0) + chr(0xAC8C)


def _ko_honorific_to_person() -> str:
    return chr(0xAED8)


def _roll_allowed_from_check_hint(runtime: GameRuntimeState, action: Action) -> bool:
    if action.verb in {"move", "use", "speak", "perceive"}:
        return True
    if action.verb != "transfer":
        return False
    if action.how != "free":
        return False
    return not _is_public_pickup(runtime, action)


def _is_risky_move(runtime: GameRuntimeState, action: Action) -> bool:
    if action.how == "hasty":
        return True
    source_id = location_of(runtime.graph, runtime.progress.player_id)
    destination_id = _single(action.to) or _single(action.what)
    if source_id is None or destination_id is None:
        return False
    for edge in runtime.graph.edges.values():
        if (
            edge.type == "connects_to"
            and edge.from_node_id == source_id
            and edge.to_node_id == destination_id
        ):
            return edge.properties.get("difficulty") is not None
    return False


def _is_public_pickup(runtime: GameRuntimeState, action: Action) -> bool:
    item_id = _single(action.what) or _single(action.with_)
    if item_id is None:
        return False
    to_id = _single(action.to) or runtime.progress.player_id
    if to_id != runtime.progress.player_id:
        return False
    source_id = _single(action.from_) or _item_owner(runtime.graph, item_id)
    if source_id is None:
        return False
    source = runtime.graph.nodes.get(source_id)
    return source is not None and source.type == "location"


def _item_owner(graph: Graph, item_id: str) -> str | None:
    for edge in graph.edges.values():
        if edge.type in {"located_at", "hidden_at", "reward_of"} and edge.from_node_id == item_id:
            return edge.to_node_id
        if edge.type in {"carries", "equips"} and edge.to_node_id == item_id:
            return edge.from_node_id
    return None


def _attack_target(
    graph: Graph,
    player_id: str,
    action: Action,
) -> str | None:
    if action.verb == "attack":
        candidates = _list(action.what)
    else:
        return None
    for target in candidates:
        if _can_target_start_combat(graph, player_id, target):
            return target
    return None


def _normalize_attack_action(action: Action, target: str) -> Action:
    if action.verb == "attack":
        return action.model_copy(update={"what": [target]})
    return action


def _can_target_start_combat(
    graph: Graph,
    player_id: str,
    target: str,
) -> bool:
    player_location = location_of(graph, player_id)
    target_location = location_of(graph, target)
    target = graph.nodes.get(target)
    return (
        target is not None
        and target.type == "character"
        and target != player_id
        and can_character_fight(target)
        and player_location is not None
        and target_location == player_location
    )


def _single(value: object) -> str | None:
    if isinstance(value, str):
        return value
    if isinstance(value, list) and value and isinstance(value[0], str):
        return value[0]
    return None


def _list(value: object) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [item for item in value if isinstance(item, str)]
    return []
