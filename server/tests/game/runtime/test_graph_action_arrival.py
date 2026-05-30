from src.game.domain.action import Action
from src.game.domain.graph import Graph, GraphEdge, GraphNode
from src.game.domain.graph.query import location_of
from src.game.domain.progress import GameProgress
from src.game.runtime.action.dispatch import dispatch_graph_action
from src.game.runtime.state import GameRuntimeState


def test_move_applies_arrival_branch_effects_and_clears_hidden_active_subject():
    runtime = GameRuntimeState(
        graph=Graph(
            nodes={
                "player_01": GraphNode(
                    id="player_01",
                    type="character",
                    properties={"visited_location_ids": ["white_sea"]},
                ),
                "npc_eli": GraphNode(
                    id="npc_eli",
                    type="character",
                    properties={"visited_location_ids": ["white_sea"]},
                ),
                "black_token": GraphNode(
                    id="black_token",
                    type="item",
                    properties={"black_weight": True},
                ),
                "white_sea": GraphNode(id="white_sea", type="location"),
                "white_harbor": GraphNode(
                    id="white_harbor",
                    type="location",
                    properties={
                        "arrival_branches": [
                            {
                                "inventory_item_property": "black_weight",
                                "text": "엘리는 물보라 뒤로 사라집니다.",
                                "else_text": "엘리는 함께 도착합니다.",
                                "remove_companions": ["npc_eli"],
                                "hide_characters": ["npc_eli"],
                            }
                        ]
                    },
                ),
            },
            edges={
                "located_at:player_01:white_sea": GraphEdge(
                    id="located_at:player_01:white_sea",
                    type="located_at",
                    from_node_id="player_01",
                    to_node_id="white_sea",
                ),
                "located_at:npc_eli:white_sea": GraphEdge(
                    id="located_at:npc_eli:white_sea",
                    type="located_at",
                    from_node_id="npc_eli",
                    to_node_id="white_sea",
                ),
                "connects_to:white_sea:white_harbor": GraphEdge(
                    id="connects_to:white_sea:white_harbor",
                    type="connects_to",
                    from_node_id="white_sea",
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
        ),
        progress=GameProgress(
            game_id="game-1",
            player_id="player_01",
            active_subject_id="npc_eli",
        ),
    )

    result = dispatch_graph_action(runtime, Action(verb="move", to="white_harbor"))

    assert location_of(result.runtime.graph, "player_01") == "white_harbor"
    assert location_of(result.runtime.graph, "npc_eli") is None
    assert "has_companion:player_01:npc_eli" not in result.runtime.graph.edges
    assert result.runtime.progress.active_subject_id is None
