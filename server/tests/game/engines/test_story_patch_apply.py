from src.game.domain.graph import AddEdgeChange, AddNodeChange, Graph, GraphNode
from src.game.domain.story_patch import StoryWriteResponse
from src.game.engines.story_patch_apply import story_patches_to_graph_changes


def _graph() -> Graph:
    return Graph(
        nodes={
            "player_01": GraphNode(
                id="player_01",
                type="character",
                properties={"name": "당신", "is_player": True},
            ),
            "loc_fog_harbor": GraphNode(
                id="loc_fog_harbor",
                type="location",
                properties={"name": "안개 항구"},
            ),
        }
    )


def test_apply_converts_memory_to_player_knowledge() -> None:
    response = StoryWriteResponse.model_validate(
        {
            "reason": "remembered",
            "patches": [
                {
                    "op": "add_memory",
                    "id": "mem_tore_ticket_001",
                    "summary": "당신은 표를 찢었습니다.",
                }
            ],
        }
    )

    changes = story_patches_to_graph_changes(
        response.patches,
        graph=_graph(),
        player_id="player_01",
        turn_id=3,
    )

    assert isinstance(changes[0], AddNodeChange)
    assert changes[0].node.id == "mem_tore_ticket_001"
    assert changes[0].node.type == "knowledge"
    assert changes[0].node.properties["kind"] == "memory"
    assert changes[0].node.properties["turn_id"] == 3
    assert isinstance(changes[1], AddEdgeChange)
    assert changes[1].edge.type == "has_knowledge"
    assert changes[1].edge.from_node_id == "player_01"


def test_apply_converts_clue_to_anchor_knowledge() -> None:
    response = StoryWriteResponse.model_validate(
        {
            "reason": "found",
            "patches": [
                {
                    "op": "add_clue",
                    "id": "clue_wet_ticket_001",
                    "title": "젖은 승선표",
                    "summary": "표가 젖어 있습니다.",
                    "anchor_id": "loc_fog_harbor",
                }
            ],
        }
    )

    changes = story_patches_to_graph_changes(
        response.patches,
        graph=_graph(),
        player_id="player_01",
        turn_id=4,
    )

    assert isinstance(changes[0], AddNodeChange)
    assert changes[0].node.properties["kind"] == "clue"
    assert changes[0].node.properties["title"] == "젖은 승선표"
    assert isinstance(changes[1], AddEdgeChange)
    assert changes[1].edge.id == "has_knowledge:loc_fog_harbor:clue_wet_ticket_001"
    assert changes[1].edge.from_node_id == "loc_fog_harbor"
