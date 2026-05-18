import os
from collections.abc import AsyncIterator, Sequence

from src.db.repo import GraphRepo, ScenarioRepo
from src.game.domain.action import Action, ActionCheckHint
from src.game.domain.content import node_label
from src.game.domain.graph import GraphNode
from src.game.domain.graph.character import is_visible_character
from src.game.domain.graph.query import characters_at, location_of
from src.game.domain.memory import PlayerLogEntry
from src.llm.calls.classify.runner import classify
from src.llm.calls.classify.schema import ClassifyInput
from src.llm.context.classify_view import (
    ClassifyContextLimits,
    build_classify_context_view,
)
from src.llm.client import LLMClient
from src.llm.diag import engine_diag, set_diag_context
from src.locale.render import render
from src.wire.graph.to_front import graph_to_front_state

from .confirmation import (
    GraphConfirmationActive,
    run_graph_action_request,
    run_graph_action_request_stream,
    should_start_graph_roll,
)
from .roll import run_graph_preroll_stream
from ..load import load_runtime_state
from ..narration.input import (
    generate_graph_input_narration,
    generate_graph_input_rejection_narration,
    stream_graph_input_narration,
    stream_graph_input_rejection_narration,
)
from ..narration.result import (
    GraphNarrationResult,
    VisibleNarrationStream,
    gm_log_entry_from_narration,
    parse_graph_narration_answer,
    persist_graph_narration_result,
)
from ..request_result import GraphActionRequestResult, rejected_result
from ..state import GameRuntimeState
from .turn import GraphActionTurnError


class GraphInputError(ValueError):
    pass


# Classification settings


def _classify_temperature() -> float:
    return float(os.environ.get("LLM_CLASSIFY_TEMPERATURE") or "0.0")


def _input_narration_timeout_s(default: float = 30.0) -> float:
    return float(os.environ.get("GRAPH_INPUT_NARRATION_TIMEOUT_S") or str(default))


def _classify_context_limits() -> ClassifyContextLimits:
    return ClassifyContextLimits(
        visible_targets=_classify_limit("VISIBLE_TARGETS", 8),
        exits=_classify_limit("EXITS", 6),
        inventory=_classify_limit("INVENTORY", 10),
        skills=_classify_limit("SKILLS", 8),
        location_items=_classify_limit("LOCATION_ITEMS", 8),
        recent_dialogue=_classify_limit("RECENT_DIALOGUE", 5),
        target_carryables=_classify_limit("TARGET_CARRYABLES", 6),
        merchant_stock=_classify_limit("MERCHANT_STOCK", 8),
        corpses=_classify_limit("CORPSES", 4),
        corpse_items=_classify_limit("CORPSE_ITEMS", 6),
    )


def _classify_limit(name: str, default: int) -> int:
    return int(os.environ.get(f"LLM_CLASSIFY_LIMIT_{name}") or str(default))


# Public flow


async def run_graph_input_turn(
    client: LLMClient,
    repo: GraphRepo,
    game_id: str,
    player_input: str,
    scenario_repo: ScenarioRepo | None = None,
) -> GraphActionRequestResult:
    runtime = await load_runtime_state(repo, game_id, scenario_repo)
    _raise_if_pending_input_blocked(runtime)
    set_diag_context(game_id, runtime.progress.turn_count)
    engine_diag("input:start", chars=len(player_input))
    runtime = await _append_player_input_log(repo, runtime, player_input)
    output = await classify(
        client,
        ClassifyInput(
            player_input=player_input,
            context=build_classify_context_view(
                runtime,
                player_input,
                limits=_classify_context_limits(),
            ),
        ),
        locale=runtime.progress.locale,
        temperature=_classify_temperature(),
    )

    if output.refuse is not None:
        return await _run_graph_refused_input(
            client,
            repo,
            runtime,
            player_input,
            output.refuse.message_hint,
            target=output.refuse.target,
        )
    actions = output.actions or []
    if not actions:
        raise GraphInputError("graph input requires at least one action")

    return await _run_classified_actions(
        client,
        repo,
        runtime,
        actions,
        output.action_checks,
        player_input,
        scenario_repo=scenario_repo,
    )


