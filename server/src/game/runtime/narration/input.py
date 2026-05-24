import asyncio
from collections.abc import AsyncIterator

from openai import APIConnectionError, InternalServerError, RateLimitError

from src.game.domain.action import Action
from src.game.domain.errors import LLMUnavailable
from src.game.domain.graph import GraphNode
from src.llm.calls.runner import get_prompt
from src.llm.client import LLMClient
from src.llm.diag import llm_diag

from ..state import GameRuntimeState
from ..action_refs import first_ref
from .brief import build_narration_brief
from .context import (
    build_input_narration_payload,
    narration_action_payload,
    update_compact_narration_event,
)
from .result import GraphNarrationResult, parse_graph_narration_answer


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
    try:
        llm_diag("llm:call", agent="graph_narrate")
        result = await asyncio.wait_for(
            client.chat(
                messages,
                think=False,
                agent="graph_narrate",
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
    try:
        llm_diag("llm:call", agent="graph_narrate")
        result = await asyncio.wait_for(
            client.chat(
                messages,
                think=False,
                agent="graph_narrate",
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
    try:
        llm_diag("llm:call", agent="graph_narrate")
        async with asyncio.timeout(timeout_s):
            async for part in client.chat_stream(
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
    try:
        llm_diag("llm:call", agent="graph_narrate")
        async with asyncio.timeout(timeout_s):
            async for part in client.chat_stream(
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
    try:
        llm_diag("llm:call", agent="graph_narrate")
        async with asyncio.timeout(timeout_s):
            async for part in client.chat_stream(
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
            "content": build_narration_brief(payload),
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
    body = pending_roll.get("body")
    title = pending_roll.get("title")
    update_compact_narration_event(
        payload,
        {
            "kind": "roll_prompt",
            "outcome": "pending_roll",
            "action": narration_action_payload(action),
            "check_reason": body if isinstance(body, str) else "",
            "resolved_results": [title, body],
        },
        player_input=player_input,
        result_cards=[{"text": body if isinstance(body, str) else ""}],
    )
    return [
        {
            "role": "system",
            "content": get_prompt("graph_narrate", runtime.progress.locale),
        },
        {
            "role": "user",
            "content": build_narration_brief(payload),
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
    scene_state = payload.get("scene_state")
    target_view = scene_state.get("target_view") if isinstance(scene_state, dict) else None
    update_compact_narration_event(
        payload,
        {
            "kind": "action_rejected",
            "outcome": "action_rejected",
            "action": narration_action_payload(action),
            "target": target_view,
            "resolved_results": [public_reason],
        },
        player_input=player_input,
        result_cards=[{"text": public_reason}],
    )
    return [
        {
            "role": "system",
            "content": get_prompt("graph_narrate", runtime.progress.locale),
        },
        {
            "role": "user",
            "content": build_narration_brief(payload),
        },
    ]


def _action_target_node(
    runtime: GameRuntimeState,
    action: Action,
) -> GraphNode | None:
    target = first_ref(action.what) or first_ref(action.to) or first_ref(action.with_)
    if target is None:
        return None
    return runtime.graph.nodes.get(target)
