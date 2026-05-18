import asyncio
import json
import os
from collections.abc import AsyncIterator

from openai import APIConnectionError, InternalServerError, RateLimitError

from src.game.domain.action import Action
from src.game.domain.errors import LLMUnavailable
from src.game.domain.graph import GraphNode
from src.llm.calls.runner import get_prompt
from src.llm.client import LLMClient
from src.llm.diag import llm_diag

from ..state import GameRuntimeState
from .context import build_input_narration_payload
from .result import GraphNarrationResult, parse_graph_narration_answer


def _narration_temperature(default: float = 1.0) -> float:
    return float(os.environ.get("LLM_GRAPH_NARRATE_TEMPERATURE") or str(default))


async def generate_graph_input_narration(
    client: LLMClient,
    runtime: GameRuntimeState,
    player_input: str,
    action: Action,
    subject_id: str | None,
    *,
    timeout_s: float,
) -> GraphNarrationResult:
    messages = _graph_input_narration_messages(
        runtime,
        player_input,
        action,
        subject_id,
    )
    temperature = _narration_temperature()
    try:
        llm_diag("llm:call", agent="graph_narrate")
        result = await asyncio.wait_for(
            client.chat(
                messages,
                think=False,
                agent="graph_narrate",
                temperature=temperature,
            ),
            timeout=timeout_s,
        )
    except (
        LLMUnavailable,
        OSError,
        TimeoutError,
        InternalServerError,
        APIConnectionError,
        RateLimitError,
    ) as exc:
        llm_diag("llm:fail", agent="graph_narrate", err=type(exc).__name__)
        return GraphNarrationResult()
    llm_diag("llm:done", agent="graph_narrate")
    answer = result.get("answer")
    if not isinstance(answer, str):
        return GraphNarrationResult()
    return parse_graph_narration_answer(answer)


async def generate_graph_input_rejection_narration(
    client: LLMClient,
    runtime: GameRuntimeState,
    player_input: str,
    action: Action,
    public_reason: str,
    *,
    timeout_s: float,
) -> GraphNarrationResult:
    messages = _graph_input_rejection_narration_messages(
        runtime,
        player_input,
        action,
        public_reason,
    )
    temperature = _narration_temperature()
    try:
        llm_diag("llm:call", agent="graph_narrate")
        result = await asyncio.wait_for(
            client.chat(
                messages,
                think=False,
                agent="graph_narrate",
                temperature=temperature,
            ),
            timeout=timeout_s,
        )
    except (
        LLMUnavailable,
        OSError,
        TimeoutError,
        InternalServerError,
        APIConnectionError,
        RateLimitError,
    ) as exc:
        llm_diag("llm:fail", agent="graph_narrate", err=type(exc).__name__)
        return GraphNarrationResult()
    llm_diag("llm:done", agent="graph_narrate")
    answer = result.get("answer")
    if not isinstance(answer, str):
        return GraphNarrationResult()
    return parse_graph_narration_answer(answer)


async def stream_graph_input_narration(
    client: LLMClient,
    runtime: GameRuntimeState,
    player_input: str,
    action: Action,
    subject_id: str | None,
    *,
    timeout_s: float,
) -> AsyncIterator[str]:
    messages = _graph_input_narration_messages(
        runtime,
        player_input,
        action,
        subject_id,
    )
    temperature = _narration_temperature()
    try:
        llm_diag("llm:call", agent="graph_narrate")
        async with asyncio.timeout(timeout_s):
            async for part in client.chat_stream(
                messages,
                think=False,
                agent="graph_narrate",
                temperature=temperature,
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
    ) as exc:
        llm_diag("llm:fail", agent="graph_narrate", err=type(exc).__name__)
        return
    llm_diag("llm:done", agent="graph_narrate")


async def stream_graph_input_rejection_narration(
    client: LLMClient,
    runtime: GameRuntimeState,
    player_input: str,
    action: Action,
    public_reason: str,
    *,
    timeout_s: float,
) -> AsyncIterator[str]:
    messages = _graph_input_rejection_narration_messages(
        runtime,
        player_input,
        action,
        public_reason,
    )
    temperature = _narration_temperature()
    try:
        llm_diag("llm:call", agent="graph_narrate")
        async with asyncio.timeout(timeout_s):
            async for part in client.chat_stream(
                messages,
                think=False,
                agent="graph_narrate",
                temperature=temperature,
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
    ) as exc:
        llm_diag("llm:fail", agent="graph_narrate", err=type(exc).__name__)
        return
    llm_diag("llm:done", agent="graph_narrate")


