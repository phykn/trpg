import asyncio
from collections.abc import AsyncIterator

from openai import APIConnectionError, InternalServerError, RateLimitError

from src.db.repo import GraphRepo
from src.game.domain.action import Action
from src.game.domain.content import node_label
from src.game.domain.errors import LLMUnavailable
from src.game.domain.memory import LogEntry
from src.locale.render import render
from src.llm.calls.runner import get_prompt
from src.llm.client import LLMClient
from src.wire.graph.to_front import graph_to_front_state

from ...env import env_float
from ...narration.brief import build_narration_brief
from ...narration.context import build_roll_narration_payload
from ...narration.result import (
    GraphNarrationResult,
    gm_log_entry_from_narration,
    parse_graph_narration_answer,
    persist_graph_narration_result,
)
from ...narration.suggestions import GraphSuggestion, filter_grounded_suggestions
from ...request_result import GraphActionRequestResult, GraphResultOutcome, executed_result
from ...roll.pending import roll_action_target
from ...roll.text import (
    prepare_roll_narration_text,
    roll_fallback_text,
    roll_result_texts,
)
from ...state import GameRuntimeState
from .types import ResolvedGraphRoll


def roll_narration_timeout_s(default: float = 120.0) -> float:
    return env_float("LLM_TIMEOUT_S", default)


async def stream_roll_narration(
    llm: LLMClient | None,
    resolved: ResolvedGraphRoll,
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
        async with asyncio.timeout(roll_narration_timeout_s()):
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


async def build_roll_narration(
    llm: LLMClient | None,
    resolved: ResolvedGraphRoll,
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
            timeout=roll_narration_timeout_s(),
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


async def commit_roll_narration(
    repo: GraphRepo,
    game_id: str,
    resolved: ResolvedGraphRoll,
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
        narration_result = narration_result.model_copy(update={"narration": text})
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
        suggestions=roll_result_suggestions(runtime, resolved, narration_result),
    )


def _with_system_roll_cues(
    resolved: ResolvedGraphRoll,
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


async def finish_narrative_roll(
    repo: GraphRepo,
    game_id: str,
    runtime: GameRuntimeState,
    action: Action,
    *,
    outcome: GraphResultOutcome,
    resolved: ResolvedGraphRoll,
    llm: LLMClient | None,
) -> GraphActionRequestResult:
    narration_result = await build_roll_narration(llm, resolved)
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
            "suggestions": roll_result_suggestions(
                next_runtime,
                resolved,
                narration_result,
            )
        }
    )


def roll_result_suggestions(
    runtime: GameRuntimeState,
    resolved: ResolvedGraphRoll,
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
