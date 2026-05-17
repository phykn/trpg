import asyncio
import json
import os
import random
import secrets
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any

from openai import APIConnectionError, InternalServerError, RateLimitError

from src.db.repo import GraphRepo, ScenarioRepo
from src.game.domain.action import Action
from src.game.domain.errors import LLMUnavailable
from src.game.domain.graph import Graph, GraphEdge
from src.game.domain.memory import BonusItem, GMLogEntry, LogEntry, RollLogEntry
from src.game.engines.graph.quest import (
    plan_quest_progress_for_trigger,
    plan_quest_rewards,
)
from src.game.rules import RULES
from src.game.rules.dc import compute_grade, compute_required_roll, pick_dc
from src.locale.labels import roll_dice_label, stat_label
from src.locale.render import render
from src.llm.calls.runner import get_prompt
from src.llm.client import LLMClient
from src.llm.diag import engine_diag, set_diag_context
from src.wire.graph.to_front import graph_to_front_state

from ..action.apply import GraphRuntimeDirty, apply_runtime_graph_changes
from ..load import load_runtime_state
from ..narration.context import build_roll_narration_payload
from ..narration.result import (
    GraphNarrationResult,
    VisibleNarrationStream,
    parse_graph_narration_answer,
    persist_graph_narration_result,
)
from ..pending_action import build_pending_action_payload, load_pending_action
from ..request_result import (
    GraphActionRequestResult,
    GraphResultOutcome,
    executed_result,
    roll_required_result,
)
from ..state import GameRuntimeState
from .turn import (
    run_graph_action_turn_from_runtime,
    run_graph_action_turn_from_runtime_stream,
)


class GraphRollError(ValueError):
    pass


class GraphRollExpected(GraphRollError):
    pass


class GraphRollActive(GraphRollError):
    pass


@dataclass
class _ResolvedGraphRoll:
    runtime: GameRuntimeState
    action: Action
    pending: dict[str, Any]
    roll_entry: RollLogEntry
    grade: str
    outcome: GraphResultOutcome


def _default_roll_dc(default: int = 13) -> int:
    raw = os.getenv("GRAPH_DEFAULT_ROLL_DC")
    if raw is not None:
        try:
            return int(raw)
        except ValueError:
            return default
    return pick_dc("normal")


def _roll_narration_timeout_s(default: float = 30.0) -> float:
    return float(os.environ.get("GRAPH_ROLL_NARRATION_TIMEOUT_S") or str(default))


def _narration_temperature(default: float = 1.0) -> float:
    return float(os.environ.get("LLM_GRAPH_NARRATE_TEMPERATURE") or str(default))


async def start_graph_roll(
    repo: GraphRepo,
    game_id: str,
    action: Action,
    *,
    reason: str | None = None,
    player_input: str | None = None,
    scenario_repo: ScenarioRepo | None = None,
    append_body_log: bool = False,
) -> GraphActionRequestResult:
    runtime = await load_runtime_state(repo, game_id, scenario_repo)
    set_diag_context(game_id, runtime.progress.turn_count)
    engine_diag("roll:start", action=action.verb)
    if runtime.progress.pending_roll is not None:
        raise GraphRollActive("a pending_roll is already active")
    if runtime.progress.pending_confirmation is not None:
        raise GraphRollActive("a pending_confirmation is already active")

    pending = build_pending_roll(
        runtime.graph.nodes[runtime.progress.player_id].properties,
        action,
        runtime.progress.locale,
        graph=runtime.graph,
        player_id=runtime.progress.player_id,
        reason=reason,
    )
    if player_input:
        pending["player_input"] = player_input
    progress_update: dict[str, Any] = {"pending_roll": pending}
    next_log_entries = list(runtime.log_entries)
    entries: list[LogEntry] = []
    if append_body_log:
        entry = GMLogEntry(
            id=runtime.progress.next_log_id,
            kind="gm",
            text=_str(pending.get("body"), "body"),
        )
        progress_update["next_log_id"] = entry.id + 1
        next_log_entries.append(entry)
        entries.append(entry)
    next_progress = runtime.progress.model_copy(update=progress_update)
    next_runtime = runtime.model_copy(
        update={
            "progress": next_progress,
            "log_entries": next_log_entries,
        }
    )
    await repo.append_log_entries(game_id, entries)
    await repo.save_progress(next_progress)
    engine_diag("roll:pending", kind=pending.get("kind"))
    return roll_required_result(
        next_runtime,
        graph_to_front_state(next_runtime),
        pending,
    )


