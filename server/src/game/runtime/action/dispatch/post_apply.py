"""Post-application follow-up effects for graph dispatch."""

from src.game.domain.action import Action
from src.game.domain.graph.query import location_of
from src.game.engines.graph.arrival import plan_arrival_branch_effects
from src.game.engines.graph.quest import plan_quest_progress_for_trigger, plan_quest_rewards
from src.game.runtime.state import GameRuntimeState

from ...action_refs import first_ref
from ..apply import GraphRuntimeDirty, apply_runtime_graph_changes


def apply_arrival_branch_effects(
    before: GameRuntimeState,
    after: GameRuntimeState,
    kind: str,
) -> tuple[GameRuntimeState, GraphRuntimeDirty, int, list[str]] | None:
    if kind != "move":
        return None
    before_place_id = location_of(before.graph, before.progress.player_id)
    after_place_id = location_of(after.graph, after.progress.player_id)
    if before_place_id == after_place_id or after_place_id is None:
        return None

    planned = plan_arrival_branch_effects(
        after.graph,
        after.progress.player_id,
        after_place_id,
    )
    if not planned.changes:
        return None
    applied = apply_runtime_graph_changes(after, planned.changes)
    return (
        applied.runtime,
        GraphRuntimeDirty.from_apply_result(applied),
        applied.applied,
        planned.hidden_character_ids,
    )


def apply_quest_progress_for_action(
    runtime: GameRuntimeState,
    action: Action,
    kind: str,
) -> tuple[GameRuntimeState, GraphRuntimeDirty, int, list[str]] | None:
    trigger = _quest_trigger_for_action(runtime, action, kind)
    if trigger is None:
        return None
    trigger_type, target = trigger
    progress = plan_quest_progress_for_trigger(runtime.graph, trigger_type, target)
    if not progress.changes:
        return None

    applied = apply_runtime_graph_changes(runtime, progress.changes)
    next_runtime = applied.runtime
    dirty = GraphRuntimeDirty.from_apply_result(applied)
    applied_count = applied.applied
    for quest_id in progress.completed_quest_ids:
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
    return next_runtime, dirty, applied_count, progress.completed_quest_ids


def visited_location_ids(runtime: GameRuntimeState) -> set[str]:
    player = runtime.graph.nodes.get(runtime.progress.player_id)
    if player is None:
        return set()
    raw = player.properties.get("visited_location_ids", [])
    if not isinstance(raw, list):
        return set()
    return {item for item in raw if isinstance(item, str)}


def _quest_trigger_for_action(
    runtime: GameRuntimeState,
    action: Action,
    kind: str,
) -> tuple[str, str] | None:
    if kind == "move":
        destination_id = first_ref(action.to) or first_ref(action.what)
        if destination_id is not None:
            return "location_enter", destination_id
    if kind == "use":
        item_id = first_ref(action.what) or first_ref(action.with_)
        if item_id is not None:
            return "item_use", item_id
    if kind in {"transfer", "trade_buy"}:
        item_id = first_ref(action.what) or first_ref(action.with_)
        target = first_ref(action.to) or runtime.progress.player_id
        if item_id is not None and target == runtime.progress.player_id:
            return "item_obtained", item_id
    return None
