from src.game.domain.graph import Graph, GraphEdge, GraphNode
from src.game.domain.graph.apply import apply_graph_changes
from src.game.domain.graph.query import location_of
from src.game.engines.graph.arrival import plan_arrival_branch_effects


def _graph() -> Graph:
    return Graph(
        nodes={
            "player_01": GraphNode(id="player_01", type="character"),
            "npc_eli": GraphNode(id="npc_eli", type="character"),
            "black_token": GraphNode(
                id="black_token",
                type="item",
                properties={"name": "검은 증표", "black_weight": True},
            ),
            "white_harbor": GraphNode(
                id="white_harbor",
                type="location",
                properties={
                    "arrival_branches": [
                        {
                            "inventory_item_property": "black_weight",
                            "text": "엘리는 물보라 뒤로 사라집니다.",
                            "else_text": "엘리는 함께 항구에 도착합니다.",
                            "remove_companions": ["npc_eli"],
                            "hide_characters": ["npc_eli"],
                        }
                    ]
                },
            ),
        },
        edges={
            "located_at:player_01:white_harbor": GraphEdge(
                id="located_at:player_01:white_harbor",
                type="located_at",
                from_node_id="player_01",
                to_node_id="white_harbor",
            ),
            "located_at:npc_eli:white_harbor": GraphEdge(
                id="located_at:npc_eli:white_harbor",
                type="located_at",
                from_node_id="npc_eli",
                to_node_id="white_harbor",
            ),
            "has_companion:player_01:npc_eli": GraphEdge(
                id="has_companion:player_01:npc_eli",
                type="has_companion",
                from_node_id="player_01",
                to_node_id="npc_eli",
            ),
            "carries:player_01:black_token": GraphEdge(
                id="carries:player_01:black_token",
                type="carries",
                from_node_id="player_01",
                to_node_id="black_token",
            ),
        },
    )


def test_arrival_branch_can_remove_and_hide_a_companion():
    graph = _graph()

    result = plan_arrival_branch_effects(graph, "player_01", "white_harbor")
    changed = apply_graph_changes(graph, result.changes)

    assert result.hidden_character_ids == ["npc_eli"]
    assert "has_companion:player_01:npc_eli" not in changed.edges
    assert location_of(changed, "npc_eli") is None


def test_arrival_branch_skips_effects_when_condition_is_not_met():
    graph = _graph()
    graph.edges.pop("carries:player_01:black_token")

    result = plan_arrival_branch_effects(graph, "player_01", "white_harbor")

    assert result.changes == []
    assert result.hidden_character_ids == []
