import asyncio
import json
from collections.abc import AsyncIterator

from openai import APIConnectionError, InternalServerError, RateLimitError
from pydantic import BaseModel, ConfigDict, Field

from src.db.repo import GraphRepo, ScenarioRepo
from src.game.domain.action import Action
from src.game.domain.content import merge_content, node_label, node_text
from src.game.domain.errors import LLMUnavailable
from src.game.domain.graph import GraphNode
from src.game.domain.memory import GMLogEntry
from src.game.engines.graph_quest_generation import plan_missing_quest_offer
from src.llm.calls._runner import get_prompt
from src.llm.client import LLMClient
from src.llm.diag import engine_diag, llm_diag, set_diag_context
from src.locale.render import render
from src.wire.graph_to_front import GraphFrontStatePayload, graph_to_front_state

from .apply import apply_runtime_graph_changes
from .dispatch import (
    GraphActionDispatchError,
    GraphActionDispatchResult,
    dispatch_graph_action,
)
from .cards import build_graph_action_card, build_graph_quest_offer_card
from .load import load_runtime_state
from .narration_context import build_action_narration_payload
from .narration_result import (
    GraphNarrationResult,
    VisibleNarrationStream,
    parse_graph_narration_answer,
    persist_graph_narration_result,
)
from .state import GameRuntimeState
from .suggestions import GraphSuggestionValue


class GraphActionTurnError(ValueError):
    pass


class GraphActionTurnResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    runtime: GameRuntimeState
    dispatch: GraphActionDispatchResult
    front_state: GraphFrontStatePayload
    suggestions: list[GraphSuggestionValue] = Field(default_factory=list)


_GRAPH_ACTION_NARRATION_TIMEOUT_SECONDS = 30.0


async def run_graph_action_turn(
    repo: GraphRepo,
    game_id: str,
    action: Action,
    *,
    llm: LLMClient | None = None,
    scenario_repo: ScenarioRepo | None = None,
) -> GraphActionTurnResult:
    runtime = await load_runtime_state(repo, game_id, scenario_repo)
    set_diag_context(game_id, runtime.progress.turn_count)
    return await run_graph_action_turn_from_runtime(
        repo,
        game_id,
        runtime,
        action,
        llm=llm,
    )


async def run_graph_action_turn_from_runtime(
    repo: GraphRepo,
    game_id: str,
    runtime: GameRuntimeState,
    action: Action,
    *,
    llm: LLMClient | None = None,
) -> GraphActionTurnResult:
    set_diag_context(game_id, runtime.progress.turn_count)
    engine_diag("turn:start", action=action.verb)
    try:
        dispatch = dispatch_graph_action(runtime, action)
    except GraphActionDispatchError as exc:
        engine_diag("dispatch:fail", action=action.verb, err=type(exc).__name__)
        raise GraphActionTurnError(str(exc)) from exc
    engine_diag(
        "dispatch:done",
        kind=dispatch.kind,
        applied=dispatch.applied,
        outcome=dispatch.outcome,
    )

    next_runtime = dispatch.runtime
    changed_node_ids = set(dispatch.changed_node_ids)
    changed_edge_ids = set(dispatch.changed_edge_ids)
    removed_edge_ids = set(dispatch.removed_edge_ids)
    offer_quest_id: str | None = None
    if next_runtime.progress.graph_combat_state is None:
        offer = plan_missing_quest_offer(
            next_runtime.graph,
            next_runtime.progress.player_id,
            next_runtime.progress.locale,
        )
        if offer is not None:
            offer_apply = apply_runtime_graph_changes(
                next_runtime,
                offer.changes,
            )
            next_runtime = offer_apply.runtime
            changed_node_ids.update(offer_apply.changed_node_ids)
            changed_edge_ids.update(offer_apply.changed_edge_ids)
            removed_edge_ids.update(offer_apply.removed_edge_ids)
            runtime_content = merge_content(
                next_runtime.progress.runtime_content,
                offer.content,
            )
            next_runtime = next_runtime.model_copy(
                update={
                    "content": merge_content(next_runtime.content, offer.content),
                    "progress": next_runtime.progress.model_copy(
                        update={"runtime_content": runtime_content}
                    ),
                }
            )
            offer_quest_id = offer.quest_id
            engine_diag("quest:offer", quest=offer_quest_id)
    card = build_graph_action_card(runtime, next_runtime, action, dispatch)
    cards = [card]
    if offer_quest_id is not None:
        cards.append(
            build_graph_quest_offer_card(
                next_runtime,
                offer_quest_id,
                card.id + 1,
            )
        )
    narration_result = await _build_graph_action_narration(
        llm,
        before=runtime,
        after=next_runtime,
        action=action,
        dispatch=dispatch,
        card_texts=[card.text for card in cards],
    )
    narration = narration_result.narration
    log_entries = [*cards]
    if narration:
        log_entries.append(
            GMLogEntry(
                id=card.id + len(cards),
                kind="gm",
                text=narration,
            )
        )

    next_progress = next_runtime.progress.model_copy(
        update={"next_log_id": card.id + len(log_entries)}
    )
    next_runtime = next_runtime.model_copy(
        update={
            "progress": next_progress,
            "log_entries": [*next_runtime.log_entries, *log_entries],
        }
    )
    await repo.save_graph_changes(
        game_id,
        next_runtime.graph,
        changed_node_ids=sorted(changed_node_ids),
        changed_edge_ids=sorted(changed_edge_ids),
        removed_edge_ids=sorted(removed_edge_ids),
    )
    await repo.append_log_entries(game_id, log_entries)
    await repo.save_progress(next_runtime.progress)
    next_runtime = await persist_graph_narration_result(
        repo,
        next_runtime,
        narration_result,
        target_id=_action_target_id(action),
    )
    engine_diag(
        "turn:done",
        status="executed",
        logs=len(log_entries),
        next_turn=next_runtime.progress.turn_count,
    )
    return GraphActionTurnResult(
        runtime=next_runtime,
        dispatch=dispatch,
        front_state=graph_to_front_state(next_runtime),
        suggestions=narration_result.suggestions,
    )


