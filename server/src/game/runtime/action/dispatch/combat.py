"""Combat branch for graph action dispatch."""

from src.game.domain.action import Action
from src.game.runtime.state import GameRuntimeState

from ..combat import GraphCombatDispatchError, dispatch_graph_combat_action
from .types import GraphActionDispatchError, GraphActionDispatchResult


def dispatch_combat(
    runtime: GameRuntimeState,
    action: Action,
) -> GraphActionDispatchResult:
    try:
        combat = dispatch_graph_combat_action(runtime, action)
    except GraphCombatDispatchError as exc:
        raise GraphActionDispatchError(str(exc)) from exc

    next_progress = combat.runtime.progress.model_copy(
        update={"turn_count": combat.runtime.progress.turn_count + 1}
    )
    next_runtime = combat.runtime.model_copy(update={"progress": next_progress})
    return GraphActionDispatchResult(
        runtime=next_runtime,
        kind="combat",
        applied=combat.applied,
        changed_node_ids=combat.changed_node_ids,
        changed_edge_ids=combat.changed_edge_ids,
        removed_edge_ids=combat.removed_edge_ids,
        outcome=combat.outcome,
        combat_trace=combat.combat.state.trace,
    )