async def run_graph_preroll_stream(
    _llm: LLMClient | None,
    repo: GraphRepo,
    game_id: str,
    action: Action,
    *,
    player_input: str | None = None,
    reason: str | None = None,
    scenario_repo: ScenarioRepo | None = None,
) -> AsyncIterator[dict[str, object]]:
    result = await start_graph_roll(
        repo,
        game_id,
        action,
        reason=reason,
        player_input=player_input,
        scenario_repo=scenario_repo,
    )
    yield {"type": "result", "result": result}
    yield {"type": "final", "result": result}


async def run_graph_roll(
    repo: GraphRepo,
    game_id: str,
    roll_id: str,
    *,
    dice: int | None = None,
    scenario_repo: ScenarioRepo | None = None,
) -> GraphActionRequestResult:
    resolved = await _resolve_graph_roll(
        repo,
        game_id,
        roll_id,
        dice=dice,
        scenario_repo=scenario_repo,
    )
    if resolved.outcome == "failure" and not _is_narrative_roll_action(resolved.action):
        return executed_result(
            resolved.runtime,
            graph_to_front_state(resolved.runtime),
            outcome="failure",
        )

    if _is_narrative_roll_action(resolved.action):
        return await _finish_narrative_roll(
            repo,
            game_id,
            resolved.runtime,
            resolved.action,
            outcome=resolved.outcome,
        )

    turn_result = await run_graph_action_turn_from_runtime(
        repo,
        game_id,
        resolved.runtime,
        resolved.action,
        llm=None,
        narration_outcome=resolved.outcome,
    )
    result = executed_result(
        turn_result.runtime,
        turn_result.front_state,
        outcome=resolved.outcome,
        suggestions=turn_result.suggestions,
    )
    return result.model_copy(update={"dispatch": turn_result.dispatch})


async def run_graph_roll_stream(
    llm: LLMClient | None,
    repo: GraphRepo,
    game_id: str,
    roll_id: str,
    *,
    dice: int | None = None,
    scenario_repo: ScenarioRepo | None = None,
) -> AsyncIterator[dict[str, object]]:
    resolved = await _resolve_graph_roll(
        repo,
        game_id,
        roll_id,
        dice=dice,
        scenario_repo=scenario_repo,
    )
    if resolved.outcome == "success" and not _is_narrative_roll_action(resolved.action):
        async for event in run_graph_action_turn_from_runtime_stream(
            repo,
            game_id,
            resolved.runtime,
            resolved.action,
            llm=llm,
            result_outcome=resolved.outcome,
            narration_outcome=resolved.outcome,
        ):
            yield event
        return

    result = executed_result(
        resolved.runtime,
        graph_to_front_state(resolved.runtime),
        outcome=resolved.outcome,
    )
    yield {"type": "result", "result": result}
    stream = VisibleNarrationStream()
    async for chunk in _stream_roll_narration(llm, resolved):
        for visible in stream.push(chunk):
            yield {"type": "narration_delta", "text": visible}
    for visible in stream.finish():
        yield {"type": "narration_delta", "text": visible}
    narration_result = parse_graph_narration_answer(stream.answer())
    if not narration_result.narration:
        narration_result = GraphNarrationResult(
            narration=render(
                _roll_resolution_key(resolved.action, resolved.outcome),
                resolved.runtime.progress.locale,
            )
        )
        yield {"type": "narration_delta", "text": narration_result.narration}
    final = await _commit_roll_narration(repo, game_id, resolved, narration_result)
    yield {"type": "final", "result": final}