async def run_graph_action_turn_from_runtime_stream(
    repo: GraphRepo,
    game_id: str,
    runtime: GameRuntimeState,
    action: Action,
    *,
    llm: LLMClient | None = None,
) -> AsyncIterator[dict[str, object]]:
    set_diag_context(game_id, runtime.progress.turn_count)
    engine_diag("turn:start", action=action.verb)
    try:
        dispatch = dispatch_graph_action(runtime, action)
    except GraphActionDispatchError as exc:
        engine_diag("dispatch:fail", action=action.verb, err=type(exc).__name__)
        raise GraphActionTurnError(str(exc)) from exc
    engine_diag(
        "dispatch:done",
        kind=dispatch.kind,
        applied=dispatch.applied,
        outcome=dispatch.outcome,
    )

    next_runtime = dispatch.runtime
    changed_node_ids = set(dispatch.changed_node_ids)
    changed_edge_ids = set(dispatch.changed_edge_ids)
    removed_edge_ids = set(dispatch.removed_edge_ids)
    offer_quest_id: str | None = None
    if next_runtime.progress.graph_combat_state is None:
        offer = plan_missing_quest_offer(
            next_runtime.graph,
            next_runtime.progress.player_id,
            next_runtime.progress.locale,
        )
        if offer is not None:
            offer_apply = apply_runtime_graph_changes(
                next_runtime,
                offer.changes,
            )
            next_runtime = offer_apply.runtime
            changed_node_ids.update(offer_apply.changed_node_ids)
            changed_edge_ids.update(offer_apply.changed_edge_ids)
            removed_edge_ids.update(offer_apply.removed_edge_ids)
            runtime_content = merge_content(
                next_runtime.progress.runtime_content,
                offer.content,
            )
            next_runtime = next_runtime.model_copy(
                update={
                    "content": merge_content(next_runtime.content, offer.content),
                    "progress": next_runtime.progress.model_copy(
                        update={"runtime_content": runtime_content}
                    ),
                }
            )
            offer_quest_id = offer.quest_id
            engine_diag("quest:offer", quest=offer_quest_id)
    card = build_graph_action_card(runtime, next_runtime, action, dispatch)
    cards = [card]
    if offer_quest_id is not None:
        cards.append(
            build_graph_quest_offer_card(
                next_runtime,
                offer_quest_id,
                card.id + 1,
            )
        )
    stream = VisibleNarrationStream()
    async for chunk in _stream_graph_action_narration(
        llm,
        before=runtime,
        after=next_runtime,
        action=action,
        dispatch=dispatch,
        card_texts=[card.text for card in cards],
    ):
        for visible in stream.push(chunk):
            yield {"type": "delta", "text": visible}
    for visible in stream.finish():
        yield {"type": "delta", "text": visible}
    narration_result = parse_graph_narration_answer(
        _clean_narration(stream.answer(), recent_texts=_recent_gm_texts(runtime))
    )
    narration = narration_result.narration
    log_entries = [*cards]
    if narration:
        log_entries.append(
            GMLogEntry(
                id=card.id + len(cards),
                kind="gm",
                text=narration,
            )
        )

    next_progress = next_runtime.progress.model_copy(
        update={"next_log_id": card.id + len(log_entries)}
    )
    next_runtime = next_runtime.model_copy(
        update={
            "progress": next_progress,
            "log_entries": [*next_runtime.log_entries, *log_entries],
        }
    )
    await repo.save_graph_changes(
        game_id,
        next_runtime.graph,
        changed_node_ids=sorted(changed_node_ids),
        changed_edge_ids=sorted(changed_edge_ids),
        removed_edge_ids=sorted(removed_edge_ids),
    )
    await repo.append_log_entries(game_id, log_entries)
    await repo.save_progress(next_runtime.progress)
    next_runtime = await persist_graph_narration_result(
        repo,
        next_runtime,
        narration_result,
        target_id=_action_target_id(action),
    )
    engine_diag(
        "turn:done",
        status="executed",
        logs=len(log_entries),
        next_turn=next_runtime.progress.turn_count,
    )
    yield {
        "type": "final",
        "result": GraphActionTurnResult(
            runtime=next_runtime,
            dispatch=dispatch,
            front_state=graph_to_front_state(next_runtime),
            suggestions=narration_result.suggestions,
        ),
    }


