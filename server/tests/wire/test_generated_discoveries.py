from src.game.domain.content import RuntimeContent
from src.game.domain.graph import Graph, GraphEdge, GraphNode
from src.game.domain.progress import GameProgress
from src.game.runtime import GameRuntimeState
from src.wire.graph.to_front import graph_to_front_state


def _runtime() -> GameRuntimeState:
    return GameRuntimeState(
        graph=Graph(
            nodes={
                "player_01": GraphNode(
                    id="player_01",
                    type="character",
                    properties={
                        "name": "당신",
                        "level": 1,
                        "gold": 0,
                        "xp_pool": 0,
                        "hp": 5,
                        "max_hp": 5,
                        "mp": 5,
                        "max_mp": 5,
                        "stats": {
                            "body": 1,
                            "agility": 1,
                            "mind": 1,
                            "presence": 1,
                        },
                    },
                ),
                "loc_fog_harbor": GraphNode(
                    id="loc_fog_harbor",
                    type="location",
                    properties={"name": "안개 항구", "description": "안개 낀 항구입니다."},
                ),
                "mem_tore_ticket_001": GraphNode(
                    id="mem_tore_ticket_001",
                    type="knowledge",
                    properties={
                        "kind": "memory",
                        "title": "당신은 표를 찢었습니다.",
                        "summary": "당신은 표를 찢었습니다.",
                        "visibility": "player",
                        "stability": "campaign",
                        "turn_id": 3,
                    },
                ),
                "clue_wet_ticket_001": GraphNode(
                    id="clue_wet_ticket_001",
                    type="knowledge",
                    properties={
                        "kind": "clue",
                        "title": "젖은 승선표",
                        "summary": "표가 젖어 있습니다.",
                        "visibility": "player",
                        "stability": "scene",
                        "turn_id": 4,
                    },
                ),
                "clue_private": GraphNode(
                    id="clue_private",
                    type="knowledge",
                    properties={
                        "kind": "clue",
                        "title": "비공개",
                        "summary": "보이지 않습니다.",
                        "visibility": "private",
                    },
                ),
            },
            edges={
                "located_at:player_01:loc_fog_harbor": GraphEdge(
                    id="located_at:player_01:loc_fog_harbor",
                    type="located_at",
                    from_node_id="player_01",
                    to_node_id="loc_fog_harbor",
                ),
                "has_knowledge:player_01:mem_tore_ticket_001": GraphEdge(
                    id="has_knowledge:player_01:mem_tore_ticket_001",
                    type="has_knowledge",
                    from_node_id="player_01",
                    to_node_id="mem_tore_ticket_001",
                ),
                "has_knowledge:loc_fog_harbor:clue_wet_ticket_001": GraphEdge(
                    id="has_knowledge:loc_fog_harbor:clue_wet_ticket_001",
                    type="has_knowledge",
                    from_node_id="loc_fog_harbor",
                    to_node_id="clue_wet_ticket_001",
                ),
                "has_knowledge:loc_fog_harbor:clue_private": GraphEdge(
                    id="has_knowledge:loc_fog_harbor:clue_private",
                    type="has_knowledge",
                    from_node_id="loc_fog_harbor",
                    to_node_id="clue_private",
                ),
            },
        ),
        content=RuntimeContent(),
        progress=GameProgress(game_id="game-1", player_id="player_01"),
    )


def test_graph_front_state_projects_player_visible_discoveries() -> None:
    payload = graph_to_front_state(_runtime())

    assert [entry.id for entry in payload.discoveries.memories] == [
        "mem_tore_ticket_001"
    ]
    assert [entry.id for entry in payload.discoveries.clues] == [
        "clue_wet_ticket_001"
    ]
    assert payload.discoveries.clues[0].title == "젖은 승선표"


def test_graph_front_state_serializes_discoveries_as_camel_payload() -> None:
    payload = graph_to_front_state(_runtime()).model_dump(mode="json", by_alias=True)

    assert payload["discoveries"]["memories"][0]["turnId"] == 3
    assert payload["discoveries"]["clues"][0]["stability"] == "scene"
