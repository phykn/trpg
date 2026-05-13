from src.game.domain.graph import Graph, GraphEdge, GraphNode, apply_graph_change
from src.game.engines.graph_quest_generation import plan_missing_quest_offer


def _character(character_id: str) -> GraphNode:
    return GraphNode(
        id=character_id,
        type="character",
        properties={
            "name": character_id,
            "hp": 30,
            "max_hp": 30,
            "mp": 10,
            "max_mp": 10,
            "alive": True,
            "stats": {"body": 3, "agility": 2, "mind": 1, "presence": 0},
        },
    )


def _graph_without_work() -> Graph:
    return Graph(
        nodes={
            "town": GraphNode(id="town", type="location", properties={"name": "마을"}),
            "player_01": _character("player_01"),
        },
        edges={
            "located_at:player_01:town": GraphEdge(
                id="located_at:player_01:town",
                type="located_at",
                from_node_id="player_01",
                to_node_id="town",
            ),
        },
    )


def _graph_with_visible_pending_offer() -> Graph:
    graph = _graph_without_work()
    graph.nodes["giver_01"] = _character("giver_01")
    graph.nodes["quest_existing"] = GraphNode(
        id="quest_existing",
        type="quest",
        properties={"status": "pending"},
    )
    graph.edges["located_at:giver_01:town"] = GraphEdge(
        id="located_at:giver_01:town",
        type="located_at",
        from_node_id="giver_01",
        to_node_id="town",
    )
    graph.edges["gives_quest:giver_01:quest_existing"] = GraphEdge(
        id="gives_quest:giver_01:quest_existing",
        type="gives_quest",
        from_node_id="giver_01",
        to_node_id="quest_existing",
    )
    return Graph.model_validate(graph.model_dump())


def _apply_all(graph: Graph, changes) -> Graph:
    current = graph
    for change in changes:
        current = apply_graph_change(current, change)
    return current


def test_generates_pending_hunt_offer_when_no_work_exists():
    result = plan_missing_quest_offer(_graph_without_work(), "player_01")

    assert result is not None
    assert result.template == "hunt"
    assert result.generated_ids == {
        "quest": "auto_quest_001",
        "giver": "auto_giver_001",
        "enemy": "auto_enemy_001",
        "reward": "auto_reward_001",
    }
    assert {change.type for change in result.changes} == {"add_node", "add_edge"}
    graph = _apply_all(_graph_without_work(), result.changes)
    quest = graph.nodes[result.quest_id]
    enemy = graph.nodes["auto_enemy_001"]
    giver = graph.nodes["auto_giver_001"]
    assert quest.type == "quest"
    assert "title" not in quest.properties
    assert "summary" not in quest.properties
    assert "name" not in enemy.properties
    assert quest.properties["status"] == "pending"
    assert quest.properties["triggers"][0]["type"] == "character_defeat"
    assert "name" not in quest.properties["triggers"][0]
    assert quest.properties["triggers_met"] == [False]
    assert result.content.quests[result.quest_id]["title"]
    assert result.content.quests[result.quest_id]["triggers"][0]["name"]
    assert result.content.characters["auto_enemy_001"]["name"]
    assert enemy.properties["combat_behavior"] is not None
    for key in ("hp", "max_hp", "mp", "max_mp"):
        assert key not in enemy.properties
        assert key not in giver.properties
    assert any(
        edge.type == "gives_quest" and edge.to_node_id == result.quest_id
        for edge in graph.edges.values()
    )
    assert any(
        edge.type == "target_of" and edge.to_node_id == result.quest_id
        for edge in graph.edges.values()
    )
    assert any(
        edge.type == "reward_of" and edge.to_node_id == result.quest_id
        for edge in graph.edges.values()
    )


def test_noops_when_active_quest_exists():
    graph = _graph_without_work()
    graph.nodes["quest_existing"] = GraphNode(
        id="quest_existing",
        type="quest",
        properties={"status": "active"},
    )

    assert plan_missing_quest_offer(graph, "player_01") is None


def test_noops_when_visible_offer_exists():
    graph = _graph_with_visible_pending_offer()

    assert plan_missing_quest_offer(graph, "player_01") is None