async def _build_graph_action_narration(
    llm: LLMClient | None,
    *,
    before: GameRuntimeState,
    after: GameRuntimeState,
    action: Action,
    dispatch: GraphActionDispatchResult,
    card_texts: list[str],
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
    llm_diag("llm:call", agent="graph_narrate")
    try:
        result = await asyncio.wait_for(
            llm.chat(
                messages,
                think=False,
                agent="graph_narrate",
                temperature=0.2,
            ),
            timeout=_GRAPH_ACTION_NARRATION_TIMEOUT_SECONDS,
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
    return parse_graph_narration_answer(
        _clean_narration(answer, recent_texts=_recent_gm_texts(before))
    )


async def _stream_graph_action_narration(
    llm: LLMClient | None,
    *,
    before: GameRuntimeState,
    after: GameRuntimeState,
    action: Action,
    dispatch: GraphActionDispatchResult,
    card_texts: list[str],
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
    llm_diag("llm:call", agent="graph_narrate")
    try:
        async with asyncio.timeout(_GRAPH_ACTION_NARRATION_TIMEOUT_SECONDS):
            async for part in llm.chat_stream(
                messages,
                think=False,
                agent="graph_narrate",
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
        llm_diag("llm:fail", agent="graph_narrate", err=type(exc).__name__)
        return
    llm_diag("llm:done", agent="graph_narrate")


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
    return [
        {
            "role": "system",
            "content": get_prompt("graph_narrate", before.progress.locale),
        },
        {"role": "user", "content": prompt},
    ]


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


def _clean_narration(text: str, *, recent_texts=()) -> str:
    return text


def _recent_gm_texts(runtime: GameRuntimeState) -> list[str]:
    return [
        entry.text
        for entry in runtime.log_entries[-4:]
        if getattr(entry, "kind", None) == "gm" and hasattr(entry, "text")
    ]


def _action_target_id(action: Action) -> str | None:
    for value in (action.what, action.to):
        if isinstance(value, str):
            return value
        if isinstance(value, list) and value and isinstance(value[0], str):
            return value[0]
    return None


def _node_name(runtime: GameRuntimeState, node: GraphNode | None) -> str:
    if node is None:
        return render("runtime.none", runtime.progress.locale)
    return node_label(runtime.content, node)


def _node_description_value(
    runtime: GameRuntimeState, node: GraphNode | None
) -> str | None:
    if node is None:
        return None
    return node_text(runtime.content, node, "description")
