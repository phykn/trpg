from typing import Any, cast

from pydantic import BaseModel, ConfigDict, Field

from src.game.domain.action import Action
from src.game.domain.combat import GraphCombatTraceEvent
from src.game.domain.graph import GraphChange
from src.game.engines.graph_item_use import GraphItemUseError, plan_item_use
from src.game.engines.graph_move import GraphMoveError, plan_character_move
from src.game.engines.graph_quest import (
    GraphQuestError,
    plan_quest_abandon,
    plan_quest_accept,
)
from src.game.engines.graph_rest import GraphRestError, plan_safe_rest
from src.game.engines.graph_transfer import (
    EquipSlot,
    GraphTransferError,
    plan_item_equip,
    plan_item_transfer,
    plan_item_unequip,
)

from .apply import GraphRuntimeApplyError, apply_runtime_graph_changes
from .combat import GraphCombatDispatchError, dispatch_graph_combat_action
from .state import GameRuntimeState


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
    if runtime.progress.graph_combat_state is not None or action.verb in (
        "attack",
        "cast",
    ):
        return _dispatch_combat(runtime, action)

    if action.verb == "query":
        raise GraphActionDispatchError("query is read-only and belongs to query flow")

    try:
        kind, changes, progress_update = _plan_non_combat(runtime, action)
        applied = apply_runtime_graph_changes(runtime, changes)
    except (
        GraphMoveError,
        GraphTransferError,
        GraphItemUseError,
        GraphQuestError,
        GraphRestError,
        GraphRuntimeApplyError,
    ) as exc:
        raise GraphActionDispatchError(str(exc)) from exc

    next_progress = applied.runtime.progress.model_copy(update=progress_update)
    next_runtime = applied.runtime.model_copy(update={"progress": next_progress})
    return GraphActionDispatchResult(
        runtime=next_runtime,
        kind=kind,
        applied=applied.applied,
        changed_node_ids=applied.changed_node_ids,
        changed_edge_ids=applied.changed_edge_ids,
        removed_edge_ids=applied.removed_edge_ids,
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
) -> tuple[str, list[GraphChange], dict[str, Any]]:
    player_id = runtime.progress.player_id

    if action.verb == "move":
        destination_id = _single(action.to) or _single(action.what)
        if destination_id is None:
            raise GraphActionDispatchError("move destination is required")
        result = plan_character_move(
            runtime.graph,
            player_id,
            destination_id,
            require_connection=True,
        )
        return "move", result.changes, _advance_turn(runtime)

    if action.verb == "transfer":
        if action.how in ("accept", "abandon"):
            quest_id = _single(action.what) or _single(action.to)
            if quest_id is None:
                raise GraphActionDispatchError("quest id is required")
            if action.how == "accept":
                result = plan_quest_accept(runtime.graph, quest_id)
                return (
                    "quest_accept",
                    result.changes,
                    {
                        **_advance_turn(runtime),
                        "active_quest_id": quest_id,
                    },
                )
            result = plan_quest_abandon(runtime.graph, quest_id)
            return (
                "quest_abandon",
                result.changes,
                {
                    **_advance_turn(runtime),
                    "active_quest_id": None,
                },
            )

        item_id = _single(action.what) or _single(action.with_)
        if item_id is None:
            raise GraphActionDispatchError("transfer item is required")
        mode = action.how or "transfer"
        if mode == "equip":
            slot = _equip_slot(_single(action.to) or "weapon")
            result = plan_item_equip(runtime.graph, player_id, item_id, slot)
            return "equip", result.changes, _advance_turn(runtime)
        if mode == "unequip":
            result = plan_item_unequip(runtime.graph, player_id, item_id)
            return "unequip", result.changes, _advance_turn(runtime)
        result = plan_item_transfer(
            runtime.graph,
            item_id,
            to_character_id=_single(action.to) or player_id,
            from_node_id=_single(action.from_),
        )
        return "transfer", result.changes, _advance_turn(runtime)

    if action.verb == "use":
        item_id = _single(action.what) or _single(action.with_)
        if item_id is None:
            raise GraphActionDispatchError("use item is required")
        result = plan_item_use(
            runtime.graph,
            player_id,
            item_id,
            target_id=_single(action.to),
        )
        return "use", result.changes, _advance_turn(runtime)

    if action.verb == "rest":
        result = plan_safe_rest(runtime, player_id)
        return "rest", result.changes, {"turn_count": result.next_turn_count}

    if action.verb == "pass":
        raise GraphActionDispatchError("pass outside combat is a narrative no-op")

    if action.verb in ("speak", "perceive"):
        raise GraphActionDispatchError(f"{action.verb} belongs to narrative flow")

    if action.verb == "query":
        raise GraphActionDispatchError("query is read-only and belongs to query flow")

    raise GraphActionDispatchError(f"unsupported graph action: {action.verb}")


def _advance_turn(runtime: GameRuntimeState) -> dict[str, int]:
    return {"turn_count": runtime.progress.turn_count + 1}


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
