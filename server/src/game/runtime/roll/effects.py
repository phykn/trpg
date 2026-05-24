from dataclasses import dataclass, field

from src.game.domain.action import Action
from src.game.domain.memory import NarrationCue
from src.game.engines.graph.progression import plan_progression_after_quest_completion
from src.game.engines.graph.quest import (
    plan_quest_progress_for_trigger,
    plan_quest_rewards,
)
from src.game.engines.graph.roll import plan_roll_graph_effects, plan_roll_quest_trigger

from ..action.apply import GraphRuntimeDirty, apply_runtime_graph_changes
from ..request_result import GraphResultOutcome
from ..state import GameRuntimeState
from .affinity import affinity_change_cues


@dataclass
class RollEffectResult:
    runtime: GameRuntimeState
    changed_node_ids: list[str] = field(default_factory=list)
    changed_edge_ids: list[str] = field(default_factory=list)
    removed_edge_ids: list[str] = field(default_factory=list)
    completed_quest_ids: list[str] = field(default_factory=list)
    next_active_quest_id: str | None = None
    affinity_cues: list[NarrationCue] = field(default_factory=list)


def apply_roll_effects(
    runtime: GameRuntimeState,
    action: Action,
    *,
    grade: str,
    outcome: GraphResultOutcome,
) -> RollEffectResult:
    effect = plan_roll_graph_effects(
        runtime.graph,
        player_id=runtime.progress.player_id,
        action=action,
        grade=grade,
        roll_outcome=outcome,
    )
    affinity_cues = affinity_change_cues(runtime, effect.changes)
    if effect.changes:
        effect_apply = apply_runtime_graph_changes(runtime, effect.changes)
        runtime = effect_apply.runtime
        changed_node_ids = list(effect_apply.changed_node_ids)
        changed_edge_ids = list(effect_apply.changed_edge_ids)
        removed_edge_ids = list(effect_apply.removed_edge_ids)
    else:
        changed_node_ids = []
        changed_edge_ids = []
        removed_edge_ids = []

    runtime, quest_dirty, completed_quest_ids = _apply_roll_quest_effect(
        runtime,
        action,
        roll_outcome=outcome,
    )
    changed_node_ids.extend(quest_dirty.changed_node_ids)
    changed_edge_ids.extend(quest_dirty.changed_edge_ids)
    removed_edge_ids.extend(quest_dirty.removed_edge_ids)
    next_active_quest_id = runtime.progress.active_quest_id

    if completed_quest_ids:
        progression = plan_progression_after_quest_completion(
            runtime.graph,
            completed_quest_ids=completed_quest_ids,
            active_quest_id=runtime.progress.active_quest_id,
            satisfied_location_ids=_visited_location_ids(runtime),
        )
        if progression.changes:
            progression_apply = apply_runtime_graph_changes(
                runtime,
                progression.changes,
            )
            runtime = progression_apply.runtime
            changed_node_ids.extend(progression_apply.changed_node_ids)
            changed_edge_ids.extend(progression_apply.changed_edge_ids)
            removed_edge_ids.extend(progression_apply.removed_edge_ids)
        for quest_id in progression.auto_completed_quest_ids:
            reward = plan_quest_rewards(
                runtime.graph,
                quest_id,
                runtime.progress.player_id,
            )
            if not reward.changes:
                continue
            reward_apply = apply_runtime_graph_changes(runtime, reward.changes)
            runtime = reward_apply.runtime
            changed_node_ids.extend(reward_apply.changed_node_ids)
            changed_edge_ids.extend(reward_apply.changed_edge_ids)
            removed_edge_ids.extend(reward_apply.removed_edge_ids)
        next_active_quest_id = progression.next_active_quest_id

    return RollEffectResult(
        runtime=runtime,
        changed_node_ids=changed_node_ids,
        changed_edge_ids=changed_edge_ids,
        removed_edge_ids=removed_edge_ids,
        completed_quest_ids=completed_quest_ids,
        next_active_quest_id=next_active_quest_id,
        affinity_cues=affinity_cues,
    )


def _apply_roll_quest_effect(
    runtime: GameRuntimeState,
    action: Action,
    *,
    roll_outcome: GraphResultOutcome,
) -> tuple[GameRuntimeState, GraphRuntimeDirty, list[str]]:
    dirty = GraphRuntimeDirty()
    if roll_outcome != "success":
        return runtime, dirty, []
    trigger = plan_roll_quest_trigger(
        runtime.graph,
        player_id=runtime.progress.player_id,
        action=action,
    )
    if trigger is None:
        return runtime, dirty, []

    trigger_type, target = trigger
    progress = plan_quest_progress_for_trigger(runtime.graph, trigger_type, target)
    if not progress.changes:
        return runtime, dirty, []

    progress_apply = apply_runtime_graph_changes(runtime, progress.changes)
    next_runtime = progress_apply.runtime
    dirty.add_apply_result(progress_apply)
    for quest_id in progress.completed_quest_ids:
        reward = plan_quest_rewards(
            next_runtime.graph,
            quest_id,
            next_runtime.progress.player_id,
        )
        if not reward.changes:
            continue
        reward_apply = apply_runtime_graph_changes(next_runtime, reward.changes)
        next_runtime = reward_apply.runtime
        dirty.add_apply_result(reward_apply)
    return next_runtime, dirty, progress.completed_quest_ids


def _visited_location_ids(runtime: GameRuntimeState) -> set[str]:
    player = runtime.graph.nodes.get(runtime.progress.player_id)
    if player is None:
        return set()
    raw = player.properties.get("visited_location_ids", [])
    if not isinstance(raw, list):
        return set()
    return {item for item in raw if isinstance(item, str)}
