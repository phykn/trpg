import pytest
from pydantic import ValidationError

from src.game.domain.graph import (
    Graph,
    GraphEdge,
    GraphInvariantError,
    GraphNode,
)
from src.game.domain.graph.apply import apply_graph_change, parse_graph_change


def test_graph_edge_accepts_contract_aliases():
    edge = GraphEdge.model_validate(
        {
            "id": "edge_1",
            "type": "located_at",
            "from": "player_01",
            "to": "plaza_01",
            "properties": {"visible": True},
        }
    )

    assert edge.from_node_id == "player_01"
    assert edge.to_node_id == "plaza_01"
    assert edge.model_dump(by_alias=True)["from"] == "player_01"


def test_add_edge_requires_existing_nodes():
    graph = Graph(
        nodes={
            "player_01": GraphNode(id="player_01", type="character"),
            "plaza_01": GraphNode(id="plaza_01", type="location"),
        }
    )

    changed = apply_graph_change(
        graph,
        parse_graph_change(
            {
                "type": "add_edge",
                "edge": {
                    "id": "player_at_plaza",
                    "type": "located_at",
                    "from": "player_01",
                    "to": "plaza_01",
                },
            }
        ),
    )

    assert changed.edges["player_at_plaza"].to_node_id == "plaza_01"

    with pytest.raises(GraphInvariantError, match="missing node"):
        apply_graph_change(
            graph,
            parse_graph_change(
                {
                    "type": "add_edge",
                    "edge": {
                        "id": "player_at_void",
                        "type": "located_at",
                        "from": "player_01",
                        "to": "void_01",
                    },
                }
            ),
        )


def test_item_has_only_one_placement_edge():
    graph = Graph(
        nodes={
            "player_01": GraphNode(id="player_01", type="character"),
            "potion_01": GraphNode(id="potion_01", type="item"),
            "plaza_01": GraphNode(id="plaza_01", type="location"),
        }
    )
    carried = apply_graph_change(
        graph,
        parse_graph_change(
            {
                "type": "add_edge",
                "edge": {
                    "id": "player_carries_potion",
                    "type": "carries",
                    "from": "player_01",
                    "to": "potion_01",
                },
            }
        ),
    )

    with pytest.raises(GraphInvariantError, match="item placement"):
        apply_graph_change(
            carried,
            parse_graph_change(
                {
                    "type": "add_edge",
                    "edge": {
                        "id": "potion_at_plaza",
                        "type": "located_at",
                        "from": "potion_01",
                        "to": "plaza_01",
                    },
                }
            ),
        )


def test_remove_edge_is_allowed_but_remove_node_is_not():
    graph = Graph(
        nodes={
            "player_01": GraphNode(id="player_01", type="character"),
            "plaza_01": GraphNode(id="plaza_01", type="location"),
        },
        edges={
            "player_at_plaza": GraphEdge(
                id="player_at_plaza",
                type="located_at",
                from_node_id="player_01",
                to_node_id="plaza_01",
            )
        },
    )

    changed = apply_graph_change(
        graph, parse_graph_change({"type": "remove_edge", "edge_id": "player_at_plaza"})
    )

    assert changed.edges == {}
    with pytest.raises(ValidationError):
        parse_graph_change({"type": "remove_node", "node_id": "player_01"})


def test_set_node_property_updates_copy():
    graph = Graph(
        nodes={
            "player_01": GraphNode(
                id="player_01",
                type="character",
                properties={"resources": {"hp": 8, "mp": 3}},
            )
        }
    )

    changed = apply_graph_change(
        graph,
        parse_graph_change(
            {
                "type": "set_node_property",
                "node_id": "player_01",
                "path": "resources.hp",
                "value": 4,
            }
        ),
    )

    assert graph.nodes["player_01"].properties["resources"]["hp"] == 8
    assert changed.nodes["player_01"].properties["resources"]["hp"] == 4


def test_graph_accepts_progression_structure_edges():
    graph = Graph(
        nodes={
            "player_01": GraphNode(id="player_01", type="character"),
            "human": GraphNode(id="human", type="race"),
            "slash": GraphNode(id="slash", type="skill"),
            "quest_01": GraphNode(id="quest_01", type="quest"),
            "chapter_01": GraphNode(id="chapter_01", type="chapter"),
        }
    )

    for edge in (
        {
            "id": "belongs_to_race:player_01:human",
            "type": "belongs_to_race",
            "from": "player_01",
            "to": "human",
        },
        {
            "id": "grants_skill:human:slash",
            "type": "grants_skill",
            "from": "human",
            "to": "slash",
        },
        {
            "id": "part_of_chapter:quest_01:chapter_01",
            "type": "part_of_chapter",
            "from": "quest_01",
            "to": "chapter_01",
        },
    ):
        graph = apply_graph_change(
            graph,
            parse_graph_change({"type": "add_edge", "edge": edge}),
        )

    edge_types = {
        (edge.type, edge.from_node_id, edge.to_node_id) for edge in graph.edges.values()
    }

    assert ("belongs_to_race", "player_01", "human") in edge_types
    assert ("grants_skill", "human", "slash") in edge_types
    assert ("part_of_chapter", "quest_01", "chapter_01") in edge_types


def test_graph_constructor_validates_loaded_edge_invariants():
    with pytest.raises(ValidationError, match="missing node"):
        Graph(
            nodes={"player_01": GraphNode(id="player_01", type="character")},
            edges={
                "player_at_void": GraphEdge(
                    id="player_at_void",
                    type="located_at",
                    from_node_id="player_01",
                    to_node_id="void_01",
                )
            },
        )

    with pytest.raises(ValidationError, match="item placement conflict"):
        Graph(
            nodes={
                "player_01": GraphNode(id="player_01", type="character"),
                "potion_01": GraphNode(id="potion_01", type="item"),
                "plaza_01": GraphNode(id="plaza_01", type="location"),
            },
            edges={
                "player_carries_potion": GraphEdge(
                    id="player_carries_potion",
                    type="carries",
                    from_node_id="player_01",
                    to_node_id="potion_01",
                ),
                "potion_at_plaza": GraphEdge(
                    id="potion_at_plaza",
                    type="located_at",
                    from_node_id="potion_01",
                    to_node_id="plaza_01",
                ),
            },
        )


def test_graph_constructor_rejects_non_player_equipment():
    with pytest.raises(ValidationError, match="equips owner must be player"):
        Graph(
            nodes={
                "npc_01": GraphNode(id="npc_01", type="character"),
                "sword_01": GraphNode(id="sword_01", type="item"),
            },
            edges={
                "equips:npc_01:sword_01": GraphEdge(
                    id="equips:npc_01:sword_01",
                    type="equips",
                    from_node_id="npc_01",
                    to_node_id="sword_01",
                )
            },
        )


def test_quest_trigger_target_must_exist_in_graph():
    with pytest.raises(ValidationError, match="quest trigger target missing"):
        Graph(
            nodes={
                "quest_01": GraphNode(
                    id="quest_01",
                    type="quest",
                    properties={
                        "triggers": [
                            {
                                "id": "trigger_01",
                                "type": "character_death",
                                "target_id": "ghost_01",
                            }
                        ]
                    },
                )
            }
        )
