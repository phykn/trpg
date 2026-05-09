from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from src.db.repo import GraphRepo
from src.game.domain.action import Action
from src.game.engines.graph_quest_generation import plan_missing_quest_offer
from src.wire.graph_to_front import GraphFrontStatePayload, graph_to_front_state

from .apply import apply_runtime_graph_changes
from .dispatch import (
    GraphActionDispatchError,
    GraphActionDispatchResult,
    dispatch_graph_action,
)
from .cards import build_graph_action_card
from .load import load_runtime_state
from .state import GameRuntimeState


class GraphActionTurnError(ValueError):
    pass


class GraphActionTurnResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    runtime: GameRuntimeState
    dispatch: GraphActionDispatchResult
    front_state: GraphFrontStatePayload


async def run_graph_action_turn(
    repo: GraphRepo,
    game_id: str,
    action: Action,
) -> GraphActionTurnResult:
    runtime = await load_runtime_state(repo, game_id)
    return await run_graph_action_turn_from_runtime(repo, game_id, runtime, action)


async def run_graph_action_turn_from_runtime(
    repo: GraphRepo,
    game_id: str,
    runtime: GameRuntimeState,
    action: Action,
) -> GraphActionTurnResult:
    try:
        dispatch = dispatch_graph_action(runtime, action)
    except GraphActionDispatchError as exc:
        raise GraphActionTurnError(str(exc)) from exc

    next_runtime = dispatch.runtime
    if next_runtime.progress.graph_combat_state is None:
        offer = plan_missing_quest_offer(
            next_runtime.graph,
            next_runtime.progress.player_id,
        )
        if offer is not None:
            next_runtime = apply_runtime_graph_changes(
                next_runtime,
                offer.changes,
            ).runtime
    card = build_graph_action_card(runtime, next_runtime, action, dispatch)
    next_progress = next_runtime.progress.model_copy(
        update={"next_log_id": card.id + 1}
    )
    next_runtime = next_runtime.model_copy(
        update={
            "progress": next_progress,
            "log_entries": [*next_runtime.log_entries, card],
        }
    )
    await repo.save_graph(game_id, next_runtime.graph)
    await repo.append_log_entries(game_id, [card])
    await repo.save_progress(next_runtime.progress)
    return GraphActionTurnResult(
        runtime=next_runtime,
        dispatch=dispatch,
        front_state=graph_to_front_state(next_runtime),
    )
