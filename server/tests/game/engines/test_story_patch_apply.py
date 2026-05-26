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


def test_apply_converts_location_to_node_and_connection() -> None:
    response = StoryWriteResponse.model_validate(
        {
            "reason": "expanded",
            "patches": [
                {
                    "op": "add_location",
                    "id": "loc_back_alley_001",
                    "name": "창고 뒤 골목",
                    "description": "젖은 밧줄이 놓인 좁은 골목입니다.",
                    "connect_from": "loc_fog_harbor",
                }
            ],
        }
    )

    changes = story_patches_to_graph_changes(
        response.patches,
        graph=_graph(),
        player_id="player_01",
        turn_id=5,
    )

    assert isinstance(changes[0], AddNodeChange)
    assert changes[0].node.id == "loc_back_alley_001"
    assert changes[0].node.type == "location"
    assert changes[0].node.properties["name"] == "창고 뒤 골목"
    assert changes[0].node.properties["stability"] == "scene"
    assert changes[0].node.properties["turn_id"] == 5
    assert isinstance(changes[1], AddEdgeChange)
    assert changes[1].edge.id == "connects_to:loc_fog_harbor:loc_back_alley_001"
    assert changes[1].edge.type == "connects_to"


def test_apply_converts_character_to_node_and_location_edge() -> None:
    response = StoryWriteResponse.model_validate(
        {
            "reason": "witness",
            "patches": [
                {
                    "op": "add_character",
                    "id": "char_silent_child_001",
                    "name": "말없는 아이",
                    "role": "witness",
                    "location_id": "loc_fog_harbor",
                }
            ],
        }
    )

    changes = story_patches_to_graph_changes(
        response.patches,
        graph=_graph(),
        player_id="player_01",
        turn_id=6,
    )

    assert isinstance(changes[0], AddNodeChange)
    assert changes[0].node.id == "char_silent_child_001"
    assert changes[0].node.type == "character"
    assert changes[0].node.properties["name"] == "말없는 아이"
    assert changes[0].node.properties["role"] == "witness"
    assert changes[0].node.properties["stability"] == "scene"
    assert changes[0].node.properties["turn_id"] == 6
    assert isinstance(changes[1], AddEdgeChange)
    assert changes[1].edge.id == "located_at:char_silent_child_001:loc_fog_harbor"
    assert changes[1].edge.type == "located_at"


def test_apply_converts_owned_item_to_node_and_ownership_edge() -> None:
    response = StoryWriteResponse.model_validate(
        {
            "reason": "kept object",
            "patches": [
                {
                    "op": "add_item",
                    "id": "item_half_ticket_001",
                    "name": "찢어진 승선표 반쪽",
                    "description": "이름 없는 승선표의 반쪽입니다.",
                    "owner_id": "player_01",
                    "stability": "campaign",
                }
            ],
        }
    )

    changes = story_patches_to_graph_changes(
        response.patches,
        graph=_graph(),
        player_id="player_01",
        turn_id=7,
    )

    assert isinstance(changes[0], AddNodeChange)
    assert changes[0].node.id == "item_half_ticket_001"
    assert changes[0].node.type == "item"
    assert changes[0].node.properties["name"] == "찢어진 승선표 반쪽"
    assert changes[0].node.properties["stability"] == "campaign"
    assert changes[0].node.properties["turn_id"] == 7
    assert isinstance(changes[1], AddEdgeChange)
    assert changes[1].edge.id == "carries:player_01:item_half_ticket_001"
    assert changes[1].edge.type == "carries"


def test_apply_converts_quest_beat_to_pending_quest_node() -> None:
    response = StoryWriteResponse.model_validate(
        {
            "reason": "lead",
            "patches": [
                {
                    "op": "add_quest_beat",
                    "id": "quest_follow_wet_rope_001",
                    "title": "젖은 밧줄을 따라간다",
                    "summary": "밧줄의 물기가 이어지는 방향을 확인합니다.",
                    "stability": "chapter",
                }
            ],
        }
    )

    changes = story_patches_to_graph_changes(
        response.patches,
        graph=_graph(),
        player_id="player_01",
        turn_id=8,
    )

    assert len(changes) == 1
    assert isinstance(changes[0], AddNodeChange)
    assert changes[0].node.id == "quest_follow_wet_rope_001"
    assert changes[0].node.type == "quest"
    assert changes[0].node.properties["title"] == "젖은 밧줄을 따라간다"
    assert changes[0].node.properties["status"] == "pending"
    assert changes[0].node.properties["stability"] == "chapter"
    assert changes[0].node.properties["turn_id"] == 8