async def stream_graph_preroll_narration(
    client: LLMClient,
    runtime: GameRuntimeState,
    player_input: str | None,
    action: Action,
    pending_roll: dict[str, object],
    *,
    timeout_s: float,
) -> AsyncIterator[str]:
    messages = _graph_preroll_narration_messages(
        runtime,
        player_input,
        action,
        pending_roll,
    )
    temperature = _narration_temperature()
    try:
        llm_diag("llm:call", agent="graph_narrate")
        async with asyncio.timeout(timeout_s):
            async for part in client.chat_stream(
                messages,
                think=False,
                agent="graph_narrate",
                temperature=temperature,
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
    ) as exc:
        llm_diag("llm:fail", agent="graph_narrate", err=type(exc).__name__)
        return
    llm_diag("llm:done", agent="graph_narrate")


def _graph_input_narration_messages(
    runtime: GameRuntimeState,
    player_input: str,
    action: Action,
    subject_id: str | None,
) -> list[dict[str, str]]:
    subject = runtime.graph.nodes.get(subject_id or "")
    payload = build_input_narration_payload(
        runtime=runtime,
        player_input=player_input,
        action=action,
        dialogue_target=subject if subject_id is not None else None,
    )
    return [
        {
            "role": "system",
            "content": get_prompt("graph_narrate", runtime.progress.locale),
        },
        {
            "role": "user",
            "content": json.dumps(payload, ensure_ascii=False),
        },
    ]


def _graph_preroll_narration_messages(
    runtime: GameRuntimeState,
    player_input: str | None,
    action: Action,
    pending_roll: dict[str, object],
) -> list[dict[str, str]]:
    target = _action_target_node(runtime, action)
    payload = build_input_narration_payload(
        runtime=runtime,
        player_input=player_input or "",
        action=action,
        dialogue_target=target,
    )
    payload["player_input"] = player_input
    body = pending_roll.get("body")
    title = pending_roll.get("title")
    payload["current_event"] = {
        "kind": "roll_prompt",
        "outcome": "pending_roll",
        "action": action.model_dump(mode="json", by_alias=True, exclude_none=True),
        "check_reason": body if isinstance(body, str) else "",
        "resolved_results": [title, body],
    }
    payload["result_cards"] = [
        {"text": body if isinstance(body, str) else ""},
    ]
    return [
        {
            "role": "system",
            "content": get_prompt("graph_narrate", runtime.progress.locale),
        },
        {
            "role": "user",
            "content": json.dumps(payload, ensure_ascii=False),
        },
    ]


def _graph_input_rejection_narration_messages(
    runtime: GameRuntimeState,
    player_input: str,
    action: Action,
    public_reason: str,
) -> list[dict[str, str]]:
    target = _action_target_node(runtime, action)
    payload = build_input_narration_payload(
        runtime=runtime,
        player_input=player_input,
        action=action,
        dialogue_target=target,
    )
    payload["current_event"] = {
        "kind": "action_rejected",
        "outcome": "action_rejected",
        "action": action.model_dump(mode="json", by_alias=True, exclude_none=True),
        "target": payload["target_view"],
        "resolved_results": [public_reason],
    }
    payload["result_cards"] = [{"text": public_reason}]
    return [
        {
            "role": "system",
            "content": get_prompt("graph_narrate", runtime.progress.locale),
        },
        {
            "role": "user",
            "content": json.dumps(payload, ensure_ascii=False),
        },
    ]


def _action_target_node(
    runtime: GameRuntimeState,
    action: Action,
) -> GraphNode | None:
    target = _single(action.what) or _single(action.to) or _single(action.with_)
    if target is None:
        return None
    return runtime.graph.nodes.get(target)


def _single(value: object) -> str | None:
    if isinstance(value, str):
        return value
    if isinstance(value, list) and value and isinstance(value[0], str):
        return value[0]
    return None