async def run_graph_input_turn_stream(
    client: LLMClient,
    repo: GraphRepo,
    game_id: str,
    player_input: str,
    scenario_repo: ScenarioRepo | None = None,
) -> AsyncIterator[dict[str, object]]:
    runtime = await load_runtime_state(repo, game_id, scenario_repo)
    _raise_if_pending_input_blocked(runtime)
    set_diag_context(game_id, runtime.progress.turn_count)
    engine_diag("input:start", chars=len(player_input))
    runtime = await _append_player_input_log(repo, runtime, player_input)
    output = await classify(
        client,
        ClassifyInput(
            player_input=player_input,
            context=build_classify_context_view(
                runtime,
                player_input,
                limits=_classify_context_limits(),
            ),
        ),
        locale=runtime.progress.locale,
        temperature=_classify_temperature(),
    )

    if output.refuse is not None:
        async for event in _run_graph_refused_input_stream(
            client,
            repo,
            runtime,
            player_input,
            output.refuse.message_hint,
            target=output.refuse.target,
        ):
            yield event
        return
    actions = output.actions or []
    if not actions:
        raise GraphInputError("graph input requires at least one action")

    async for event in _run_classified_actions_stream(
        client,
        repo,
        runtime,
        actions,
        output.action_checks,
        player_input,
        scenario_repo=scenario_repo,
    ):
        yield event


# Classified action dispatch


async def _run_classified_actions(
    client: LLMClient,
    repo: GraphRepo,
    runtime: GameRuntimeState,
    actions: Sequence[Action],
    action_checks: Sequence[ActionCheckHint],
    player_input: str,
    *,
    scenario_repo: ScenarioRepo | None = None,
) -> GraphActionRequestResult:
    result: GraphActionRequestResult | None = None
    for index, action in enumerate(actions):
        engine_diag(
            "input:classified",
            action=action.verb,
            index=index + 1,
            total=len(actions),
        )
        result = await _run_classified_action(
            client,
            repo,
            runtime,
            player_input,
            action,
            _check_hint_at(action_checks, index),
            scenario_repo=scenario_repo,
        )
        runtime = result.runtime
        if result.status != "executed":
            return result

    if result is None:
        raise GraphInputError("graph input requires at least one action")
    return result


async def _run_classified_actions_stream(
    client: LLMClient,
    repo: GraphRepo,
    runtime: GameRuntimeState,
    actions: Sequence[Action],
    action_checks: Sequence[ActionCheckHint],
    player_input: str,
    *,
    scenario_repo: ScenarioRepo | None = None,
) -> AsyncIterator[dict[str, object]]:
    result: GraphActionRequestResult | None = None
    emitted_result = False
    for index, action in enumerate(actions):
        engine_diag(
            "input:classified",
            action=action.verb,
            index=index + 1,
            total=len(actions),
        )
        async for event in _run_classified_action_stream(
            client,
            repo,
            runtime,
            player_input,
            action,
            _check_hint_at(action_checks, index),
            scenario_repo=scenario_repo,
        ):
            if event["type"] == "final":
                result = _event_result(event)
            elif event["type"] == "result":
                if not emitted_result:
                    yield event
                    emitted_result = True
            else:
                yield event

        if result is None:
            raise GraphInputError("graph input requires at least one action")
        runtime = result.runtime
        if result.status != "executed":
            yield {"type": "final", "result": result}
            return

    if result is None:
        raise GraphInputError("graph input requires at least one action")
    yield {"type": "final", "result": result}