async def _resolve_graph_roll(
    repo: GraphRepo,
    game_id: str,
    roll_id: str,
    *,
    dice: int | None,
    scenario_repo: ScenarioRepo | None,
) -> _ResolvedGraphRoll:
    runtime = await load_runtime_state(repo, game_id, scenario_repo)
    set_diag_context(game_id, runtime.progress.turn_count)
    engine_diag("roll:resolve", roll=roll_id)
    pending = runtime.progress.pending_roll
    if pending is None:
        raise GraphRollExpected("no pending_roll")
    if pending.get("id") != roll_id:
        raise GraphRollExpected("roll id mismatch")

    action = load_pending_action(pending, error_type=GraphRollExpected)
    required_roll = _int(pending.get("required_roll"), "required_roll")
    rolled = dice if dice is not None else random.randint(1, 20)
    if rolled < 1 or rolled > 20:
        raise GraphRollError("dice must be between 1 and 20")
    grade = compute_grade(dice=rolled, total=rolled, required_roll=required_roll)
    entry = RollLogEntry(
        id=runtime.progress.next_log_id,
        kind="roll",
        check=_str(pending.get("stat_label"), "stat_label"),
        roll=rolled,
        margin=rolled - required_roll,
        result=_roll_result(grade),
        bonus_breakdown=[
            BonusItem(
                label=roll_dice_label(runtime.progress.locale),
                value=rolled,
            )
        ],
    )
    next_progress = runtime.progress.model_copy(
        update={
            "pending_roll": None,
            "turn_count": runtime.progress.turn_count + 1,
            "next_log_id": entry.id + 1,
        }
    )
    next_runtime = runtime.model_copy(
        update={
            "progress": next_progress,
            "log_entries": [*runtime.log_entries, entry],
        }
    )
    await repo.append_log_entries(game_id, [entry])
    await repo.save_progress(next_progress)
    engine_diag(
        "roll:done",
        action=action.verb,
        result=entry.result,
        rolled=rolled,
        required=required_roll,
        next_turn=next_progress.turn_count,
    )
    outcome: GraphResultOutcome = "success" if entry.result == "success" else "failure"
    next_runtime, changed_edge_ids = _apply_roll_relation_effect(
        next_runtime,
        action,
        grade,
        roll_outcome=outcome,
    )
    next_runtime, changed_node_ids = _apply_roll_xp_effect(
        next_runtime,
        action,
        grade,
        roll_outcome=outcome,
    )
    (
        next_runtime,
        quest_dirty,
        completed_quest_ids,
    ) = _apply_roll_quest_effect(next_runtime, action, roll_outcome=outcome)
    changed_node_ids.extend(quest_dirty.changed_node_ids)
    changed_edge_ids.extend(quest_dirty.changed_edge_ids)
    removed_edge_ids = list(quest_dirty.removed_edge_ids)

    if changed_edge_ids or changed_node_ids or removed_edge_ids:
        await repo.save_graph_changes(
            game_id,
            next_runtime.graph,
            changed_node_ids=sorted(set(changed_node_ids)),
            changed_edge_ids=sorted(set(changed_edge_ids)),
            removed_edge_ids=sorted(set(removed_edge_ids)),
        )
    if next_runtime.progress.active_quest_id in completed_quest_ids:
        next_progress = next_runtime.progress.model_copy(
            update={"active_quest_id": None}
        )
        next_runtime = next_runtime.model_copy(update={"progress": next_progress})
        await repo.save_progress(next_progress)
    return _ResolvedGraphRoll(
        runtime=next_runtime,
        action=action,
        pending=pending,
        roll_entry=entry,
        grade=grade,
        outcome=outcome,
    )


