from typing import Any, cast

from pydantic import BaseModel, ConfigDict, Field

from src.game.domain.action import Action
from src.game.domain.combat import GraphCombatTraceEvent
from src.game.domain.graph import GraphChange
from src.game.engines.graph.item_use import GraphItemUseError, plan_item_use
from src.game.engines.graph.move import GraphMoveError, plan_character_move
from src.game.engines.graph.progression import plan_progression_after_quest_completion
from src.game.engines.graph.quest import (
    GraphQuestError,
    plan_quest_abandon,
    plan_quest_accept,
    plan_quest_decide,
    plan_quest_progress_for_trigger,
    plan_quest_rewards,
)
from src.game.engines.graph.rest import GraphRestError, plan_rest
from src.game.engines.graph.transfer import (
    EquipSlot,
    GraphTransferError,
    plan_item_equip,
    plan_item_trade,
    plan_item_transfer,
    plan_item_unequip,
)

from ..state import GameRuntimeState
from .apply import (
    GraphRuntimeApplyError,
    GraphRuntimeDirty,
    apply_runtime_graph_changes,
)
from .combat import GraphCombatDispatchError, dispatch_graph_combat_action


class GraphActionDispatchError(ValueError):
    pass


class GraphActionDispatchResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    runtime: GameRuntimeState
    kind: str
    applied: int
    changed_node_ids: list[str]
    changed_edge_ids: list[str]
    removed_edge_ids: list[str]
    outcome: str | None = None
    combat_trace: list[GraphCombatTraceEvent] = Field(default_factory=list)


