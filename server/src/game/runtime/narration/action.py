import asyncio
import json
from collections.abc import AsyncIterator

from openai import APIConnectionError, InternalServerError, RateLimitError

from src.game.domain.action import Action
from src.game.domain.errors import LLMUnavailable
from src.llm.calls.runner import get_prompt
from src.llm.client import LLMClient
from src.llm.diag import llm_diag

from ..action.dispatch import GraphActionDispatchResult
from ..state import GameRuntimeState
from .context import build_action_narration_payload
from .result import GraphNarrationResult, parse_graph_narration_answer


async def build_graph_action_narration(
    llm: LLMClient | None,
    *,
    before: GameRuntimeState,
    after: GameRuntimeState,
    action: Action,
    dispatch: GraphActionDispatchResult,
    card_texts: list[str],
    timeout_s: float,
) -> GraphNarrationResult:
    messages = _graph_action_narration_messages(
        llm,
        before=before,
        after=after,
        action=action,
        dispatch=dispatch,
        card_texts=card_texts,
    )
    if messages is None:
        return GraphNarrationResult()
    agent = _graph_action_narration_agent(dispatch)
    llm_diag("llm:call", agent=agent)
    try:
        result = await asyncio.wait_for(
            llm.chat(
                messages,
                think=False,
                agent=agent,
                temperature=0.2,
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
        llm_diag("llm:fail", agent=agent, err=type(exc).__name__)
        return GraphNarrationResult()
    llm_diag("llm:done", agent=agent)
    answer = result.get("answer")
    if not isinstance(answer, str):
        return GraphNarrationResult()
    return parse_graph_narration_answer(answer)


async def stream_graph_action_narration(
    llm: LLMClient | None,
    *,
    before: GameRuntimeState,
    after: GameRuntimeState,
    action: Action,
    dispatch: GraphActionDispatchResult,
    card_texts: list[str],
    timeout_s: float,
) -> AsyncIterator[str]:
    messages = _graph_action_narration_messages(
        llm,
        before=before,
        after=after,
        action=action,
        dispatch=dispatch,
        card_texts=card_texts,
    )
    if messages is None or llm is None:
        return
    agent = _graph_action_narration_agent(dispatch)
    llm_diag("llm:call", agent=agent)
    try:
        async with asyncio.timeout(timeout_s):
            async for part in llm.chat_stream(
                messages,
                think=False,
                agent=agent,
                temperature=0.2,
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
        llm_diag("llm:fail", agent=agent, err=type(exc).__name__)
        return
    llm_diag("llm:done", agent=agent)


def _graph_action_narration_messages(
    llm: LLMClient | None,
    *,
    before: GameRuntimeState,
    after: GameRuntimeState,
    action: Action,
    dispatch: GraphActionDispatchResult,
    card_texts: list[str],
) -> list[dict[str, str]] | None:
    if llm is None or not _needs_graph_action_narration(
        before, after, action, dispatch
    ):
        return None
    prompt = _narration_user_prompt(before, after, action, dispatch, card_texts)
    if not prompt:
        return None
    agent = _graph_action_narration_agent(dispatch)
    return [
        {
            "role": "system",
            "content": get_prompt(agent, before.progress.locale),
        },
        {"role": "user", "content": prompt},
    ]


def _graph_action_narration_agent(dispatch: GraphActionDispatchResult) -> str:
    if dispatch.kind == "combat":
        return "combat_narrate"
    return "graph_narrate"


def _needs_graph_action_narration(
    before: GameRuntimeState,
    after: GameRuntimeState,
    action: Action,
    dispatch: GraphActionDispatchResult,
) -> bool:
    if dispatch.kind == "combat":
        if dispatch.outcome == "fled":
            return False
        return True
    if dispatch.kind in {"quest_accept", "quest_abandon"}:
        return True
    if action.verb == "move":
        return False
    return before.progress.active_quest_id != after.progress.active_quest_id


def _narration_user_prompt(
    before: GameRuntimeState,
    after: GameRuntimeState,
    action: Action,
    dispatch: GraphActionDispatchResult,
    card_texts: list[str],
) -> str:
    payload = build_action_narration_payload(
        before=before,
        after=after,
        action=action,
        dispatch=dispatch,
        card_texts=card_texts,
    )
    if payload["current_place"] is None:
        return ""
    return json.dumps(payload, ensure_ascii=False)
