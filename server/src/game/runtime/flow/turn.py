import os
from collections.abc import AsyncIterator
from dataclasses import dataclass

from pydantic import BaseModel, ConfigDict, Field

from src.db.repo import GraphRepo, ScenarioRepo
from src.game.domain.action import Action
from src.game.domain.content import merge_content
from src.game.domain.memory import GMLogEntry, LogEntry
from src.game.engines.graph.quest_generation import plan_missing_quest_offer
from src.llm.client import LLMClient
from src.llm.diag import engine_diag, set_diag_context
from src.wire.graph.to_front import GraphFrontStatePayload, graph_to_front_state

from ..action.apply import GraphRuntimeDirty, apply_runtime_graph_changes
from ..action.dispatch import (
    GraphActionDispatchError,
    GraphActionDispatchResult,
    dispatch_graph_action,
)
from ..narration.action import (
    build_graph_action_narration,
    stream_graph_action_narration,
)
from ..narration.cards import build_graph_action_card, build_graph_quest_offer_card
from ..load import load_runtime_state
from ..narration.result import (
    GraphNarrationResult,
    VisibleNarrationStream,
    parse_graph_narration_answer,
    persist_graph_narration_result,
)
from ..request_result import executed_result, outcome_from_dispatch
from ..state import GameRuntimeState
from ..narration.suggestions import GraphSuggestion


class GraphActionTurnError(ValueError):
    pass


class GraphActionTurnResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    runtime: GameRuntimeState
    dispatch: GraphActionDispatchResult
    front_state: GraphFrontStatePayload
    suggestions: list[GraphSuggestion] = Field(default_factory=list)


@dataclass
class _PreparedGraphActionTurn:
    before: GameRuntimeState
    after: GameRuntimeState
    action: Action
    dispatch: GraphActionDispatchResult
    dirty: GraphRuntimeDirty
    cards: list[LogEntry]


def _action_narration_timeout_s(default: float = 30.0) -> float:
    return float(os.environ.get("GRAPH_ACTION_NARRATION_TIMEOUT_S") or str(default))


# Public flow


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
    prepared = _prepare_graph_action_turn(game_id, runtime, action)
    result = await _commit_graph_action_result(repo, game_id, prepared)
    narration_result = await build_graph_action_narration(
        llm,
        before=prepared.before,
        after=prepared.after,
        action=prepared.action,
        dispatch=prepared.dispatch,
        card_texts=[card.text for card in prepared.cards],
        timeout_s=_action_narration_timeout_s(),
    )
    return await _commit_graph_action_narration(
        repo,
        game_id,
        prepared,
        result,
        narration_result,
    )


async def run_graph_action_turn_from_runtime_stream(
    repo: GraphRepo,
    game_id: str,
    runtime: GameRuntimeState,
    action: Action,
    *,
    llm: LLMClient | None = None,
) -> AsyncIterator[dict[str, object]]:
    prepared = _prepare_graph_action_turn(game_id, runtime, action)
    result = await _commit_graph_action_result(repo, game_id, prepared)
    outcome = outcome_from_dispatch(prepared.dispatch)
    yield {
        "type": "result",
        "result": executed_result(
            result.runtime,
            result.front_state,
            dispatch=prepared.dispatch,
            outcome=outcome,
        ),
    }
    stream = VisibleNarrationStream()
    async for chunk in stream_graph_action_narration(
        llm,
        before=prepared.before,
        after=prepared.after,
        action=prepared.action,
        dispatch=prepared.dispatch,
        card_texts=[card.text for card in prepared.cards],
        timeout_s=_action_narration_timeout_s(),
    ):
        for visible in stream.push(chunk):
            yield {"type": "narration_delta", "text": visible}
    for visible in stream.finish():
        yield {"type": "narration_delta", "text": visible}
    narration_result = parse_graph_narration_answer(stream.answer())
    final = await _commit_graph_action_narration(
        repo,
        game_id,
        prepared,
        result,
        narration_result,
    )
    yield {
        "type": "final",
        "result": executed_result(
            final.runtime,
            final.front_state,
            dispatch=prepared.dispatch,
            outcome=outcome,
            suggestions=final.suggestions,
        ),
    }


# Action preparation