async def _run_classified_action(
    client: LLMClient,
    repo: GraphRepo,
    runtime: GameRuntimeState,
    player_input: str,
    action: Action,
    check_hint: ActionCheckHint | None,
    *,
    scenario_repo: ScenarioRepo | None = None,
) -> GraphActionRequestResult:
    if _should_start_check_roll(runtime, action, check_hint):
        from .roll import start_graph_roll

        return await start_graph_roll(
            repo,
            runtime.progress.game_id,
            action,
            reason=check_hint.reason if check_hint is not None else None,
            player_input=player_input,
            scenario_repo=scenario_repo,
        )
    if action.verb in {"speak", "pass"} and runtime.progress.graph_combat_state is None:
        return await _run_graph_narrative_input(
            client,
            repo,
            runtime,
            player_input,
            action,
        )
    try:
        return await run_graph_action_request(
            repo,
            runtime.progress.game_id,
            action,
            llm=client,
            scenario_repo=scenario_repo,
        )
    except GraphActionTurnError as exc:
        return await _run_graph_rejected_input(
            client,
            repo,
            runtime,
            player_input,
            action,
            exc,
        )


async def _run_classified_action_stream(
    client: LLMClient,
    repo: GraphRepo,
    runtime: GameRuntimeState,
    player_input: str,
    action: Action,
    check_hint: ActionCheckHint | None,
    *,
    scenario_repo: ScenarioRepo | None = None,
) -> AsyncIterator[dict[str, object]]:
    if _should_start_check_roll(runtime, action, check_hint):
        async for event in run_graph_preroll_stream(
            client,
            repo,
            runtime.progress.game_id,
            action,
            player_input=player_input,
            reason=check_hint.reason if check_hint is not None else None,
            scenario_repo=scenario_repo,
        ):
            yield event
        return
    if action.verb in {"speak", "pass"} and runtime.progress.graph_combat_state is None:
        async for event in _run_graph_narrative_input_stream(
            client,
            repo,
            runtime,
            player_input,
            action,
        ):
            yield event
        return
    try:
        async for event in run_graph_action_request_stream(
            repo,
            runtime.progress.game_id,
            action,
            llm=client,
            scenario_repo=scenario_repo,
        ):
            yield event
    except GraphActionTurnError as exc:
        async for event in _run_graph_rejected_input_stream(
            client,
            repo,
            runtime,
            player_input,
            action,
            exc,
        ):
            yield event


def _event_result(event: dict[str, object]) -> GraphActionRequestResult:
    result = event.get("result")
    if not isinstance(result, GraphActionRequestResult):
        raise GraphInputError("graph input stream requires result events")
    return result


def _check_hint_at(
    action_checks: Sequence[ActionCheckHint],
    index: int,
) -> ActionCheckHint | None:
    if index >= len(action_checks):
        return None
    return action_checks[index]


def _should_start_check_roll(
    runtime: GameRuntimeState,
    action: Action,
    check_hint: ActionCheckHint | None,
) -> bool:
    return should_start_graph_roll(
        runtime,
        action,
        check_required=check_hint is not None and check_hint.required,
    )


def _raise_if_pending_input_blocked(runtime: GameRuntimeState) -> None:
    if runtime.progress.pending_confirmation is not None:
        raise GraphConfirmationActive(
            "a pending_confirmation is already active; call graph confirm instead"
        )
    if runtime.progress.pending_roll is not None:
        raise GraphConfirmationActive(
            "a pending_roll is already active; call graph roll instead"
        )


# Rejected action narration


async def _run_graph_rejected_input(
    client: LLMClient,
    repo: GraphRepo,
    runtime: GameRuntimeState,
    player_input: str,
    action: Action,
    exc: GraphActionTurnError,
) -> GraphActionRequestResult:
    reason = str(exc)
    engine_diag("input:action_rejected", action=action.verb, reason=reason)
    public_reason = _public_action_rejection_reason(runtime, reason)
    return await _run_graph_rejected_reason_input(
        client,
        repo,
        runtime,
        player_input,
        action,
        public_reason,
    )


