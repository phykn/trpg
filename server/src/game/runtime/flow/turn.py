from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from src.db.repo import GraphRepo, ScenarioRepo
from src.game.domain.action import Action
from src.game.domain.graph.query import inventory_of
from src.game.domain.memory import LogEntry, NarrationCue
from src.llm.client import LLMClient
from src.llm.diag import engine_diag, set_diag_context
from src.wire.graph.to_front import GraphFrontStatePayload, graph_to_front_state

from ..action.apply import GraphRuntimeDirty
from ..action.dispatch import (
    GraphActionDispatchError,
    GraphActionDispatchResult,
    dispatch_graph_action,
)
from ..narration.action import (
    build_graph_action_narration,
    stream_graph_action_narration,
)
from ..narration.cards import build_graph_action_card
from ..load import load_runtime_state
from ..narration.context.events import story_transition_payload
from ..narration.result import (
    GraphNarrationResult,
    VisibleNarrationStream,
    gm_log_entry_from_narration,
    parse_graph_narration_answer,
    persist_graph_narration_result,
)
from ..request_result import GraphResultOutcome, executed_result, outcome_from_dispatch
from ..state import GameRuntimeState
from ..narration.suggestions import GraphSuggestion, next_turn_suggestions
from ..env import env_float
from .generated_input import apply_generated_story_after_action


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


def _action_narration_timeout_s(default: float = 120.0) -> float:
    return env_float("LLM_TIMEOUT_S", default)


# Public flow


async def run_graph_action_turn(
    repo: GraphRepo,
    game_id: str,
    action: Action,
    *,
    llm: LLMClient | None = None,
    scenario_repo: ScenarioRepo | None = None,
    player_input: str | None = None,
) -> GraphActionTurnResult:
    runtime = await load_runtime_state(repo, game_id, scenario_repo)
    set_diag_context(game_id, runtime.progress.turn_count)
    return await run_graph_action_turn_from_runtime(
        repo,
        game_id,
        runtime,
        action,
        llm=llm,
        player_input=player_input,
    )


async def run_graph_action_turn_from_runtime(
    repo: GraphRepo,
    game_id: str,
    runtime: GameRuntimeState,
    action: Action,
    *,
    llm: LLMClient | None = None,
    narration_outcome: GraphResultOutcome | None = None,
    extra_ui_cues: list[NarrationCue] | None = None,
    player_input: str | None = None,
) -> GraphActionTurnResult:
    prepared = _prepare_graph_action_turn(game_id, runtime, action)
    result = await _commit_graph_action_result(repo, game_id, prepared)
    result = await apply_generated_story_after_action(
        client=llm,
        repo=repo,
        result=result,
        contract=_generated_contract(result.runtime),
        player_input=player_input or "",
        action=prepared.action,
    )
    narration_result = await build_graph_action_narration(
        llm,
        before=prepared.before,
        after=result.runtime,
        action=prepared.action,
        dispatch=prepared.dispatch,
        card_texts=[card.text for card in prepared.cards],
        timeout_s=_action_narration_timeout_s(),
    )
    narration_result = _guard_no_reward_choice_narration(
        prepared.before,
        result.runtime,
        prepared.action,
        narration_result,
    )
    return await _commit_graph_action_narration(
        repo,
        game_id,
        prepared,
        result,
        narration_result,
        narration_outcome=narration_outcome,
        extra_ui_cues=extra_ui_cues,
    )


async def run_graph_action_turn_from_runtime_stream(
    repo: GraphRepo,
    game_id: str,
    runtime: GameRuntimeState,
    action: Action,
    *,
    llm: LLMClient | None = None,
    result_outcome: GraphResultOutcome | None = None,
    narration_outcome: GraphResultOutcome | None = None,
    extra_ui_cues: list[NarrationCue] | None = None,
    player_input: str | None = None,
) -> AsyncIterator[dict[str, object]]:
    prepared = _prepare_graph_action_turn(game_id, runtime, action)
    result = await _commit_graph_action_result(repo, game_id, prepared)
    result = await apply_generated_story_after_action(
        client=llm,
        repo=repo,
        result=result,
        contract=_generated_contract(result.runtime),
        player_input=player_input or "",
        action=prepared.action,
    )
    outcome = result_outcome or outcome_from_dispatch(prepared.dispatch)
    yield {
        "type": "result",
        "result": executed_result(
            result.runtime,
            result.front_state,
            outcome=outcome,
        ).model_copy(update={"dispatch": prepared.dispatch}),
    }
    buffer_visible_narration = _should_buffer_no_reward_choice_narration(
        prepared.before,
        result.runtime,
        prepared.action,
    )
    stream = VisibleNarrationStream()
    async for chunk in stream_graph_action_narration(
        llm,
        before=prepared.before,
        after=result.runtime,
        action=prepared.action,
        dispatch=prepared.dispatch,
        card_texts=[card.text for card in prepared.cards],
        timeout_s=_action_narration_timeout_s(),
    ):
        for visible in stream.push(chunk):
            if not buffer_visible_narration:
                yield {"type": "narration_delta", "text": visible}
    for visible in stream.finish():
        if not buffer_visible_narration:
            yield {"type": "narration_delta", "text": visible}
    narration_result = parse_graph_narration_answer(stream.answer())
    narration_result = _guard_no_reward_choice_narration(
        prepared.before,
        result.runtime,
        prepared.action,
        narration_result,
    )
    if buffer_visible_narration and narration_result.narration:
        yield {"type": "narration_delta", "text": narration_result.narration}
    final = await _commit_graph_action_narration(
        repo,
        game_id,
        prepared,
        result,
        narration_result,
        narration_outcome=narration_outcome or result_outcome,
        extra_ui_cues=extra_ui_cues,
    )
    yield {
        "type": "final",
        "result": executed_result(
            final.runtime,
            final.front_state,
            outcome=outcome,
            suggestions=final.suggestions,
        ).model_copy(update={"dispatch": prepared.dispatch}),
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
    card = build_graph_action_card(runtime, next_runtime, action, dispatch)
    cards = [card]
    return _PreparedGraphActionTurn(
        before=runtime,
        after=next_runtime,
        action=action,
        dispatch=dispatch,
        dirty=dirty,
        cards=cards,
    )


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
    *,
    narration_outcome: GraphResultOutcome | None = None,
    extra_ui_cues: list[NarrationCue] | None = None,
) -> GraphActionTurnResult:
    next_runtime = result.runtime
    log_entries: list[LogEntry] = []
    if narration_result.narration:
        if extra_ui_cues:
            narration_result = narration_result.model_copy(
                update={
                    "ui_cues": [
                        *extra_ui_cues,
                        *narration_result.ui_cues,
                    ][:3]
                }
            )
        entry = gm_log_entry_from_narration(
            next_runtime.progress.next_log_id,
            narration_result,
            outcome=narration_outcome or outcome_from_dispatch(prepared.dispatch),
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
        target=_action_target(prepared.action),
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
        suggestions=next_turn_suggestions(next_runtime, narration_result.suggestions),
    )


