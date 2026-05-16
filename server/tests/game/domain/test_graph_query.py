import pytest

from src.game.domain.graph import Graph, GraphEdge, GraphInvariantError, GraphNode
from src.game.domain.graph.query import (
    GraphIndex,
    characters_at,
    edges_from,
    edges_to,
    equipment_of,
    inventory_of,
    items_at,
    known_skills_of,
    location_of,
    nodes_of_type,
    quest_requirements_of,
    quest_reward_items_of,
    quest_targets_of,
    quests_in_chapter,
    race_of,
    require_node,
    source_nodes,
    target_nodes,
)


def test_graph_query_filters_edges_and_resolves_neighbor_nodes():
    graph = Graph(
        nodes={
            "player": GraphNode(
                id="player",
                type="character",
                properties={"is_player": True},
            ),
            "elder": GraphNode(id="elder", type="character"),
            "town": GraphNode(id="town", type="location"),
            "potion": GraphNode(id="potion", type="item"),
        },
        edges={
            "located_at:player:town": GraphEdge(
                id="located_at:player:town",
                type="located_at",
                from_node_id="player",
                to_node_id="town",
            ),
            "carries:player:potion": GraphEdge(
                id="carries:player:potion",
                type="carries",
                from_node_id="player",
                to_node_id="potion",
            ),
            "relation:player:elder": GraphEdge(
                id="relation:player:elder",
                type="relation",
                from_node_id="player",
                to_node_id="elder",
                properties={"affinity": 10},
            ),
        },
    )

    assert [node.id for node in nodes_of_type(graph, "character")] == [
        "player",
        "elder",
    ]
    assert [edge.id for edge in edges_from(graph, "player", "carries")] == [
        "carries:player:potion"
    ]
    assert [edge.id for edge in edges_to(graph, "town", "located_at")] == [
        "located_at:player:town"
    ]
    assert [node.id for node in target_nodes(graph, "player", "carries")] == ["potion"]
    assert [node.id for node in source_nodes(graph, "town", "located_at")] == ["player"]

    assert require_node(graph, "elder").id == "elder"
    with pytest.raises(GraphInvariantError, match="missing node"):
        require_node(graph, "missing")


def test_contract_semantic_queries_read_documented_edges():
    graph = Graph(
        nodes={
            "player": GraphNode(
                id="player",
                type="character",
                properties={"is_player": True},
            ),
            "elder": GraphNode(id="elder", type="character"),
            "town": GraphNode(id="town", type="location"),
            "potion": GraphNode(id="potion", type="item"),
            "hidden_key": GraphNode(id="hidden_key", type="item"),
            "sword": GraphNode(id="sword", type="item"),
            "reward_gem": GraphNode(id="reward_gem", type="item"),
            "human": GraphNode(id="human", type="race"),
            "slash": GraphNode(id="slash", type="skill"),
            "quest": GraphNode(id="quest", type="quest"),
            "chapter": GraphNode(id="chapter", type="chapter"),
        },
        edges={
            "located_at:player:town": GraphEdge(
                id="located_at:player:town",
                type="located_at",
                from_node_id="player",
                to_node_id="town",
            ),
            "located_at:potion:town": GraphEdge(
                id="located_at:potion:town",
                type="located_at",
                from_node_id="potion",
                to_node_id="town",
            ),
            "hidden_at:hidden_key:town": GraphEdge(
                id="hidden_at:hidden_key:town",
                type="hidden_at",
                from_node_id="hidden_key",
                to_node_id="town",
            ),
            "equips:player:sword": GraphEdge(
                id="equips:player:sword",
                type="equips",
                from_node_id="player",
                to_node_id="sword",
                properties={"slot": "weapon"},
            ),
            "belongs_to_race:player:human": GraphEdge(
                id="belongs_to_race:player:human",
                type="belongs_to_race",
                from_node_id="player",
                to_node_id="human",
            ),
            "knows_skill:player:slash": GraphEdge(
                id="knows_skill:player:slash",
                type="knows_skill",
                from_node_id="player",
                to_node_id="slash",
            ),
            "target_of:elder:quest": GraphEdge(
                id="target_of:elder:quest",
                type="target_of",
                from_node_id="elder",
                to_node_id="quest",
            ),
            "required_by:hidden_key:quest": GraphEdge(
                id="required_by:hidden_key:quest",
                type="required_by",
                from_node_id="hidden_key",
                to_node_id="quest",
            ),
            "reward_of:reward_gem:quest": GraphEdge(
                id="reward_of:reward_gem:quest",
                type="reward_of",
                from_node_id="reward_gem",
                to_node_id="quest",
            ),
            "part_of_chapter:quest:chapter": GraphEdge(
                id="part_of_chapter:quest:chapter",
                type="part_of_chapter",
                from_node_id="quest",
                to_node_id="chapter",
            ),
        },
    )

    assert location_of(graph, "player") == "town"
    assert characters_at(graph, "town") == ["player"]
    assert items_at(graph, "town") == ["potion"]
    assert items_at(graph, "town", include_hidden=True) == ["potion", "hidden_key"]
    assert inventory_of(graph, "player") == []
    assert [edge.to_node_id for edge in equipment_of(graph, "player")] == ["sword"]
    assert race_of(graph, "player") == "human"
    assert [edge.to_node_id for edge in known_skills_of(graph, "player")] == ["slash"]
    assert quest_targets_of(graph, "quest") == ["elder"]
    assert quest_requirements_of(graph, "quest") == ["hidden_key"]
    assert quest_reward_items_of(graph, "quest") == ["reward_gem"]
    assert quests_in_chapter(graph, "chapter") == ["quest"]

    index = GraphIndex(graph)
    assert edges_from(index, "player", "located_at") == edges_from(
        graph, "player", "located_at"
    )
    assert edges_to(index, "town", "located_at") == edges_to(
        graph, "town", "located_at"
    )
    assert characters_at(index, "town") == characters_at(graph, "town")
    assert inventory_of(index, "player") == inventory_of(graph, "player")
