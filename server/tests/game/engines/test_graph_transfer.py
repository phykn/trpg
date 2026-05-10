import pytest

from src.game.domain.graph import Graph, GraphEdge, GraphNode, apply_graph_change
from src.game.engines.graph_transfer import (
    GraphTransferError,
    plan_item_equip,
    plan_item_transfer,
    plan_item_unequip,
)


def _graph() -> Graph:
    return Graph(
        nodes={
            "player_01": GraphNode(id="player_01", type="character"),
            "npc_01": GraphNode(id="npc_01", type="character"),
            "potion": GraphNode(id="potion", type="item"),
            "axe": GraphNode(id="axe", type="item"),
            "shield": GraphNode(id="shield", type="item"),
            "sword": GraphNode(id="sword", type="item"),
            "dagger": GraphNode(id="dagger", type="item"),
            "armor": GraphNode(id="armor", type="item"),
        },
        edges={
            "carries:npc_01:potion": GraphEdge(
                id="carries:npc_01:potion",
                type="carries",
                from_node_id="npc_01",
                to_node_id="potion",
            ),
            "equips:npc_01:axe": GraphEdge(
                id="equips:npc_01:axe",
                type="equips",
                from_node_id="npc_01",
                to_node_id="axe",
                properties={"slot": "weapon"},
            ),
            "carries:player_01:shield": GraphEdge(
                id="carries:player_01:shield",
                type="carries",
                from_node_id="player_01",
                to_node_id="shield",
            ),
            "carries:player_01:sword": GraphEdge(
                id="carries:player_01:sword",
                type="carries",
                from_node_id="player_01",
                to_node_id="sword",
            ),
            "equips:player_01:dagger": GraphEdge(
                id="equips:player_01:dagger",
                type="equips",
                from_node_id="player_01",
                to_node_id="dagger",
                properties={"slot": "weapon"},
            ),
            "equips:player_01:armor": GraphEdge(
                id="equips:player_01:armor",
                type="equips",
                from_node_id="player_01",
                to_node_id="armor",
                properties={"slot": "armor"},
            ),
        },
    )


def _apply_all(graph: Graph, changes) -> Graph:
    for change in changes:
        graph = apply_graph_change(graph, change)
    return graph


def test_transfer_moves_carried_item_between_characters():
    result = plan_item_transfer(
        _graph(),
        "potion",
        to_character_id="player_01",
        from_node_id="npc_01",
    )
    changed = _apply_all(_graph(), result.changes)

    assert result.item_id == "potion"
    assert "carries:npc_01:potion" not in changed.edges
    assert changed.edges["carries:player_01:potion"].from_node_id == "player_01"


def test_transfer_from_equipment_unequips_source_item():
    result = plan_item_transfer(
        _graph(),
        "axe",
        to_character_id="player_01",
        from_node_id="npc_01",
    )
    changed = _apply_all(_graph(), result.changes)

    assert "equips:npc_01:axe" not in changed.edges
    assert changed.edges["carries:player_01:axe"].to_node_id == "axe"


def test_equip_carried_item_adds_slot_edge():
    result = plan_item_equip(_graph(), "player_01", "shield", "accessory")
    changed = _apply_all(_graph(), result.changes)

    assert "carries:player_01:shield" not in changed.edges
    assert changed.edges["equips:player_01:shield"].properties == {"slot": "accessory"}


def test_equip_replaces_existing_item_in_slot():
    result = plan_item_equip(_graph(), "player_01", "sword", "weapon")
    changed = _apply_all(_graph(), result.changes)

    assert "equips:player_01:dagger" not in changed.edges
    assert "carries:player_01:sword" not in changed.edges
    assert changed.edges["carries:player_01:dagger"].to_node_id == "dagger"
    assert changed.edges["equips:player_01:sword"].properties["slot"] == "weapon"


def test_unequip_moves_item_back_to_inventory():
    result = plan_item_unequip(_graph(), "player_01", "armor")
    changed = _apply_all(_graph(), result.changes)

    assert "equips:player_01:armor" not in changed.edges
    assert changed.edges["carries:player_01:armor"].to_node_id == "armor"


def test_transfer_rejects_wrong_source_and_missing_ids():
    with pytest.raises(GraphTransferError, match="source"):
        plan_item_transfer(
            _graph(),
            "potion",
            to_character_id="player_01",
            from_node_id="player_01",
        )
    with pytest.raises(GraphTransferError, match="missing item"):
        plan_item_transfer(_graph(), "ghost_item", to_character_id="player_01")
    with pytest.raises(GraphTransferError, match="missing character"):
        plan_item_transfer(_graph(), "potion", to_character_id="ghost")


def test_transfer_changes_are_individually_valid_graph_changes():
    graph = _graph()
    result = plan_item_equip(graph, "player_01", "sword", "weapon")

    for change in result.changes:
        graph = apply_graph_change(graph, change)

    assert graph.edges["equips:player_01:sword"].to_node_id == "sword"
