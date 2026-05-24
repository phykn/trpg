import asyncio
import difflib
import os
import random
import re
import secrets
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any

from openai import APIConnectionError, InternalServerError, RateLimitError

from src.db.repo import GraphRepo, ScenarioRepo
from src.game.domain.action import Action
from src.game.domain.content import node_label, node_text
from src.game.domain.errors import LLMUnavailable
from src.game.domain.graph import Graph
from src.game.domain.memory import (
    BonusItem,
    GMLogEntry,
    LogEntry,
    NarrationCue,
    RollLogEntry,
)
from src.game.engines.graph.roll import (
    plan_roll_check,
    plan_roll_graph_effects,
    plan_roll_quest_trigger,
)
from src.game.engines.graph.progression import plan_progression_after_quest_completion
from src.game.engines.graph.quest import (
    plan_quest_progress_for_trigger,
    plan_quest_rewards,
)
from src.game.rules.dc import compute_grade, pick_dc
from src.locale.labels import roll_dice_label, stat_label
from src.locale.render import render
from src.llm.calls.runner import get_prompt
from src.llm.client import LLMClient
from src.llm.diag import engine_diag, set_diag_context
from src.wire.graph.to_front import graph_to_front_state

from ..action.apply import GraphRuntimeDirty, apply_runtime_graph_changes
from ..load import load_runtime_state
from ..narration.brief import build_narration_brief
from ..narration.context import build_roll_narration_payload
from ..narration.input import stream_graph_preroll_narration
from ..narration.result import (
    GraphNarrationResult,
    VisibleNarrationStream,
    gm_log_entry_from_narration,
    parse_graph_narration_answer,
    persist_graph_narration_result,
)
from ..narration.safety import guard_speak_narration_player_quote
from ..narration.suggestions import GraphSuggestion, filter_grounded_suggestions
from ..pending_action import build_pending_action_payload, load_pending_action
from ..request_result import (
    GraphActionRequestResult,
    GraphResultOutcome,
    executed_result,
    roll_required_result,
)
from ..state import GameRuntimeState
from ..env import env_float
from .roll_affinity import affinity_change_cues
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
    completed_quest_ids: list[str]
    affinity_cues: list[NarrationCue]


def _default_roll_dc(default: int = 13) -> int:
    raw = os.getenv("GRAPH_DEFAULT_ROLL_DC")
    if raw is not None:
        try:
            return int(raw)
        except ValueError:
            return default
    return pick_dc("normal")


def _roll_narration_timeout_s(default: float = 120.0) -> float:
    return env_float("LLM_TIMEOUT_S", default)


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
    llm: LLMClient | None,
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

    stream = VisibleNarrationStream()
    defer_visible_narration = action.verb == "speak"
    if result.pending_roll is not None and llm is not None:
        async for chunk in stream_graph_preroll_narration(
            llm,
            result.runtime,
            player_input,
            action,
            result.pending_roll,
            timeout_s=_roll_narration_timeout_s(),
        ):
            for visible in stream.push(chunk):
                if not defer_visible_narration:
                    yield {"type": "narration_delta", "text": visible}
        for visible in stream.finish():
            if not defer_visible_narration:
                yield {"type": "narration_delta", "text": visible}

    narration_result = parse_graph_narration_answer(stream.answer())
    body = result.pending_roll.get("body") if result.pending_roll is not None else ""
    if not narration_result.narration and isinstance(body, str) and body:
        narration_result = GraphNarrationResult(narration=body)
        if not defer_visible_narration:
            yield {"type": "narration_delta", "text": body}
    narration_result = guard_speak_narration_player_quote(
        result.runtime,
        action,
        _action_target(action),
        narration_result,
        player_input,
    )
    if defer_visible_narration and narration_result.narration:
        yield {"type": "narration_delta", "text": narration_result.narration}
    final_result = await _finish_preroll_body(repo, result, narration_result)
    yield {"type": "final", "result": final_result}


