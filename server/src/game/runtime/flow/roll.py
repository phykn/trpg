import asyncio
import random
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any

from openai import APIConnectionError, InternalServerError, RateLimitError

from src.db.repo import GraphRepo, ScenarioRepo
from src.game.domain.action import Action
from src.game.domain.content import node_label
from src.game.domain.errors import LLMUnavailable
from src.game.domain.memory import (
    BonusItem,
    GMLogEntry,
    LogEntry,
    NarrationCue,
    RollLogEntry,
)
from src.game.rules.dc import compute_grade
from src.locale.labels import roll_dice_label
from src.locale.render import render
from src.llm.calls.runner import get_prompt
from src.llm.client import LLMClient
from src.llm.diag import engine_diag, set_diag_context
from src.wire.graph.to_front import graph_to_front_state

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
from ..pending_action import load_pending_action
from ..request_result import (
    GraphActionRequestResult,
    GraphResultOutcome,
    executed_result,
    roll_required_result,
)
from ..roll.effects import apply_roll_effects
from ..roll.pending import build_pending_roll, roll_action_target
from ..roll.text import (
    prepare_roll_narration_text,
    roll_fallback_text,
    roll_resolution_text,
    roll_result_texts,
)
from ..state import GameRuntimeState
from ..env import env_float
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
        roll_action_target(action),
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
    resolution_text = roll_resolution_text(resolved)
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
            narration=roll_fallback_text(resolved)
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
    roll_effects = apply_roll_effects(
        next_runtime,
        action,
        grade=grade,
        outcome=outcome,
    )
    next_runtime = roll_effects.runtime

    if (
        roll_effects.changed_edge_ids
        or roll_effects.changed_node_ids
        or roll_effects.removed_edge_ids
    ):
        await repo.save_graph_changes(
            game_id,
            next_runtime.graph,
            changed_node_ids=sorted(set(roll_effects.changed_node_ids)),
            changed_edge_ids=sorted(set(roll_effects.changed_edge_ids)),
            removed_edge_ids=sorted(set(roll_effects.removed_edge_ids)),
        )
    if roll_effects.completed_quest_ids:
        next_progress = next_runtime.progress.model_copy(
            update={"active_quest_id": roll_effects.next_active_quest_id}
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
        completed_quest_ids=roll_effects.completed_quest_ids,
        affinity_cues=roll_effects.affinity_cues,
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
        result_texts=roll_result_texts(resolved),
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
        result_texts=roll_result_texts(resolved),
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
        text = prepare_roll_narration_text(
            resolved,
            narration_result.narration,
            ensure_resolution=resolved.outcome == "success",
        )
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
        target=roll_action_target(resolved.action),
    )
    return executed_result(
        runtime,
        graph_to_front_state(runtime),
        outcome=resolved.outcome,
        suggestions=_roll_result_suggestions(runtime, resolved, narration_result),
    )


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
    text = prepare_roll_narration_text(
        resolved,
        narration_result.narration or roll_fallback_text(resolved),
        ensure_resolution=outcome == "success",
    )
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
    target_id = roll_action_target(resolved.action)
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
