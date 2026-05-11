from typing import Literal

from pydantic import BaseModel, ConfigDict

from src.game.domain.graph import (
    AddEdgeChange,
    Graph,
    GraphChange,
    GraphEdge,
    GraphNode,
    RemoveEdgeChange,
    SetNodePropertyChange,
)
from src.game.domain.graph_query import edges_from
from src.game.rules import RULES


EquipSlot = Literal["weapon", "armor", "accessory"]

_EQUIP_SLOTS: frozenset[str] = frozenset({"weapon", "armor", "accessory"})
_ITEM_FROM_PLACEMENT_TYPES: frozenset[str] = frozenset(
    {"located_at", "hidden_at", "reward_of"}
)
_ITEM_TO_PLACEMENT_TYPES: frozenset[str] = frozenset({"carries", "equips"})


class GraphTransferError(ValueError):
    pass


class GraphItemTransferResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    changes: list[GraphChange]
    item_id: str
    from_node_id: str | None = None
    to_node_id: str
    action: Literal["transfer", "equip", "unequip", "buy", "sell"]


def plan_item_transfer(
    graph: Graph,
    item_id: str,
    *,
    to_character_id: str,
    from_node_id: str | None = None,
) -> GraphItemTransferResult:
    _require_item(graph, item_id)
    _require_character(graph, to_character_id)
    placement = _require_placement(graph, item_id)
    owner_id = _placement_owner(placement)
    if from_node_id is not None and owner_id != from_node_id:
        raise GraphTransferError(
            f"source mismatch for {item_id}: expected {from_node_id}, got {owner_id}"
        )

    changes: list[GraphChange] = [
        RemoveEdgeChange(type="remove_edge", edge_id=placement.id),
        _carry_change(to_character_id, item_id),
    ]
    return GraphItemTransferResult(
        changes=changes,
        item_id=item_id,
        from_node_id=owner_id,
        to_node_id=to_character_id,
        action="transfer",
    )


def plan_item_trade(
    graph: Graph,
    item_id: str,
    *,
    from_character_id: str,
    to_character_id: str,
    player_id: str,
) -> GraphItemTransferResult:
    item = _require_item(graph, item_id)
    source = _require_character(graph, from_character_id)
    target = _require_character(graph, to_character_id)
    if from_character_id == to_character_id:
        raise GraphTransferError("trade requires two different characters")
    if player_id not in {from_character_id, to_character_id}:
        raise GraphTransferError("trade must include the player")

    placement = _require_placement(graph, item_id)
    owner_id = _placement_owner(placement)
    if owner_id != from_character_id:
        raise GraphTransferError(
            f"source mismatch for {item_id}: expected {from_character_id}, got {owner_id}"
        )
    if placement.type == "equips":
        raise GraphTransferError(f"equipped item cannot be traded: {item_id}")

    merchant_id = to_character_id if from_character_id == player_id else from_character_id
    _require_trade_affinity(graph, merchant_id, player_id)

    price = _int_value(item.properties.get("price"), default=0)
    action: Literal["buy", "sell"]
    if to_character_id == player_id:
        action = "buy"
        amount = price
        _require_gold(source, "merchant")
        _require_gold_at_least(target, amount, "player")
        gold_changes = _gold_transfer(
            payer_id=to_character_id,
            payer=target,
            receiver_id=from_character_id,
            receiver=source,
            amount=amount,
        )
    else:
        action = "sell"
        amount = int(price * RULES.trade.sell_ratio)
        _require_gold(source, "player")
        _require_gold_at_least(target, amount, "merchant")
        gold_changes = _gold_transfer(
            payer_id=to_character_id,
            payer=target,
            receiver_id=from_character_id,
            receiver=source,
            amount=amount,
        )

    changes: list[GraphChange] = [
        RemoveEdgeChange(type="remove_edge", edge_id=placement.id),
        _carry_change(to_character_id, item_id),
        *gold_changes,
    ]
    return GraphItemTransferResult(
        changes=changes,
        item_id=item_id,
        from_node_id=from_character_id,
        to_node_id=to_character_id,
        action=action,
    )


def plan_item_equip(
    graph: Graph,
    character_id: str,
    item_id: str,
    slot: EquipSlot,
) -> GraphItemTransferResult:
    _require_item(graph, item_id)
    _require_character(graph, character_id)
    _require_slot(slot)
    placement = _require_placement(graph, item_id)
    owner_id = _placement_owner(placement)
    if owner_id != character_id:
        raise GraphTransferError(
            f"source mismatch for {item_id}: expected {character_id}, got {owner_id}"
        )

    occupied = _equipped_in_slot(graph, character_id, slot)
    already_equipped_in_slot = (
        placement.type == "equips"
        and placement.from_node_id == character_id
        and placement.to_node_id == item_id
        and placement.properties.get("slot") == slot
    )
    if already_equipped_in_slot:
        return GraphItemTransferResult(
            changes=[],
            item_id=item_id,
            from_node_id=character_id,
            to_node_id=character_id,
            action="equip",
        )

    changes: list[GraphChange] = [
        RemoveEdgeChange(type="remove_edge", edge_id=placement.id)
    ]
    if occupied is not None and occupied.id != placement.id:
        changes.append(RemoveEdgeChange(type="remove_edge", edge_id=occupied.id))
        changes.append(_carry_change(character_id, occupied.to_node_id))
    changes.append(_equip_change(character_id, item_id, slot))

    return GraphItemTransferResult(
        changes=changes,
        item_id=item_id,
        from_node_id=character_id,
        to_node_id=character_id,
        action="equip",
    )


