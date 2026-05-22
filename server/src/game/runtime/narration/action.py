import asyncio
import json
from collections.abc import AsyncIterator

from openai import APIConnectionError, InternalServerError, RateLimitError

from src.game.domain.action import Action
from src.game.domain.errors import LLMUnavailable
from src.locale.render import render
from src.llm.calls.runner import get_prompt
from src.llm.client import LLMClient
from src.llm.diag import llm_diag

from ..action.dispatch import GraphActionDispatchResult
from ..env import graph_narration_temperature
from ..state import GameRuntimeState
from .context import build_action_narration_payload
from .result import GraphNarrationResult, parse_graph_narration_answer


def _narration_temperature(default: float = 1.0) -> float:
    return graph_narration_temperature(default)


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
    if llm is None:
        deterministic = _deterministic_graph_action_narration(before, dispatch)
        if deterministic is not None:
            return deterministic
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
    temperature = _narration_temperature()
    llm_diag("llm:call", agent=agent)
    try:
        result = await asyncio.wait_for(
            llm.chat(
                messages,
                think=False,
                agent=agent,
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
        llm_diag("llm:fail", agent=agent, err=type(exc).__name__)
        return _fallback_graph_action_narration(before)
    llm_diag("llm:done", agent=agent)
    answer = result.get("answer")
    if not isinstance(answer, str):
        return _fallback_graph_action_narration(before)
    return ensure_graph_action_narration(
        before=before,
        after=after,
        action=action,
        dispatch=dispatch,
        card_texts=card_texts,
        result=parse_graph_narration_answer(answer),
        llm_available=True,
    )


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
    if llm is None:
        deterministic = _deterministic_graph_action_narration(before, dispatch)
        if deterministic is not None:
            yield deterministic.narration
            return
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
    temperature = _narration_temperature()
    llm_diag("llm:call", agent=agent)
    try:
        async with asyncio.timeout(timeout_s):
            async for part in llm.chat_stream(
                messages,
                think=False,
                agent=agent,
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
        before, after, action, dispatch, card_texts
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
    card_texts: list[str],
) -> bool:
    if dispatch.kind == "combat":
        return True
    if len(card_texts) > 1:
        return True
    if dispatch.kind in {
        "quest_accept",
        "quest_abandon",
        "transfer",
        "trade_buy",
        "trade_sell",
        "use",
        "rest",
        "rest_encounter",
    }:
        return True
    if action.verb == "move":
        return _is_first_visit_move(before, action)
    return before.progress.active_quest_id != after.progress.active_quest_id


def ensure_graph_action_narration(
    *,
    before: GameRuntimeState,
    after: GameRuntimeState,
    action: Action,
    dispatch: GraphActionDispatchResult,
    card_texts: list[str],
    result: GraphNarrationResult,
    llm_available: bool,
) -> GraphNarrationResult:
    deterministic = _deterministic_graph_action_narration(before, dispatch)
    if deterministic is not None and not llm_available:
        return deterministic
    if result.narration:
        return _replace_repeated_graph_action_narration(before, dispatch, result)
    if not llm_available:
        return result
    if not _needs_graph_action_narration(before, after, action, dispatch, card_texts):
        return result
    return _fallback_graph_action_narration(before)


def _fallback_graph_action_narration(runtime: GameRuntimeState) -> GraphNarrationResult:
    return GraphNarrationResult(
        narration=render("runtime.input.quiet", runtime.progress.locale)
    )


def _deterministic_graph_action_narration(
    runtime: GameRuntimeState,
    dispatch: GraphActionDispatchResult,
) -> GraphNarrationResult | None:
    if dispatch.kind != "combat":
        return None
    if _combat_exchange_result(dispatch) != "failure":
        return None
    return GraphNarrationResult(
        narration=render(_combat_failure_fallback_key(dispatch), runtime.progress.locale)
    )


def _combat_exchange_result(dispatch: GraphActionDispatchResult) -> str:
    state = dispatch.runtime.progress.graph_combat_state
    if state is not None and state.last_roll is not None and state.last_dc is not None:
        return "success" if state.last_roll >= state.last_dc else "failure"
    if dispatch.outcome in {"victory", "escaped", "combat_stopped"}:
        return "success"
    if dispatch.outcome == "defeat":
        return "failure"
    for event in reversed(dispatch.combat_trace):
        if event.kind.endswith("_success") or event.kind in {
            "enemy_defeated",
            "combat_stopped",
        }:
            return "success"
        if event.kind.endswith("_failure") or event.kind == "player_defeated":
            return "failure"
    return "neutral"


def _combat_failure_fallback_key(dispatch: GraphActionDispatchResult) -> str:
    action = _latest_combat_action(dispatch)
    if action == "flee":
        return "runtime.narration.combat_failure.flee"
    if action == "talk":
        return "runtime.narration.combat_failure.talk"
    if action == "defend":
        return "runtime.narration.combat_failure.defend"
    return "runtime.narration.combat_failure.attack"


def _latest_combat_action(dispatch: GraphActionDispatchResult) -> str | None:
    state = dispatch.runtime.progress.graph_combat_state
    if state is not None and state.last_action:
        return state.last_action
    for event in reversed(dispatch.combat_trace):
        kind = event.kind
        for action in ("attack", "flee", "talk", "defend"):
            if action in kind:
                return action
    return None


def _replace_repeated_graph_action_narration(
    runtime: GameRuntimeState,
    dispatch: GraphActionDispatchResult,
    result: GraphNarrationResult,
) -> GraphNarrationResult:
    text = result.narration.strip()
    if not text:
        return result
    recent = {
        entry.text.strip()
        for entry in runtime.log_entries[-6:]
        if entry.kind == "gm" and entry.text.strip()
    }
    if text not in recent:
        return result
    key = _repeat_fallback_key(dispatch)
    return result.model_copy(
        update={"narration": render(key, runtime.progress.locale)}
    )


def _repeat_fallback_key(dispatch: GraphActionDispatchResult) -> str:
    if dispatch.kind != "combat":
        return "runtime.narration.repeat.neutral"
    state = dispatch.runtime.progress.graph_combat_state
    if state is not None and state.last_roll is not None and state.last_dc is not None:
        if state.last_roll >= state.last_dc:
            return "runtime.narration.repeat.combat_success"
        return "runtime.narration.repeat.combat_failure"
    if dispatch.outcome == "victory":
        return "runtime.narration.repeat.combat_success"
    if dispatch.outcome == "defeat":
        return "runtime.narration.repeat.combat_failure"
    return "runtime.narration.repeat.combat_neutral"


def _is_first_visit_move(runtime: GameRuntimeState, action: Action) -> bool:
    destination_id = _single(action.to) or _single(action.what)
    if destination_id is None:
        return False
    player = runtime.graph.nodes.get(runtime.progress.player_id)
    if player is None:
        return False
    visited = player.properties.get("visited_location_ids")
    if not isinstance(visited, list):
        return True
    return destination_id not in {item for item in visited if isinstance(item, str)}


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


def _single(value: object) -> str | None:
    if isinstance(value, str):
        return value
    if isinstance(value, list) and value and isinstance(value[0], str):
        return value[0]
    return None