async def _run_graph_refused_input(
    client: LLMClient,
    repo: GraphRepo,
    runtime: GameRuntimeState,
    player_input: str,
    public_reason: str,
    *,
    target: str | None = None,
) -> GraphActionRequestResult:
    action = Action(verb="pass", to=target)
    engine_diag("input:refused", reason=public_reason)
    return await _run_graph_rejected_reason_input(
        client,
        repo,
        runtime,
        player_input,
        action,
        public_reason,
    )


async def _run_graph_rejected_reason_input(
    client: LLMClient,
    repo: GraphRepo,
    runtime: GameRuntimeState,
    player_input: str,
    action: Action,
    public_reason: str,
) -> GraphActionRequestResult:
    narration_result = await generate_graph_input_rejection_narration(
        client,
        runtime,
        player_input,
        action,
        public_reason,
        timeout_s=_input_narration_timeout_s(),
    )
    text = narration_result.narration or public_reason
    narration_result = narration_result.model_copy(update={"narration": text})
    return await _persist_graph_rejected_input(
        repo,
        runtime,
        player_input,
        action,
        narration_result,
    )


async def _run_graph_rejected_input_stream(
    client: LLMClient,
    repo: GraphRepo,
    runtime: GameRuntimeState,
    player_input: str,
    action: Action,
    exc: GraphActionTurnError,
) -> AsyncIterator[dict[str, object]]:
    reason = str(exc)
    engine_diag("input:action_rejected", action=action.verb, reason=reason)
    public_reason = _public_action_rejection_reason(runtime, reason)
    async for event in _run_graph_rejected_reason_input_stream(
        client,
        repo,
        runtime,
        player_input,
        action,
        public_reason,
    ):
        yield event


async def _run_graph_refused_input_stream(
    client: LLMClient,
    repo: GraphRepo,
    runtime: GameRuntimeState,
    player_input: str,
    public_reason: str,
    *,
    target: str | None = None,
) -> AsyncIterator[dict[str, object]]:
    action = Action(verb="pass", to=target)
    engine_diag("input:refused", reason=public_reason)
    async for event in _run_graph_rejected_reason_input_stream(
        client,
        repo,
        runtime,
        player_input,
        action,
        public_reason,
    ):
        yield event


async def _run_graph_rejected_reason_input_stream(
    client: LLMClient,
    repo: GraphRepo,
    runtime: GameRuntimeState,
    player_input: str,
    action: Action,
    public_reason: str,
) -> AsyncIterator[dict[str, object]]:
    yield {"type": "result", "result": _neutral_stream_result(runtime)}
    stream = VisibleNarrationStream()
    async for chunk in stream_graph_input_rejection_narration(
        client,
        runtime,
        player_input,
        action,
        public_reason,
        timeout_s=_input_narration_timeout_s(),
    ):
        for visible in stream.push(chunk):
            yield {"type": "narration_delta", "text": visible}
    for visible in stream.finish():
        yield {"type": "narration_delta", "text": visible}

    narration_result = parse_graph_narration_answer(stream.answer())
    text = narration_result.narration or public_reason
    narration_result = narration_result.model_copy(update={"narration": text})
    result = await _persist_graph_rejected_input(
        repo,
        runtime,
        player_input,
        action,
        narration_result,
    )
    yield {"type": "final", "result": result}