def dispatch_graph_action(
    runtime: GameRuntimeState,
    action: Action,
) -> GraphActionDispatchResult:
    if runtime.progress.graph_combat_state is not None or action.verb == "attack":
        return _dispatch_combat(runtime, action)

    if action.verb == "query":
        raise GraphActionDispatchError("query is read-only and belongs to query flow")

    try:
        kind, changes, progress_update, completed_quest_ids = _plan_non_combat(
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
        quest_apply = _apply_quest_progress_for_action(next_runtime, action, kind)
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
            satisfied_location_ids=_visited_location_ids(next_runtime),
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


def _dispatch_combat(
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


def _plan_non_combat(
    runtime: GameRuntimeState,
    action: Action,
) -> tuple[str, list[GraphChange], dict[str, Any], list[str]]:
    player_id = runtime.progress.player_id

    if action.verb == "move":
        _require_player_can_move(runtime)
        destination_id = _single(action.to) or _single(action.what)
        if destination_id is None:
            raise GraphActionDispatchError("move destination is required")
        result = plan_character_move(
            runtime.graph,
            player_id,
            destination_id,
            require_connection=True,
        )
        return "move", result.changes, _advance_turn(runtime), []

    if action.verb == "transfer":
        if action.how in ("accept", "abandon"):
            quest_id = _single(action.what) or _single(action.to)
            if quest_id is None:
                raise GraphActionDispatchError("quest id is required")
            if action.how == "accept":
                result = plan_quest_accept(
                    runtime.graph,
                    quest_id,
                    active_quest_id=runtime.progress.active_quest_id,
                )
                return (
                    "quest_accept",
                    result.changes,
                    {
                        **_advance_turn(runtime),
                        "active_quest_id": quest_id,
                    },
                    [],
                )
            result = plan_quest_abandon(runtime.graph, quest_id)
            return (
                "quest_abandon",
                result.changes,
                {
                    **_advance_turn(runtime),
                    "active_quest_id": None,
                },
                [],
            )

        item_id = _single(action.what) or _single(action.with_)
        if item_id is None:
            raise GraphActionDispatchError("transfer item is required")
        mode = action.how or "transfer"
        if mode == "equip":
            slot = _equip_slot(_single(action.to) or "weapon")
            result = plan_item_equip(runtime.graph, player_id, item_id, slot)
            return "equip", result.changes, _advance_turn(runtime), []
        if mode == "unequip":
            result = plan_item_unequip(runtime.graph, player_id, item_id)
            return "unequip", result.changes, _advance_turn(runtime), []
        if mode == "trade":
            result = plan_item_trade(
                runtime.graph,
                item_id,
                from_character_id=_single(action.from_) or player_id,
                to_character_id=_single(action.to) or player_id,
                player_id=player_id,
            )
            return f"trade_{result.action}", result.changes, _advance_turn(runtime), []
        result = plan_item_transfer(
            runtime.graph,
            item_id,
            to_character_id=_single(action.to) or player_id,
            from_node_id=_single(action.from_),
        )
        return "transfer", result.changes, _advance_turn(runtime), []

    if action.verb == "use":
        item_id = _single(action.what) or _single(action.with_)
        if item_id is None:
            raise GraphActionDispatchError("use item is required")
        result = plan_item_use(
            runtime.graph,
            player_id,
            item_id,
            target=_single(action.to),
        )
        return "use", result.changes, _advance_turn(runtime), []

    if action.verb == "rest":
        result = plan_rest(runtime, player_id)
        progress_update: dict[str, Any] = {"turn_count": result.next_turn_count}
        if result.kind == "encounter":
            progress_update["graph_combat_state"] = result.state
            return "rest_encounter", result.changes, progress_update, []
        return "rest", result.changes, progress_update, []

    if action.verb == "decide":
        quest_id = _single(action.what)
        if quest_id is None:
            raise GraphActionDispatchError("decide quest id is required")
        if not action.how:
            raise GraphActionDispatchError("decide choice id is required")
        result = plan_quest_decide(runtime.graph, quest_id, action.how)
        return "decide", result.changes, _advance_turn(runtime), [quest_id]

    if action.verb == "pass":
        raise GraphActionDispatchError("pass outside combat is a narrative no-op")

    if action.verb in ("speak", "perceive"):
        raise GraphActionDispatchError(f"{action.verb} belongs to narrative flow")

    if action.verb == "query":
        raise GraphActionDispatchError("query is read-only and belongs to query flow")

    raise GraphActionDispatchError(f"unsupported graph action: {action.verb}")


def _advance_turn(runtime: GameRuntimeState) -> dict[str, int]:
    return {"turn_count": runtime.progress.turn_count + 1}


def _apply_quest_progress_for_action(
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


def _quest_trigger_for_action(
    runtime: GameRuntimeState,
    action: Action,
    kind: str,
) -> tuple[str, str] | None:
    if kind == "move":
        destination_id = _single(action.to) or _single(action.what)
        if destination_id is not None:
            return "location_enter", destination_id
    if kind == "use":
        item_id = _single(action.what) or _single(action.with_)
        if item_id is not None:
            return "item_use", item_id
    if kind in {"transfer", "trade_buy"}:
        item_id = _single(action.what) or _single(action.with_)
        target = _single(action.to) or runtime.progress.player_id
        if item_id is not None and target == runtime.progress.player_id:
            return "item_obtained", item_id
    return None


def _require_player_can_move(runtime: GameRuntimeState) -> None:
    player = runtime.graph.nodes.get(runtime.progress.player_id)
    if player is None:
        raise GraphActionDispatchError("missing player")


def _visited_location_ids(runtime: GameRuntimeState) -> set[str]:
    player = runtime.graph.nodes.get(runtime.progress.player_id)
    if player is None:
        return set()
    raw = player.properties.get("visited_location_ids", [])
    if not isinstance(raw, list):
        return set()
    return {item for item in raw if isinstance(item, str)}


def _single(value: object) -> str | None:
    if isinstance(value, str):
        return value
    if isinstance(value, list) and value and isinstance(value[0], str):
        return value[0]
    return None


def _equip_slot(value: str) -> EquipSlot:
    if value not in ("weapon", "armor", "accessory"):
        raise GraphActionDispatchError(f"unknown equipment slot: {value}")
    return cast(EquipSlot, value)