async def _finish_preroll_body(
    repo: GraphRepo,
    result: GraphActionRequestResult,
    narration_result: GraphNarrationResult,
) -> GraphActionRequestResult:
    if not narration_result.narration or result.pending_roll is None:
        return result
    runtime = result.runtime
    pending = dict(result.pending_roll)
    pending["body"] = narration_result.narration
    entry = gm_log_entry_from_narration(
        runtime.progress.next_log_id,
        narration_result,
    )
    progress = runtime.progress.model_copy(
        update={
            "pending_roll": pending,
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
    return GraphActionRequestResult(
        runtime=next_runtime,
        status=result.status,
        outcome=result.outcome,
        front_state=graph_to_front_state(next_runtime),
        pending_roll=pending,
        suggestions=result.suggestions,
    )


async def run_graph_roll(
    repo: GraphRepo,
    game_id: str,
    roll_id: str,
    *,
    dice: int | None = None,
    llm: LLMClient | None = None,
    scenario_repo: ScenarioRepo | None = None,
) -> GraphActionRequestResult:
    resolved = await _resolve_graph_roll(
        repo,
        game_id,
        roll_id,
        dice=dice,
        scenario_repo=scenario_repo,
    )
    if _is_narrative_roll_action(resolved.action):
        return await _finish_narrative_roll(
            repo,
            game_id,
            resolved.runtime,
            resolved.action,
            outcome=resolved.outcome,
            resolved=resolved,
            llm=llm,
        )

    if resolved.outcome == "failure":
        narration_result = await _build_roll_narration(llm, resolved)
        if narration_result.narration:
            return await _commit_roll_narration(repo, game_id, resolved, narration_result)
        return executed_result(
            resolved.runtime,
            graph_to_front_state(resolved.runtime),
            outcome="failure",
        )

    turn_result = await run_graph_action_turn_from_runtime(
        repo,
        game_id,
        resolved.runtime,
        resolved.action,
        llm=None,
        narration_outcome=resolved.outcome,
        extra_ui_cues=resolved.affinity_cues,
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
            extra_ui_cues=resolved.affinity_cues,
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
    resolution_text = _roll_resolution_text(resolved)
    if resolved.outcome == "success" and resolution_text:
        yield {"type": "narration_delta", "text": f"{resolution_text} "}
    async for chunk in _stream_roll_narration(llm, resolved):
        for visible in stream.push(chunk):
            yield {"type": "narration_delta", "text": visible}
    for visible in stream.finish():
        yield {"type": "narration_delta", "text": visible}
    narration_result = parse_graph_narration_answer(stream.answer())
    if not narration_result.narration:
        narration_result = GraphNarrationResult(
            narration=_roll_fallback_text(resolved)
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
    effect = plan_roll_graph_effects(
        next_runtime.graph,
        player_id=next_runtime.progress.player_id,
        action=action,
        grade=grade,
        roll_outcome=outcome,
    )
    affinity_cues = affinity_change_cues(next_runtime, effect.changes)
    if effect.changes:
        effect_apply = apply_runtime_graph_changes(next_runtime, effect.changes)
        next_runtime = effect_apply.runtime
        changed_node_ids = list(effect_apply.changed_node_ids)
        changed_edge_ids = list(effect_apply.changed_edge_ids)
        removed_edge_ids = list(effect_apply.removed_edge_ids)
    else:
        changed_node_ids = []
        changed_edge_ids = []
        removed_edge_ids = []
    (
        next_runtime,
        quest_dirty,
        completed_quest_ids,
    ) = _apply_roll_quest_effect(next_runtime, action, roll_outcome=outcome)
    changed_node_ids.extend(quest_dirty.changed_node_ids)
    changed_edge_ids.extend(quest_dirty.changed_edge_ids)
    removed_edge_ids.extend(quest_dirty.removed_edge_ids)
    next_active_quest_id = next_runtime.progress.active_quest_id
    if completed_quest_ids:
        progression = plan_progression_after_quest_completion(
            next_runtime.graph,
            completed_quest_ids=completed_quest_ids,
            active_quest_id=next_runtime.progress.active_quest_id,
            satisfied_location_ids=_visited_location_ids(next_runtime),
        )
        if progression.changes:
            progression_apply = apply_runtime_graph_changes(
                next_runtime,
                progression.changes,
            )
            next_runtime = progression_apply.runtime
            changed_node_ids.extend(progression_apply.changed_node_ids)
            changed_edge_ids.extend(progression_apply.changed_edge_ids)
            removed_edge_ids.extend(progression_apply.removed_edge_ids)
        for quest_id in progression.auto_completed_quest_ids:
            reward = plan_quest_rewards(
                next_runtime.graph,
                quest_id,
                next_runtime.progress.player_id,
            )
            if not reward.changes:
                continue
            reward_apply = apply_runtime_graph_changes(next_runtime, reward.changes)
            next_runtime = reward_apply.runtime
            changed_node_ids.extend(reward_apply.changed_node_ids)
            changed_edge_ids.extend(reward_apply.changed_edge_ids)
            removed_edge_ids.extend(reward_apply.removed_edge_ids)
        next_active_quest_id = progression.next_active_quest_id

    if changed_edge_ids or changed_node_ids or removed_edge_ids:
        await repo.save_graph_changes(
            game_id,
            next_runtime.graph,
            changed_node_ids=sorted(set(changed_node_ids)),
            changed_edge_ids=sorted(set(changed_edge_ids)),
            removed_edge_ids=sorted(set(removed_edge_ids)),
        )
    if completed_quest_ids:
        next_progress = next_runtime.progress.model_copy(
            update={"active_quest_id": next_active_quest_id}
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
        completed_quest_ids=completed_quest_ids,
        affinity_cues=affinity_cues,
    )


def _visited_location_ids(runtime: GameRuntimeState) -> set[str]:
    player = runtime.graph.nodes.get(runtime.progress.player_id)
    if player is None:
        return set()
    raw = player.properties.get("visited_location_ids", [])
    if not isinstance(raw, list):
        return set()
    return {item for item in raw if isinstance(item, str)}


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
        result_texts=_roll_result_texts(resolved),
    )
    messages = [
        {
            "role": "system",
            "content": get_prompt("graph_narrate", resolved.runtime.progress.locale),
        },
        {"role": "user", "content": build_narration_brief(payload)},
    ]
    try:
        async with asyncio.timeout(_roll_narration_timeout_s()):
            async for part in llm.chat_stream(
                messages,
                think=False,
                agent="graph_narrate",
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


async def _build_roll_narration(
    llm: LLMClient | None,
    resolved: _ResolvedGraphRoll,
) -> GraphNarrationResult:
    if llm is None:
        return GraphNarrationResult()
    payload = build_roll_narration_payload(
        runtime=resolved.runtime,
        action=resolved.action,
        pending=resolved.pending,
        roll_entry=resolved.roll_entry,
        outcome=resolved.outcome,
        result_texts=_roll_result_texts(resolved),
    )
    messages = [
        {
            "role": "system",
            "content": get_prompt("graph_narrate", resolved.runtime.progress.locale),
        },
        {"role": "user", "content": build_narration_brief(payload)},
    ]
    try:
        result = await asyncio.wait_for(
            llm.chat(
                messages,
                think=False,
                agent="graph_narrate",
            ),
            timeout=_roll_narration_timeout_s(),
        )
    except (
        LLMUnavailable,
        OSError,
        TimeoutError,
        InternalServerError,
        APIConnectionError,
        RateLimitError,
    ):
        return GraphNarrationResult()
    answer = result.get("answer")
    if not isinstance(answer, str):
        return GraphNarrationResult()
    return parse_graph_narration_answer(answer)


async def _commit_roll_narration(
    repo: GraphRepo,
    game_id: str,
    resolved: _ResolvedGraphRoll,
    narration_result: GraphNarrationResult,
) -> GraphActionRequestResult:
    runtime = resolved.runtime
    log_entries: list[LogEntry] = []
    if narration_result.narration:
        text = _append_missing_completed_quest_text(
            resolved,
            _strip_repeated_preroll_text(
                resolved,
                _clean_roll_meta_phrase(narration_result.narration),
            ),
        )
        if resolved.outcome == "success":
            text = _ensure_roll_resolution_text(resolved, text)
        narration_result = narration_result.model_copy(
            update={"narration": text}
        )
    if narration_result.narration:
        narration_result = _with_system_roll_cues(resolved, narration_result)
        entry = gm_log_entry_from_narration(
            runtime.progress.next_log_id,
            narration_result,
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
        target=_action_target(resolved.action),
    )
    return executed_result(
        runtime,
        graph_to_front_state(runtime),
        outcome=resolved.outcome,
        suggestions=_roll_result_suggestions(runtime, resolved, narration_result),
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
    base_dc = _default_roll_dc()
    check = plan_roll_check(
        graph,
        player_properties=player_properties,
        player_id=player_id,
        action=action,
        base_dc=base_dc,
    )
    stat = check.stat
    label = stat_label(stat, locale)
    body = reason or _roll_body(action, locale)
    return {
        "id": f"roll_{secrets.token_hex(4)}",
        "kind": action.verb,
        "title": render("runtime.roll.title", locale, label=label),
        "body": body,
        "check_reason": body,
        "stat": stat,
        "stat_label": label,
        "required_roll": check.required_roll,
        "base_dc": base_dc,
        "effective_dc": check.effective_dc,
        "payload": build_pending_action_payload(action),
    }


def _with_system_roll_cues(
    resolved: _ResolvedGraphRoll,
    narration_result: GraphNarrationResult,
) -> GraphNarrationResult:
    if not resolved.affinity_cues:
        return narration_result
    return narration_result.model_copy(
        update={
            "ui_cues": [
                *resolved.affinity_cues,
                *narration_result.ui_cues,
            ][:3]
        }
    )


def _roll_body(action: Action, locale: str) -> str:
    if action.verb == "perceive":
        return render("runtime.roll.body.perceive", locale)
    if action.verb == "speak":
        return render("runtime.roll.body.speak", locale)
    if action.verb == "move":
        return render("runtime.roll.body.move", locale)
    return render("runtime.roll.body.default", locale)


def _apply_roll_quest_effect(
    runtime: GameRuntimeState,
    action: Action,
    *,
    roll_outcome: GraphResultOutcome,
) -> tuple[GameRuntimeState, GraphRuntimeDirty, list[str]]:
    dirty = GraphRuntimeDirty()
    if roll_outcome != "success":
        return runtime, dirty, []
    trigger = plan_roll_quest_trigger(
        runtime.graph,
        player_id=runtime.progress.player_id,
        action=action,
    )
    if trigger is None:
        return runtime, dirty, []

    trigger_type, target = trigger
    progress = plan_quest_progress_for_trigger(runtime.graph, trigger_type, target)
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


def _action_target(action: Action) -> str | None:
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
    resolved: _ResolvedGraphRoll,
    llm: LLMClient | None,
) -> GraphActionRequestResult:
    narration_result = await _build_roll_narration(llm, resolved)
    text = narration_result.narration or _roll_fallback_text(resolved)
    text = _clean_roll_meta_phrase(text)
    text = _strip_repeated_preroll_text(resolved, text)
    text = _append_missing_completed_quest_text(resolved, text)
    if outcome == "success":
        text = _ensure_roll_resolution_text(resolved, text)
    narration_result = narration_result.model_copy(update={"narration": text})
    narration_result = _with_system_roll_cues(resolved, narration_result)
    entry = gm_log_entry_from_narration(
        runtime.progress.next_log_id,
        narration_result,
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
    final = executed_result(
        next_runtime,
        graph_to_front_state(next_runtime),
        outcome=outcome,
    )
    return final.model_copy(
        update={
            "suggestions": _roll_result_suggestions(
                next_runtime,
                resolved,
                narration_result,
            )
        }
    )


def _is_narrative_roll_action(action: Action) -> bool:
    return action.verb in {"perceive", "speak"}


def _roll_result_suggestions(
    runtime: GameRuntimeState,
    resolved: _ResolvedGraphRoll,
    narration_result: GraphNarrationResult,
) -> list[GraphSuggestion]:
    if resolved.outcome == "failure" and resolved.action.verb != "speak":
        return []
    suggestions = filter_grounded_suggestions(runtime, narration_result.suggestions)
    if suggestions or resolved.outcome != "failure" or resolved.action.verb != "speak":
        return suggestions
    target_id = _action_target(resolved.action)
    target = runtime.graph.nodes.get(target_id or "")
    if target is None:
        return suggestions
    target_name = node_label(runtime.content, target)
    locale = runtime.progress.locale
    return filter_grounded_suggestions(
        runtime,
        [
            GraphSuggestion(
                label=render("runtime.roll.suggestion.retry_speak.label", locale),
                input_text=render(
                    "runtime.roll.suggestion.retry_speak.input",
                    locale,
                    target=target_name,
                ),
                intent="talk",
            )
        ],
    )


def _roll_resolution_key(action: Action, outcome: GraphResultOutcome) -> str:
    if action.verb == "perceive":
        return f"runtime.roll.resolve.perceive.{outcome}"
    if action.verb == "speak":
        return f"runtime.roll.resolve.speak.{outcome}"
    return f"runtime.roll.resolve.default.{outcome}"


def _roll_result_texts(resolved: _ResolvedGraphRoll) -> list[str]:
    result_texts = [
        render(
            "runtime.roll.result.success"
            if resolved.outcome == "success"
            else "runtime.roll.result.failure",
            resolved.runtime.progress.locale,
            check=resolved.roll_entry.check,
        )
    ]
    result_texts.append(_roll_resolution_text(resolved))
    result_texts.extend(_completed_quest_descriptions(resolved))
    return result_texts


def _roll_fallback_text(resolved: _ResolvedGraphRoll) -> str:
    descriptions = _completed_quest_descriptions(resolved)
    if descriptions and resolved.outcome == "success":
        return descriptions[0]
    return _roll_resolution_text(resolved)


def _ensure_roll_resolution_text(resolved: _ResolvedGraphRoll, text: str) -> str:
    resolution_text = _roll_resolution_text(resolved)
    if not resolution_text:
        return text
    normalized_resolution = _normalize_korean_sentence(resolution_text)
    normalized_text = _normalize_korean_sentence(text)
    if normalized_resolution and normalized_resolution in normalized_text:
        return text
    if not text.strip():
        return resolution_text
    return f"{resolution_text} {text.strip()}"


def _roll_resolution_text(resolved: _ResolvedGraphRoll) -> str:
    locale = resolved.runtime.progress.locale
    key = _roll_resolution_key(resolved.action, resolved.outcome)
    if resolved.action.verb != "speak":
        return render(key, locale)
    target_id = _action_target(resolved.action)
    target = resolved.runtime.graph.nodes.get(target_id) if target_id else None
    if target is None:
        return render("runtime.roll.resolve.default." + resolved.outcome, locale)
    target_name = node_label(resolved.runtime.content, target)
    return render(key, locale, target=target_name)


def _clean_roll_meta_phrase(text: str) -> str:
    return re.sub(
        _roll_meta_phrase_pattern(),
        "",
        text,
    ).strip()


def _strip_repeated_preroll_text(resolved: _ResolvedGraphRoll, text: str) -> str:
    preroll = resolved.pending.get("body")
    if not isinstance(preroll, str) or not preroll.strip() or not text.strip():
        return text

    body_sentences = _split_korean_sentences(preroll)
    if not body_sentences:
        return text
    out = _split_korean_sentences(text)
    removed = 0
    while out and _looks_like_preroll_repeat(out[0], body_sentences):
        out.pop(0)
        removed += 1
    if removed == 0 or not out:
        return text
    return " ".join(out).strip()


def _looks_like_preroll_repeat(sentence: str, body_sentences: list[str]) -> bool:
    normalized = _normalize_korean_sentence(sentence)
    if not normalized:
        return False
    for body in body_sentences:
        body_normalized = _normalize_korean_sentence(body)
        if not body_normalized:
            continue
        if normalized in body_normalized or body_normalized in normalized:
            return True
        if difflib.SequenceMatcher(None, normalized, body_normalized).ratio() >= 0.72:
            return True
    return False


def _split_korean_sentences(text: str) -> list[str]:
    parts = re.findall(r"[^.!?。！？]+[.!?。！？]?", text)
    return [part.strip() for part in parts if part.strip()]


def _normalize_korean_sentence(text: str) -> str:
    return re.sub(_non_korean_sentence_chars_pattern(), "", text).lower()


def _roll_meta_phrase_pattern() -> str:
    stats = "|".join(
        [
            _codepoint_text(0xBAB8, 0xB825),
            _codepoint_text(0xBBFC, 0xCCA9),
            _codepoint_text(0xC9C0, 0xB825),
            _codepoint_text(0xB9E4, 0xB825),
            _codepoint_text(0xCCB4, 0xB825),
            _codepoint_text(0xADFC, 0xB825),
        ]
    )
    check = _codepoint_text(0xD310, 0xC815)
    possessive = _codepoint_text(0xC758)
    success = _codepoint_text(0xC131, 0xACF5)
    failure = _codepoint_text(0xC2E4, 0xD328)
    by = _codepoint_text(0xC73C, 0xB85C)
    return rf"(?:(?:{stats})\s*)?{check}(?:{possessive})?\s*(?:{success}|{failure})(?:{by})?[,，]?\s*"


def _non_korean_sentence_chars_pattern() -> str:
    return f"[^0-9A-Za-z{chr(0xAC00)}-{chr(0xD7A3)}]+"


def _codepoint_text(*values: int) -> str:
    return "".join(chr(value) for value in values)


def _append_missing_completed_quest_text(
    resolved: _ResolvedGraphRoll,
    text: str,
) -> str:
    descriptions = _completed_quest_descriptions(resolved)
    if resolved.outcome != "success" or not descriptions:
        return text
    missing = [description for description in descriptions if description not in text]
    if not missing:
        return text
    if not text.strip():
        return "\n\n".join(missing)
    return f"{text.rstrip()}\n\n{missing[0]}"


def _completed_quest_descriptions(resolved: _ResolvedGraphRoll) -> list[str]:
    out: list[str] = []
    for quest_id in resolved.completed_quest_ids:
        quest = resolved.runtime.graph.nodes.get(quest_id)
        if quest is None or quest.type != "quest":
            continue
        description = node_text(resolved.runtime.content, quest, "description")
        if description:
            out.append(description)
    return out


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