async def _persist_graph_rejected_input(
    repo: GraphRepo,
    runtime: GameRuntimeState,
    player_input: str,
    action: Action,
    narration_result: GraphNarrationResult,
) -> GraphActionRequestResult:
    entry = gm_log_entry_from_narration(
        runtime.progress.next_log_id,
        narration_result,
    )
    progress = runtime.progress.model_copy(
        update={
            "turn_count": runtime.progress.turn_count + 1,
            "next_log_id": entry.id + 1,
        }
    )
    next_runtime = runtime.model_copy(
        update={
            "progress": progress,
            "log_entries": [*runtime.log_entries, entry],
        }
    )
    await repo.append_log_entries(runtime.progress.game_id, [entry])
    await repo.save_progress(progress)
    next_runtime = await persist_graph_narration_result(
        repo,
        next_runtime,
        narration_result,
        player_input=player_input,
        target=_action_target(action),
    )
    engine_diag("input:done", status="rejected", action=action.verb)
    return rejected_result(
        next_runtime,
        graph_to_front_state(next_runtime),
        suggestions=narration_result.suggestions,
    )


async def _append_player_input_log(
    repo: GraphRepo,
    runtime: GameRuntimeState,
    player_input: str,
) -> GameRuntimeState:
    entry = PlayerLogEntry(
        id=runtime.progress.next_log_id,
        kind="player",
        text=player_input,
    )
    progress = runtime.progress.model_copy(update={"next_log_id": entry.id + 1})
    next_runtime = runtime.model_copy(
        update={
            "progress": progress,
            "log_entries": [*runtime.log_entries, entry],
        }
    )
    await repo.append_log_entries(runtime.progress.game_id, [entry])
    await repo.save_progress(progress)
    return next_runtime


# Narrative input


async def _run_graph_narrative_input(
    client: LLMClient,
    repo: GraphRepo,
    runtime: GameRuntimeState,
    player_input: str,
    action: Action,
) -> GraphActionRequestResult:
    subject_id = _resolve_narrative_subject(runtime, action)
    narration_result = await generate_graph_input_narration(
        client,
        runtime,
        player_input,
        action,
        subject_id,
        timeout_s=_input_narration_timeout_s(),
    )
    text = narration_result.narration
    if not text:
        text = _fallback_input_narration(runtime, subject_id)
        narration_result = GraphNarrationResult(narration=text)

    return await _finish_graph_narrative_input(
        repo,
        runtime,
        action,
        subject_id,
        narration_result,
        player_input=player_input,
    )


async def _run_graph_narrative_input_stream(
    client: LLMClient,
    repo: GraphRepo,
    runtime: GameRuntimeState,
    player_input: str,
    action: Action,
) -> AsyncIterator[dict[str, object]]:
    subject_id = _resolve_narrative_subject(runtime, action)
    yield {"type": "result", "result": _neutral_stream_result(runtime)}
    stream = VisibleNarrationStream()
    async for chunk in stream_graph_input_narration(
        client,
        runtime,
        player_input,
        action,
        subject_id,
        timeout_s=_input_narration_timeout_s(),
    ):
        for visible in stream.push(chunk):
            yield {"type": "narration_delta", "text": visible}
    for visible in stream.finish():
        yield {"type": "narration_delta", "text": visible}

    narration_result = parse_graph_narration_answer(stream.answer())
    text = narration_result.narration
    if not text:
        text = _fallback_input_narration(runtime, subject_id)
        narration_result = GraphNarrationResult(narration=text)

    result = await _finish_graph_narrative_input(
        repo,
        runtime,
        action,
        subject_id,
        narration_result,
        player_input=player_input,
    )
    yield {"type": "final", "result": result}


def _neutral_stream_result(runtime: GameRuntimeState) -> GraphActionRequestResult:
    return GraphActionRequestResult(
        runtime=runtime,
        status="executed",
        outcome="neutral",
        front_state=graph_to_front_state(runtime),
    )