def _action_target(action: Action) -> str | None:
    for value in (action.what, action.to):
        if isinstance(value, str):
            return value
        if isinstance(value, list) and value and isinstance(value[0], str):
            return value[0]
    return None


def _generated_contract(runtime: GameRuntimeState):
    return runtime.story_contract


def _should_buffer_no_reward_choice_narration(
    before: GameRuntimeState,
    after: GameRuntimeState,
    action: Action,
) -> bool:
    return _no_reward_choice_transition(before, after, action) is not None


def _guard_no_reward_choice_narration(
    before: GameRuntimeState,
    after: GameRuntimeState,
    action: Action,
    result: GraphNarrationResult,
) -> GraphNarrationResult:
    transition = _no_reward_choice_transition(before, after, action)
    if transition is None or not _claims_unearned_item(result):
        return result
    fallback = _no_reward_choice_fallback(transition)
    if not fallback:
        return result.model_copy(update={"ui_cues": [], "suggestions": []})
    return result.model_copy(
        update={
            "narration": fallback,
            "turn_summary": fallback,
            "ui_cues": [],
            "suggestions": [],
        }
    )


def _no_reward_choice_transition(
    before: GameRuntimeState,
    after: GameRuntimeState,
    action: Action,
) -> dict[str, Any] | None:
    if action.verb != "decide" or _gained_inventory_item_ids(before, after):
        return None
    transition = story_transition_payload(before, after, action)
    if transition is None:
        return None
    choice_result = transition.get("choice_result")
    if not isinstance(choice_result, dict) or choice_result.get("gained_items"):
        return None
    choice = choice_result.get("choice")
    quest = choice_result.get("quest")
    if not isinstance(choice, dict) or not isinstance(quest, dict):
        return None
    return transition


def _gained_inventory_item_ids(
    before: GameRuntimeState,
    after: GameRuntimeState,
) -> set[str]:
    before_items = set(inventory_of(before.graph_index, before.progress.player_id))
    after_items = set(inventory_of(after.graph_index, after.progress.player_id))
    return after_items - before_items


def _claims_unearned_item(result: GraphNarrationResult) -> bool:
    cue_text = " ".join(
        f"{cue.label} {cue.text}" for cue in result.ui_cues
    )
    text = " ".join(
        part
        for part in (result.narration, result.turn_summary, cue_text)
        if part
    )
    return any(token in text for token in _UNEARNED_ITEM_CLAIM_TOKENS)


def _no_reward_choice_fallback(transition: dict[str, Any]) -> str:
    choice_result = transition.get("choice_result")
    if not isinstance(choice_result, dict):
        return ""
    quest = choice_result.get("quest")
    choice = choice_result.get("choice")
    if not isinstance(quest, dict) or not isinstance(choice, dict):
        return ""
    quest_name = quest.get("name")
    choice_label = choice.get("label")
    if not isinstance(quest_name, str) or not quest_name:
        return ""
    if not isinstance(choice_label, str) or not choice_label:
        return ""
    text = f"당신은 {quest_name}에서 「{choice_label}」를 선택합니다."
    handoff = transition.get("handoff")
    if isinstance(handoff, str) and handoff:
        text = f"{text} {handoff}"
    return text


_UNEARNED_ITEM_CLAIM_TOKENS = (
    "획득 아이템",
    "아이템 획득",
    "소지품",
    "인벤토리",
    "손에",
    "손안",
    "오른손",
    "왼손",
    "주머니",
    "가방",
    "챙깁",
    "챙겼",
    "쥡",
    "쥐고",
    "쥐었",
    "받아 듭",
    "받아들고",
    "얻습",
    "얻었",
)