def _prepare_graph_action_turn(
    game_id: str,
    runtime: GameRuntimeState,
    action: Action,
) -> _PreparedGraphActionTurn:
    set_diag_context(game_id, runtime.progress.turn_count)
    engine_diag("turn:start", action=action.verb)
    try:
        dispatch = dispatch_graph_action(runtime, action)
    except GraphActionDispatchError as exc:
        engine_diag(
            "dispatch:fail",
            action=action.verb,
            err=type(exc).__name__,
            reason=str(exc),
        )
        raise GraphActionTurnError(str(exc)) from exc
    engine_diag(
        "dispatch:done",
        kind=dispatch.kind,
        applied=dispatch.applied,
        outcome=dispatch.outcome,
    )

    next_runtime = dispatch.runtime
    dirty = GraphRuntimeDirty(
        changed_node_ids=set(dispatch.changed_node_ids),
        changed_edge_ids=set(dispatch.changed_edge_ids),
        removed_edge_ids=set(dispatch.removed_edge_ids),
    )
    offer = _apply_missing_quest_offer(next_runtime, dirty)
    if offer is None:
        quest_id = None
    else:
        next_runtime, quest_id = offer
    card = build_graph_action_card(runtime, next_runtime, action, dispatch)
    cards = [card]
    if quest_id is not None:
        cards.append(build_graph_quest_offer_card(next_runtime, quest_id, card.id + 1))
    return _PreparedGraphActionTurn(
        before=runtime,
        after=next_runtime,
        action=action,
        dispatch=dispatch,
        dirty=dirty,
        cards=cards,
    )


def _apply_missing_quest_offer(
    runtime: GameRuntimeState,
    dirty: GraphRuntimeDirty,
) -> tuple[GameRuntimeState, str] | None:
    if runtime.progress.graph_combat_state is not None:
        return None
    offer = plan_missing_quest_offer(
        runtime.graph,
        runtime.progress.player_id,
        runtime.progress.locale,
    )
    if offer is None:
        return None
    offer_apply = apply_runtime_graph_changes(runtime, offer.changes)
    next_runtime = offer_apply.runtime
    dirty.add_apply_result(offer_apply)
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
    engine_diag("quest:offer", quest=offer.quest_id)
    return next_runtime, offer.quest_id


# Persistence


async def _commit_graph_action_result(
    repo: GraphRepo,
    game_id: str,
    prepared: _PreparedGraphActionTurn,
) -> GraphActionTurnResult:
    card = prepared.cards[0]
    log_entries = [*prepared.cards]
    next_progress = prepared.after.progress.model_copy(
        update={"next_log_id": card.id + len(log_entries)}
    )
    next_runtime = prepared.after.model_copy(
        update={
            "progress": next_progress,
            "log_entries": [*prepared.after.log_entries, *log_entries],
        }
    )
    await prepared.dirty.save(repo, game_id, next_runtime.graph)
    await repo.append_log_entries(game_id, log_entries)
    await repo.save_progress(next_runtime.progress)
    engine_diag(
        "turn:result",
        status="executed",
        logs=len(log_entries),
        next_turn=next_runtime.progress.turn_count,
    )
    return GraphActionTurnResult(
        runtime=next_runtime,
        dispatch=prepared.dispatch,
        front_state=graph_to_front_state(next_runtime),
    )


async def _commit_graph_action_narration(
    repo: GraphRepo,
    game_id: str,
    prepared: _PreparedGraphActionTurn,
    result: GraphActionTurnResult,
    narration_result: GraphNarrationResult,
) -> GraphActionTurnResult:
    next_runtime = result.runtime
    log_entries: list[LogEntry] = []
    if narration_result.narration:
        entry = GMLogEntry(
            id=next_runtime.progress.next_log_id,
            kind="gm",
            text=narration_result.narration,
        )
        log_entries.append(entry)
        next_progress = next_runtime.progress.model_copy(
            update={"next_log_id": entry.id + 1}
        )
        next_runtime = next_runtime.model_copy(
            update={
                "progress": next_progress,
                "log_entries": [*next_runtime.log_entries, entry],
            }
        )
        await repo.append_log_entries(game_id, log_entries)
        await repo.save_progress(next_runtime.progress)

    next_runtime = await persist_graph_narration_result(
        repo,
        next_runtime,
        narration_result,
        target_id=_action_target_id(prepared.action),
    )
    engine_diag(
        "turn:done",
        status="executed",
        logs=len(log_entries),
        next_turn=next_runtime.progress.turn_count,
    )
    return GraphActionTurnResult(
        runtime=next_runtime,
        dispatch=prepared.dispatch,
        front_state=graph_to_front_state(next_runtime),
        suggestions=narration_result.suggestions,
    )


def _action_target_id(action: Action) -> str | None:
    for value in (action.what, action.to):
        if isinstance(value, str):
            return value
        if isinstance(value, list) and value and isinstance(value[0], str):
            return value[0]
    return None