async def _finish_graph_narrative_input(
    repo: GraphRepo,
    runtime: GameRuntimeState,
    action: Action,
    subject_id: str | None,
    narration_result: GraphNarrationResult,
    *,
    player_input: str,
) -> GraphActionRequestResult:
    entry = gm_log_entry_from_narration(
        runtime.progress.next_log_id,
        narration_result,
    )
    progress = runtime.progress.model_copy(
        update={
            "turn_count": runtime.progress.turn_count + 1,
            "next_log_id": entry.id + 1,
            "active_subject_id": subject_id or runtime.progress.active_subject_id,
        }
    )
    next_runtime = runtime.model_copy(
        update={
            "progress": progress,
            "log_entries": [*runtime.log_entries, entry],
        }
    )
    await repo.append_log_entries(runtime.progress.game_id, [entry])
    await repo.save_progress(progress)
    next_runtime = await persist_graph_narration_result(
        repo,
        next_runtime,
        narration_result,
        player_input=player_input,
        target=subject_id,
    )
    engine_diag("input:done", status="executed", action=action.verb)
    return GraphActionRequestResult(
        runtime=next_runtime,
        status="executed",
        front_state=graph_to_front_state(next_runtime),
        suggestions=narration_result.suggestions,
    )


# Target helpers


def _resolve_narrative_subject(runtime, action) -> str | None:
    target = _single(action.what) or _single(action.to)
    if isinstance(target, str) and _is_at_player_location(runtime, target):
        return target
    if action.verb != "speak":
        return None
    graph = runtime.graph_index
    location_id = location_of(graph, runtime.progress.player_id)
    if location_id is None:
        return None
    for character_id in characters_at(graph, location_id):
        if character_id == runtime.progress.player_id:
            continue
        node = graph.nodes.get(character_id)
        if node is None or node.type != "character":
            continue
        if is_visible_character(node):
            return character_id
    return None


def _is_at_player_location(runtime, node_id: str) -> bool:
    graph = runtime.graph_index
    player_location = location_of(graph, runtime.progress.player_id)
    return (
        player_location is not None and location_of(graph, node_id) == player_location
    )


def _node_name(runtime, node: GraphNode | None) -> str:
    if node is None:
        return render("runtime.none", runtime.progress.locale)
    return node_label(runtime.content, node)


def _fallback_input_narration(runtime: GameRuntimeState, subject_id: str | None) -> str:
    subject = runtime.graph.nodes.get(subject_id or "")
    if subject is not None:
        return render(
            "runtime.input.dialogue_quiet",
            runtime.progress.locale,
            target=_node_name(runtime, subject),
        )
    return render("runtime.input.quiet", runtime.progress.locale)


def _public_action_rejection_reason(runtime: GameRuntimeState, reason: str) -> str:
    text = reason.lower()
    locale = runtime.progress.locale
    phrase_keys = (
        ("protected target cannot be attacked", "log.error.protected_target"),
        ("hp already full", "log.error.hp_full"),
        ("mp already full", "log.error.mp_full"),
        ("item is not carried", "log.error.item_not_in_inventory"),
        ("missing item", "log.error.unknown_item"),
        ("item is not consumable", "log.error.not_consumable"),
        ("merchant does not have enough gold", "log.error.npc_not_enough_gold"),
        ("source mismatch", "log.error.trade_item_unavailable"),
        ("player does not have enough gold", "log.error.not_enough_gold"),
        ("not enough gold", "log.error.not_enough_gold"),
        ("affinity", "log.error.affinity_too_low"),
        ("equipped item", "log.error.cant_sell_equipped"),
        ("max level", "log.error.max_level"),
        ("not enough experience", "log.error.not_enough_xp"),
    )
    for phrase, key in phrase_keys:
        if phrase in text:
            return render(key, locale)
    return render("log.error.generic_block", locale)


def _action_target(action: Action) -> str | None:
    return _single(action.what) or _single(action.to) or _single(action.with_)


def _action_target_node(
    runtime: GameRuntimeState,
    action: Action,
) -> GraphNode | None:
    target = _action_target(action)
    if target is None:
        return None
    return runtime.graph.nodes.get(target)


def _single(value: object) -> str | None:
    if isinstance(value, str):
        return value
    if isinstance(value, list) and value and isinstance(value[0], str):
        return value[0]
    return None
