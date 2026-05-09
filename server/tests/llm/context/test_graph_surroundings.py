from src.game.domain.graph import Graph, GraphEdge, GraphNode
from src.game.domain.progress import GameProgress
from src.game.runtime.state import GameRuntimeState
from src.llm.context.graph_surroundings import build_graph_surroundings


def _graph() -> Graph:
    return Graph(
        nodes={
            "town": GraphNode(
                id="town",
                type="location",
                properties={"name": "마을"},
            ),
            "forest": GraphNode(
                id="forest",
                type="location",
                properties={"name": "숲"},
            ),
            "player_01": GraphNode(
                id="player_01",
                type="character",
                properties={"name": "주인공", "alive": True},
            ),
            "goblin_01": GraphNode(
                id="goblin_01",
                type="character",
                properties={"name": "고블린", "alive": True},
            ),
            "hidden_01": GraphNode(
                id="hidden_01",
                type="character",
                properties={"name": "숨은 자", "alive": True},
            ),
            "potion_01": GraphNode(
                id="potion_01",
                type="item",
                properties={"name": "치유 물약", "kind": "consumable"},
            ),
        },
        edges={
            "located_at:player_01:town": GraphEdge(
                id="located_at:player_01:town",
                type="located_at",
                from_node_id="player_01",
                to_node_id="town",
            ),
            "located_at:goblin_01:town": GraphEdge(
                id="located_at:goblin_01:town",
                type="located_at",
                from_node_id="goblin_01",
                to_node_id="town",
            ),
            "hidden_at:hidden_01:town": GraphEdge(
                id="hidden_at:hidden_01:town",
                type="hidden_at",
                from_node_id="hidden_01",
                to_node_id="town",
            ),
            "connects_to:town:forest": GraphEdge(
                id="connects_to:town:forest",
                type="connects_to",
                from_node_id="town",
                to_node_id="forest",
            ),
            "carries:player_01:potion_01": GraphEdge(
                id="carries:player_01:potion_01",
                type="carries",
                from_node_id="player_01",
                to_node_id="potion_01",
            ),
        },
    )


def test_graph_surroundings_exposes_grounded_visible_ids():
    runtime = GameRuntimeState(
        graph=_graph(),
        progress=GameProgress(game_id="game-1", player_id="player_01"),
    )

    surroundings = build_graph_surroundings(runtime)

    assert surroundings["location"] == {"id": "town", "name": "마을"}
    assert {"id": "player_01", "name": "주인공", "type": "player"} in surroundings[
        "entities"
    ]
    assert {"id": "goblin_01", "name": "고블린", "type": "npc"} in surroundings[
        "entities"
    ]
    assert {"id": "forest", "name": "숲", "type": "connection"} in surroundings[
        "entities"
    ]
    assert all(entry["id"] != "hidden_01" for entry in surroundings["entities"])
    assert surroundings["inventory"] == [
        {"id": "potion_01", "name": "치유 물약", "kind": "consumable"}
    ]
    assert surroundings["in_combat"] is False
