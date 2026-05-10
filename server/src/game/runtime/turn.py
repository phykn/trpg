from __future__ import annotations

import asyncio
import json

from pydantic import BaseModel, ConfigDict

from src.db.repo import GraphRepo
from src.game.domain.action import Action
from src.game.domain.errors import LLMUnavailable
from src.game.domain.graph import GraphNode
from src.game.domain.graph_query import location_of
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
from .state import GameRuntimeState


class GraphActionTurnError(ValueError):
    pass


class GraphActionTurnResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    runtime: GameRuntimeState
    dispatch: GraphActionDispatchResult
    front_state: GraphFrontStatePayload


_GRAPH_ACTION_NARRATION_TIMEOUT_SECONDS = 6.0


async def run_graph_action_turn(
    repo: GraphRepo,
    game_id: str,
    action: Action,
    *,
    llm: LLMClient | None = None,
) -> GraphActionTurnResult:
    runtime = await load_runtime_state(repo, game_id)
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
    offer_quest_id: str | None = None
    if next_runtime.progress.graph_combat_state is None:
        offer = plan_missing_quest_offer(
            next_runtime.graph,
            next_runtime.progress.player_id,
            next_runtime.progress.locale,
        )
        if offer is not None:
            next_runtime = apply_runtime_graph_changes(
                next_runtime,
                offer.changes,
            ).runtime
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
    narration = await _build_graph_action_narration(
        llm,
        before=runtime,
        after=next_runtime,
        action=action,
        dispatch=dispatch,
        card_texts=[card.text for card in cards],
    )
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
    await repo.save_graph(game_id, next_runtime.graph)
    await repo.append_log_entries(game_id, log_entries)
    await repo.save_progress(next_runtime.progress)
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
    )


async def _build_graph_action_narration(
    llm: LLMClient | None,
    *,
    before: GameRuntimeState,
    after: GameRuntimeState,
    action: Action,
    dispatch: GraphActionDispatchResult,
    card_texts: list[str],
) -> str:
    if llm is None or not _needs_graph_action_narration(before, after, action, dispatch):
        return ""
    prompt = _narration_user_prompt(before, after, card_texts)
    if not prompt:
        return ""
    llm_diag("llm:call", agent="graph_narrate")
    try:
        result = await asyncio.wait_for(
            llm.chat(
                [
                    {
                        "role": "system",
                        "content": get_prompt("graph_narrate", before.progress.locale),
                    },
                    {"role": "user", "content": prompt},
                ],
                think=False,
                agent="graph_narrate",
                temperature=0.2,
            ),
            timeout=_GRAPH_ACTION_NARRATION_TIMEOUT_SECONDS,
        )
    except (LLMUnavailable, OSError, TimeoutError) as exc:
        llm_diag("llm:fail", agent="graph_narrate", err=type(exc).__name__)
        return ""
    llm_diag("llm:done", agent="graph_narrate")
    answer = result.get("answer")
    if not isinstance(answer, str):
        return ""
    return _clean_narration(answer)


def _needs_graph_action_narration(
    before: GameRuntimeState,
    after: GameRuntimeState,
    action: Action,
    dispatch: GraphActionDispatchResult,
) -> bool:
    if dispatch.kind == "combat":
        return True
    if dispatch.kind in {"quest_accept", "quest_abandon"}:
        return True
    if action.verb == "move":
        return False
    return before.progress.active_quest_id != after.progress.active_quest_id


def _narration_user_prompt(
    before: GameRuntimeState,
    after: GameRuntimeState,
    card_texts: list[str],
) -> str:
    player = after.graph.nodes.get(after.progress.player_id)
    place_id = location_of(after.graph, after.progress.player_id)
    place = after.graph.nodes.get(place_id or "")
    return json.dumps(
        {
            "player": _node_name(player, after.progress.locale),
            "current_place": _node_name(place, after.progress.locale),
            "place_description": _node_description_value(place),
            "resolved_results": card_texts,
            "combat_scene": before.progress.graph_combat_state is not None
            or after.progress.graph_combat_state is not None,
        },
        ensure_ascii=False,
    )


def _clean_narration(text: str) -> str:
    cleaned = " ".join(text.split())
    if len(cleaned) <= 220:
        return cleaned
    return cleaned[:220].rstrip()


def _node_name(node: GraphNode | None, locale: str) -> str:
    if node is None:
        return render("runtime.none", locale)
    name = node.properties.get("name")
    if isinstance(name, str) and name:
        return name
    title = node.properties.get("title")
    if isinstance(title, str) and title:
        return title
    return node.id


def _node_description_value(node: GraphNode | None) -> str | None:
    if node is None:
        return None
    description = node.properties.get("description")
    return description if isinstance(description, str) and description else None


