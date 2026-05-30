"""Non-combat action planning for graph dispatch."""

from typing import Any, cast

from src.game.domain.action import Action
from src.game.domain.graph import GraphChange
from src.game.engines.graph.item_use import plan_item_use
from src.game.engines.graph.move import plan_character_move
from src.game.engines.graph.quest import (
    plan_quest_abandon,
    plan_quest_accept,
    plan_quest_decide,
)
from src.game.engines.graph.rest import plan_rest
from src.game.engines.graph.transfer import (
    EquipSlot,
    plan_item_equip,
    plan_item_trade,
    plan_item_transfer,
    plan_item_unequip,
)
from src.game.runtime.state import GameRuntimeState

from ...action_refs import first_ref
from .types import GraphActionDispatchError


def plan_non_combat(
    runtime: GameRuntimeState,
    action: Action,
) -> tuple[str, list[GraphChange], dict[str, Any], list[str]]:
    player_id = runtime.progress.player_id

    if action.verb == "move":
        _require_player_can_move(runtime)
        destination_id = first_ref(action.to) or first_ref(action.what)
        if destination_id is None:
            raise GraphActionDispatchError("move destination is required")
        result = plan_character_move(
            runtime.graph,
            player_id,
            destination_id,
            require_connection=True,
        )
        return "move", result.changes, advance_turn(runtime), []

    if action.verb == "transfer":
        if action.how in ("accept", "abandon"):
            quest_id = first_ref(action.what) or first_ref(action.to)
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
                        **advance_turn(runtime),
                        "active_quest_id": quest_id,
                    },
                    [],
                )
            result = plan_quest_abandon(runtime.graph, quest_id)
            return (
                "quest_abandon",
                result.changes,
                {
                    **advance_turn(runtime),
                    "active_quest_id": None,
                },
                [],
            )

        item_id = first_ref(action.what) or first_ref(action.with_)
        if item_id is None:
            raise GraphActionDispatchError("transfer item is required")
        mode = action.how or "transfer"
        if mode == "equip":
            slot = _equip_slot(first_ref(action.to) or "weapon")
            result = plan_item_equip(runtime.graph, player_id, item_id, slot)
            return "equip", result.changes, advance_turn(runtime), []
        if mode == "unequip":
            result = plan_item_unequip(runtime.graph, player_id, item_id)
            return "unequip", result.changes, advance_turn(runtime), []
        if mode == "trade":
            result = plan_item_trade(
                runtime.graph,
                item_id,
                from_character_id=first_ref(action.from_) or player_id,
                to_character_id=first_ref(action.to) or player_id,
                player_id=player_id,
            )
            return f"trade_{result.action}", result.changes, advance_turn(runtime), []
        result = plan_item_transfer(
            runtime.graph,
            item_id,
            to_character_id=first_ref(action.to) or player_id,
            from_node_id=first_ref(action.from_),
        )
        return "transfer", result.changes, advance_turn(runtime), []

    if action.verb == "use":
        item_id = first_ref(action.what) or first_ref(action.with_)
        if item_id is None:
            raise GraphActionDispatchError("use item is required")
        result = plan_item_use(
            runtime.graph,
            player_id,
            item_id,
            target=first_ref(action.to),
        )
        return "use", result.changes, advance_turn(runtime), []

    if action.verb == "rest":
        result = plan_rest(runtime, player_id)
        progress_update: dict[str, Any] = {"turn_count": result.next_turn_count}
        if result.kind == "encounter":
            progress_update["graph_combat_state"] = result.state
            return "rest_encounter", result.changes, progress_update, []
        return "rest", result.changes, progress_update, []

    if action.verb == "decide":
        quest_id = first_ref(action.what)
        if quest_id is None:
            raise GraphActionDispatchError("decide quest id is required")
        if not action.how:
            raise GraphActionDispatchError("decide choice id is required")
        result = plan_quest_decide(runtime.graph, quest_id, action.how)
        return "decide", result.changes, advance_turn(runtime), [quest_id]

    if action.verb == "pass":
        raise GraphActionDispatchError("pass outside combat is a narrative no-op")

    if action.verb in ("speak", "perceive"):
        raise GraphActionDispatchError(f"{action.verb} belongs to narrative flow")

    raise GraphActionDispatchError(f"unsupported graph action: {action.verb}")


def advance_turn(runtime: GameRuntimeState) -> dict[str, int]:
    return {"turn_count": runtime.progress.turn_count + 1}


def _require_player_can_move(runtime: GameRuntimeState) -> None:
    player = runtime.graph.nodes.get(runtime.progress.player_id)
    if player is None:
        raise GraphActionDispatchError("missing player")


def _equip_slot(value: str) -> EquipSlot:
    if value not in ("weapon", "armor", "accessory"):
        raise GraphActionDispatchError(f"unknown equipment slot: {value}")
    return cast(EquipSlot, value)
