"""Top-level graph action dispatch orchestration."""

from src.game.domain.action import Action
from src.game.engines.graph.item_use import GraphItemUseError
from src.game.engines.graph.move import GraphMoveError
from src.game.engines.graph.progression import plan_progression_after_quest_completion
from src.game.engines.graph.quest import GraphQuestError, plan_quest_rewards
from src.game.engines.graph.rest import GraphRestError
from src.game.engines.graph.transfer import GraphTransferError
from src.game.runtime.state import GameRuntimeState

from ..apply import (
    GraphRuntimeApplyError,
    GraphRuntimeDirty,
    apply_runtime_graph_changes,
)
from .combat import dispatch_combat
from .planning import plan_non_combat
from .post_apply import (
    apply_arrival_branch_effects,
    apply_quest_progress_for_action,
    visited_location_ids,
)
from .types import GraphActionDispatchError, GraphActionDispatchResult


def dispatch_graph_action(
    runtime: GameRuntimeState,
    action: Action,
) -> GraphActionDispatchResult:
    if runtime.progress.graph_combat_state is not None or action.verb == "attack":
        return dispatch_combat(runtime, action)

    try:
        kind, changes, progress_update, completed_quest_ids = plan_non_combat(
            runtime,
            action,
        )
        applied = apply_runtime_graph_changes(runtime, changes)
        dirty = GraphRuntimeDirty.from_apply_result(applied)
        next_runtime = applied.runtime
        applied_count = applied.applied
        for quest_id in completed_quest_ids:
            reward = plan_quest_rewards(
                next_runtime.graph,
                quest_id,
                next_runtime.progress.player_id,
            )
            if not reward.changes:
                continue
            reward_applied = apply_runtime_graph_changes(next_runtime, reward.changes)
            next_runtime = reward_applied.runtime
            dirty.add_apply_result(reward_applied)
            applied_count += reward_applied.applied
        arrival_apply = apply_arrival_branch_effects(runtime, next_runtime, kind)
        if arrival_apply is not None:
            next_runtime, arrival_dirty, arrival_applied, hidden_character_ids = (
                arrival_apply
            )
            dirty.changed_node_ids.update(arrival_dirty.changed_node_ids)
            dirty.changed_edge_ids.update(arrival_dirty.changed_edge_ids)
            dirty.removed_edge_ids.update(arrival_dirty.removed_edge_ids)
            applied_count += arrival_applied
            if next_runtime.progress.active_subject_id in hidden_character_ids:
                progress_update = {**progress_update, "active_subject_id": None}
        quest_apply = apply_quest_progress_for_action(next_runtime, action, kind)
        if quest_apply is not None:
            next_runtime, quest_dirty, quest_applied, completed_quest_ids = quest_apply
            dirty.changed_node_ids.update(quest_dirty.changed_node_ids)
            dirty.changed_edge_ids.update(quest_dirty.changed_edge_ids)
            dirty.removed_edge_ids.update(quest_dirty.removed_edge_ids)
            applied_count += quest_applied
    except (
        GraphMoveError,
        GraphTransferError,
        GraphItemUseError,
        GraphQuestError,
        GraphRestError,
        GraphRuntimeApplyError,
    ) as exc:
        raise GraphActionDispatchError(str(exc)) from exc

    if completed_quest_ids:
        progression = plan_progression_after_quest_completion(
            next_runtime.graph,
            completed_quest_ids=completed_quest_ids,
            active_quest_id=next_runtime.progress.active_quest_id,
            satisfied_location_ids=visited_location_ids(next_runtime),
        )
        if progression.changes:
            progression_apply = apply_runtime_graph_changes(
                next_runtime,
                progression.changes,
            )
            next_runtime = progression_apply.runtime
            dirty.add_apply_result(progression_apply)
            applied_count += progression_apply.applied
        for quest_id in progression.auto_completed_quest_ids:
            reward = plan_quest_rewards(
                next_runtime.graph,
                quest_id,
                next_runtime.progress.player_id,
            )
            if not reward.changes:
                continue
            reward_applied = apply_runtime_graph_changes(next_runtime, reward.changes)
            next_runtime = reward_applied.runtime
            dirty.add_apply_result(reward_applied)
            applied_count += reward_applied.applied
        progress_update = {
            **progress_update,
            "active_quest_id": progression.next_active_quest_id,
        }
    next_progress = next_runtime.progress.model_copy(update=progress_update)
    next_runtime = next_runtime.model_copy(update={"progress": next_progress})
    return GraphActionDispatchResult(
        runtime=next_runtime,
        kind=kind,
        applied=applied_count,
        changed_node_ids=sorted(dirty.changed_node_ids),
        changed_edge_ids=sorted(dirty.changed_edge_ids),
        removed_edge_ids=sorted(dirty.removed_edge_ids),
    )