def plan_item_unequip(
    graph: Graph,
    character_id: str,
    item_id: str,
) -> GraphItemTransferResult:
    _require_item(graph, item_id)
    _require_character(graph, character_id)
    edge = _equipped_item_edge(graph, character_id, item_id)
    if edge is None:
        raise GraphTransferError(f"item is not equipped by {character_id}: {item_id}")

    changes: list[GraphChange] = [
        RemoveEdgeChange(type="remove_edge", edge_id=edge.id),
        _carry_change(character_id, item_id),
    ]
    return GraphItemTransferResult(
        changes=changes,
        item_id=item_id,
        from_node_id=character_id,
        to_node_id=character_id,
        action="unequip",
    )


def _require_item(graph: Graph, item_id: str) -> GraphNode:
    node = graph.nodes.get(item_id)
    if node is None:
        raise GraphTransferError(f"missing item: {item_id}")
    if node.type != "item":
        raise GraphTransferError(f"node is not an item: {item_id}")
    return node


def _require_character(graph: Graph, character_id: str) -> GraphNode:
    node = graph.nodes.get(character_id)
    if node is None:
        raise GraphTransferError(f"missing character: {character_id}")
    if node.type != "character":
        raise GraphTransferError(f"node is not a character: {character_id}")
    return node


def _require_slot(slot: str) -> None:
    if slot not in _EQUIP_SLOTS:
        raise GraphTransferError(f"unknown equipment slot: {slot}")


def _require_trade_affinity(graph: Graph, merchant_id: str, player_id: str) -> None:
    affinity = _trade_affinity(graph, merchant_id, player_id)
    if affinity is not None and affinity < RULES.social.trade_threshold:
        raise GraphTransferError("affinity is too low to trade")


def _trade_affinity(graph: Graph, merchant_id: str, player_id: str) -> int | None:
    for edge in graph.edges.values():
        if edge.type != "relation":
            continue
        if {edge.from_node_id, edge.to_node_id} != {merchant_id, player_id}:
            continue
        affinity = edge.properties.get("affinity")
        if isinstance(affinity, int):
            return affinity
    return None


def _require_gold(node, label: str) -> int:
    gold = node.properties.get("gold")
    if not isinstance(gold, int):
        raise GraphTransferError(f"{label} has no gold property")
    return gold


def _require_gold_at_least(node, amount: int, label: str) -> int:
    gold = _require_gold(node, label)
    if gold < amount:
        raise GraphTransferError(f"{label} does not have enough gold: {gold} < {amount}")
    return gold


def _gold_transfer(
    *,
    payer_id: str,
    payer,
    receiver_id: str,
    receiver,
    amount: int,
) -> list[GraphChange]:
    if amount <= 0:
        return []
    return [
        SetNodePropertyChange(
            type="set_node_property",
            node_id=payer_id,
            path="gold",
            value=_require_gold(payer, "payer") - amount,
        ),
        SetNodePropertyChange(
            type="set_node_property",
            node_id=receiver_id,
            path="gold",
            value=_require_gold(receiver, "receiver") + amount,
        ),
    ]


def _require_placement(graph: Graph, item_id: str) -> GraphEdge:
    placement = _placement_edge(graph, item_id)
    if placement is None:
        raise GraphTransferError(f"item has no placement: {item_id}")
    return placement


def _placement_edge(graph: Graph, item_id: str) -> GraphEdge | None:
    for edge in graph.edges.values():
        if edge.type in _ITEM_FROM_PLACEMENT_TYPES and edge.from_node_id == item_id:
            return edge
        if edge.type in _ITEM_TO_PLACEMENT_TYPES and edge.to_node_id == item_id:
            return edge
    return None


def _placement_owner(edge: GraphEdge) -> str:
    if edge.type in _ITEM_FROM_PLACEMENT_TYPES:
        return edge.to_node_id
    return edge.from_node_id


def _int_value(value: object, *, default: int) -> int:
    return value if isinstance(value, int) else default


def _equipped_in_slot(
    graph: Graph,
    character_id: str,
    slot: EquipSlot,
) -> GraphEdge | None:
    for edge in edges_from(graph, character_id, "equips"):
        if edge.properties.get("slot") == slot:
            return edge
    return None


def _equipped_item_edge(
    graph: Graph,
    character_id: str,
    item_id: str,
) -> GraphEdge | None:
    for edge in edges_from(graph, character_id, "equips"):
        if edge.to_node_id == item_id:
            return edge
    return None


def _carry_change(character_id: str, item_id: str) -> AddEdgeChange:
    return AddEdgeChange(
        type="add_edge",
        edge=GraphEdge(
            id=f"carries:{character_id}:{item_id}",
            type="carries",
            from_node_id=character_id,
            to_node_id=item_id,
        ),
    )


def _equip_change(
    character_id: str,
    item_id: str,
    slot: EquipSlot,
) -> AddEdgeChange:
    return AddEdgeChange(
        type="add_edge",
        edge=GraphEdge(
            id=f"equips:{character_id}:{item_id}",
            type="equips",
            from_node_id=character_id,
            to_node_id=item_id,
            properties={"slot": slot},
        ),
    )