async def _stream_roll_narration(
    llm: LLMClient | None,
    resolved: _ResolvedGraphRoll,
) -> AsyncIterator[str]:
    if llm is None:
        return
    payload = build_roll_narration_payload(
        runtime=resolved.runtime,
        action=resolved.action,
        pending=resolved.pending,
        roll_entry=resolved.roll_entry,
        outcome=resolved.outcome,
    )
    messages = [
        {
            "role": "system",
            "content": get_prompt("graph_narrate", resolved.runtime.progress.locale),
        },
        {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
    ]
    try:
        async with asyncio.timeout(_roll_narration_timeout_s()):
            async for part in llm.chat_stream(
                messages,
                think=False,
                agent="graph_narrate",
                temperature=_narration_temperature(),
            ):
                answer = part.get("answer")
                if isinstance(answer, str) and answer:
                    yield answer
    except (
        LLMUnavailable,
        OSError,
        TimeoutError,
        InternalServerError,
        APIConnectionError,
        RateLimitError,
    ):
        return


async def _commit_roll_narration(
    repo: GraphRepo,
    game_id: str,
    resolved: _ResolvedGraphRoll,
    narration_result: GraphNarrationResult,
) -> GraphActionRequestResult:
    runtime = resolved.runtime
    log_entries: list[LogEntry] = []
    if narration_result.narration:
        entry = GMLogEntry(
            id=runtime.progress.next_log_id,
            kind="gm",
            text=narration_result.narration,
            outcome=resolved.outcome,
        )
        log_entries.append(entry)
        next_progress = runtime.progress.model_copy(
            update={"next_log_id": entry.id + 1}
        )
        runtime = runtime.model_copy(
            update={
                "progress": next_progress,
                "log_entries": [*runtime.log_entries, entry],
            }
        )
        await repo.append_log_entries(game_id, log_entries)
        await repo.save_progress(next_progress)
    runtime = await persist_graph_narration_result(
        repo,
        runtime,
        narration_result,
        target_id=_action_target_id(resolved.action),
    )
    return executed_result(
        runtime,
        graph_to_front_state(runtime),
        outcome=resolved.outcome,
        suggestions=narration_result.suggestions,
    )


def build_pending_roll(
    player_properties: dict[str, Any],
    action: Action,
    locale: str = "ko",
    *,
    graph: Graph | None = None,
    player_id: str | None = None,
    reason: str | None = None,
) -> dict[str, Any]:
    stat = _roll_stat(action)
    label = stat_label(stat, locale)
    stats = player_properties.get("stats")
    stat_value = stats.get(stat, 10) if isinstance(stats, dict) else 10
    base_dc = _default_roll_dc()
    effective_dc = _effective_roll_dc(base_dc, graph, player_id, action)
    required_roll = compute_required_roll(effective_dc, _int(stat_value, stat))
    body = reason or _roll_body(action, locale)
    return {
        "id": f"roll_{secrets.token_hex(4)}",
        "kind": action.verb,
        "title": render("runtime.roll.title", locale, label=label),
        "body": body,
        "check_reason": body,
        "stat": stat,
        "stat_label": label,
        "required_roll": required_roll,
        "base_dc": base_dc,
        "effective_dc": effective_dc,
        "payload": build_pending_action_payload(action),
    }


def _roll_stat(action: Action) -> str:
    if action.verb == "perceive":
        return "mind"
    if action.verb == "speak":
        return "presence"
    if action.verb == "move":
        return "agility"
    if action.verb == "use":
        return "mind"
    if action.verb == "transfer":
        if action.how == "steal":
            return "agility"
        return "presence"
    return "body"


def _roll_body(action: Action, locale: str) -> str:
    if action.verb == "perceive":
        return render("runtime.roll.body.perceive", locale)
    if action.verb == "speak":
        return render("runtime.roll.body.speak", locale)
    if action.verb == "move":
        return render("runtime.roll.body.move", locale)
    return render("runtime.roll.body.default", locale)


def _effective_roll_dc(
    base_dc: int,
    graph: Graph | None,
    player_id: str | None,
    action: Action,
) -> int:
    if graph is None or player_id is None:
        return base_dc
    target_id = _roll_npc_target_id(graph, player_id, action)
    if target_id is None:
        return base_dc
    affinity = _relation_affinity(graph, target_id, player_id)
    affinity_band = int(affinity / 10)
    return max(1, min(20, base_dc - affinity_band))


def _apply_roll_relation_effect(
    runtime: GameRuntimeState,
    action: Action,
    grade: str,
    *,
    roll_outcome: GraphResultOutcome,
) -> tuple[GameRuntimeState, list[str]]:
    target_id = _roll_npc_target_id(
        runtime.graph,
        runtime.progress.player_id,
        action,
    )
    if target_id is None:
        return runtime, []
    delta = _roll_affinity_delta(action, grade, roll_outcome)
    if delta == 0:
        return runtime, []

    graph = runtime.graph.model_copy(deep=True)
    edge_id = _relation_edge_id(target_id, runtime.progress.player_id)
    edge = graph.edges.get(edge_id)
    if edge is None:
        edge = GraphEdge(
            id=edge_id,
            type="relation",
            from_node_id=target_id,
            to_node_id=runtime.progress.player_id,
            properties={"affinity": 0},
        )
        graph.edges[edge_id] = edge

    affinity = edge.properties.get("affinity")
    current = affinity if isinstance(affinity, int) else 0
    edge.properties["affinity"] = current + delta
    return runtime.model_copy(update={"graph": graph}), [edge_id]


def _apply_roll_xp_effect(
    runtime: GameRuntimeState,
    action: Action,
    grade: str,
    *,
    roll_outcome: GraphResultOutcome,
) -> tuple[GameRuntimeState, list[str]]:
    if roll_outcome != "success":
        return runtime, []
    amount = RULES.growth.roll_xp.get(grade, 0)
    if amount <= 0:
        return runtime, []
    player_id = runtime.progress.player_id
    player = runtime.graph.nodes.get(player_id)
    if player is None:
        return runtime, []
    key = _roll_xp_award_key(action)
    existing = player.properties.get("xp_award_keys")
    keys = (
        [item for item in existing if isinstance(item, str)]
        if isinstance(existing, list)
        else []
    )
    if key in keys:
        return runtime, []

    graph = runtime.graph.model_copy(deep=True)
    next_player = graph.nodes[player_id]
    current_xp = next_player.properties.get("xp_pool")
    xp_pool = current_xp if isinstance(current_xp, int) else 0
    next_player.properties["xp_pool"] = xp_pool + amount
    next_player.properties["xp_award_keys"] = [*keys, key]
    return runtime.model_copy(update={"graph": graph}), [player_id]


def _apply_roll_quest_effect(
    runtime: GameRuntimeState,
    action: Action,
    *,
    roll_outcome: GraphResultOutcome,
) -> tuple[GameRuntimeState, GraphRuntimeDirty, list[str]]:
    dirty = GraphRuntimeDirty()
    if roll_outcome != "success":
        return runtime, dirty, []
    trigger = _roll_quest_trigger(runtime, action)
    if trigger is None:
        return runtime, dirty, []

    trigger_type, target_id = trigger
    progress = plan_quest_progress_for_trigger(runtime.graph, trigger_type, target_id)
    if not progress.changes:
        return runtime, dirty, []

    progress_apply = apply_runtime_graph_changes(runtime, progress.changes)
    next_runtime = progress_apply.runtime
    dirty.add_apply_result(progress_apply)
    for quest_id in progress.completed_quest_ids:
        reward = plan_quest_rewards(
            next_runtime.graph,
            quest_id,
            next_runtime.progress.player_id,
        )
        if not reward.changes:
            continue
        reward_apply = apply_runtime_graph_changes(next_runtime, reward.changes)
        next_runtime = reward_apply.runtime
        dirty.add_apply_result(reward_apply)
    return next_runtime, dirty, progress.completed_quest_ids


def _roll_quest_trigger(
    runtime: GameRuntimeState,
    action: Action,
) -> tuple[str, str] | None:
    if action.verb == "speak":
        target_id = _roll_npc_target_id(
            runtime.graph,
            runtime.progress.player_id,
            action,
        )
        return ("social_check", target_id) if target_id is not None else None
    if action.verb == "transfer" and action.how not in {
        "accept",
        "abandon",
        "equip",
        "trade",
        "steal",
        "unequip",
    }:
        target_id = _roll_npc_target_id(
            runtime.graph,
            runtime.progress.player_id,
            action,
        )
        return ("social_check", target_id) if target_id is not None else None
    return None


def _roll_affinity_delta(
    action: Action,
    grade: str,
    roll_outcome: GraphResultOutcome,
) -> int:
    if roll_outcome == "failure":
        if grade == "critical_failure":
            return -RULES.social.affinity_critical
        return RULES.social.affinity_failure
    if not _is_positive_social_success(action):
        return 0
    if grade == "critical_success":
        return RULES.social.affinity_critical
    return RULES.social.affinity_success


def _roll_xp_award_key(action: Action) -> str:
    return f"roll:{action.verb}:{_action_target_id(action) or 'none'}"


def _is_positive_social_success(action: Action) -> bool:
    return action.verb == "speak" and action.how in {"friendly", "recruit"}


def _relation_affinity(graph: Graph, npc_id: str, player_id: str) -> int:
    edge = graph.edges.get(_relation_edge_id(npc_id, player_id))
    if edge is None:
        return 0
    affinity = edge.properties.get("affinity")
    return affinity if isinstance(affinity, int) else 0


def _relation_edge_id(npc_id: str, player_id: str) -> str:
    return f"relation:{npc_id}:{player_id}"


def _roll_npc_target_id(
    graph: Graph,
    player_id: str,
    action: Action,
) -> str | None:
    for candidate in _roll_target_candidates(action):
        node = graph.nodes.get(candidate)
        if node is not None and node.type == "character" and candidate != player_id:
            return candidate
    return None


def _roll_target_candidates(action: Action) -> list[str]:
    if action.verb == "speak":
        return _strings(action.to) + _strings(action.what)
    if action.verb == "transfer":
        return _strings(action.from_) + _strings(action.to) + _strings(action.what)
    return _strings(action.to) + _strings(action.what) + _strings(action.with_)


def _action_target_id(action: Action) -> str | None:
    for value in (action.what, action.to, action.from_, action.with_):
        strings = _strings(value)
        if strings:
            return strings[0]
    return None


def _strings(value: object) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [item for item in value if isinstance(item, str)]
    return []


async def _finish_narrative_roll(
    repo: GraphRepo,
    game_id: str,
    runtime: GameRuntimeState,
    action: Action,
    *,
    outcome: GraphResultOutcome,
) -> GraphActionRequestResult:
    entry = GMLogEntry(
        id=runtime.progress.next_log_id,
        kind="gm",
        text=render(_roll_resolution_key(action, outcome), runtime.progress.locale),
        outcome=outcome,
    )
    next_progress = runtime.progress.model_copy(update={"next_log_id": entry.id + 1})
    next_runtime = runtime.model_copy(
        update={
            "progress": next_progress,
            "log_entries": [*runtime.log_entries, entry],
        }
    )
    await repo.append_log_entries(game_id, [entry])
    await repo.save_progress(next_progress)
    return executed_result(
        next_runtime,
        graph_to_front_state(next_runtime),
        outcome=outcome,
    )


def _is_narrative_roll_action(action: Action) -> bool:
    return action.verb in {"perceive", "speak"}


def _roll_resolution_key(action: Action, outcome: GraphResultOutcome) -> str:
    if action.verb == "perceive":
        return f"runtime.roll.resolve.perceive.{outcome}"
    if action.verb == "speak":
        return f"runtime.roll.resolve.speak.{outcome}"
    return f"runtime.roll.resolve.default.{outcome}"


def _roll_result(grade: str) -> str:
    if grade in {"critical_success", "success"}:
        return "success"
    return "fail"


def _int(value: object, field: str) -> int:
    if not isinstance(value, int):
        raise GraphRollError(f"{field} must be an integer")
    return value


def _str(value: object, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise GraphRollError(f"{field} must be a string")
    return value
