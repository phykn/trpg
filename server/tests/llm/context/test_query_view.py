from src.game.domain.graph import Graph, GraphEdge, GraphNode
from src.game.domain.progress import GameProgress
from src.game.runtime import GameRuntimeState
from src.llm.context.query_view import build_query_context_view


def _character(
    character_id: str,
    *,
    hp: int = 10,
    max_hp: int = 10,
    xp_reward: int = 0,
    status: list[str] | None = None,
) -> GraphNode:
    return GraphNode(
        id=character_id,
        type="character",
        properties={
            "name": character_id,
            "hp": hp,
            "max_hp": max_hp,
            "mp": 0,
            "max_mp": 0,
            "alive": True,
            "xp_reward": xp_reward,
            "stats": {"body": 1, "agility": 1, "mind": 1, "presence": 1},
            "status": status or [],
        },
    )


def _runtime() -> GameRuntimeState:
    graph = Graph(
        nodes={
            "town": GraphNode(id="town", type="location", properties={"name": "마을"}),
            "player_01": _character("player_01"),
            "enemy_live": _character("enemy_live", xp_reward=5),
            "enemy_defeated": _character(
                "enemy_defeated",
                hp=0,
                xp_reward=5,
                status=["defeated"],
            ),
        },
        edges={
            "located_at:player_01:town": GraphEdge(
                id="located_at:player_01:town",
                type="located_at",
                from_node_id="player_01",
                to_node_id="town",
            ),
            "located_at:enemy_live:town": GraphEdge(
                id="located_at:enemy_live:town",
                type="located_at",
                from_node_id="enemy_live",
                to_node_id="town",
            ),
            "located_at:enemy_defeated:town": GraphEdge(
                id="located_at:enemy_defeated:town",
                type="located_at",
                from_node_id="enemy_defeated",
                to_node_id="town",
            ),
        },
    )
    return GameRuntimeState(
        graph=graph,
        progress=GameProgress(game_id="game-1", player_id="player_01"),
        log_entries=[],
    )


def _grounded_graph() -> Graph:
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
                properties={"name": "주인공", "alive": True, "hp": 10, "max_hp": 10},
            ),
            "goblin_01": GraphNode(
                id="goblin_01",
                type="character",
                properties={"name": "고블린", "alive": True, "hp": 10, "max_hp": 10},
            ),
            "hidden_01": GraphNode(
                id="hidden_01",
                type="character",
                properties={"name": "숨은 자", "alive": True, "hp": 10, "max_hp": 10},
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


def test_query_context_view_exposes_grounded_visible_ids():
    runtime = GameRuntimeState(
        graph=_grounded_graph(),
        progress=GameProgress(game_id="game-1", player_id="player_01"),
    )

    surroundings = build_query_context_view(runtime)

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


def test_query_context_view_includes_location_description():
    graph = _grounded_graph()
    graph.nodes["town"].properties["description"] = "돌길과 낮은 담장이 이어집니다."
    runtime = GameRuntimeState(
        graph=graph,
        progress=GameProgress(game_id="game-1", player_id="player_01"),
    )

    surroundings = build_query_context_view(runtime)

    assert surroundings["location"] == {
        "id": "town",
        "name": "마을",
        "description": "돌길과 낮은 담장이 이어집니다.",
    }


def test_query_context_view_marks_enemies_and_omits_defeated_characters():
    payload = build_query_context_view(_runtime())

    entities = payload["entities"]
    assert {"id": "enemy_live", "name": "enemy_live", "type": "enemy"} in entities
    assert all(entity["id"] != "enemy_defeated" for entity in entities)
