from src.game.domain.graph import Graph, GraphEdge, GraphNode
from src.game.domain.story_contract import StoryContract
from src.game.domain.story_patch import StoryWriteResponse
from src.game.engines.story_patch_validator import validate_story_write_response


def _contract(
    *,
    patches_per_turn: int = 1,
    allowed_ops: list[str] | None = None,
) -> StoryContract:
    allowed = allowed_ops or ["add_memory", "add_clue"]
    return StoryContract.model_validate(
        {
            "id": "white_isle_llm",
            "world": {"title": "흰섬", "locale": "ko"},
            "fixed": [],
            "forbid": ["흰섬의 결말을 조기 공개하지 않습니다."],
            "tone": {"register": "합니다체", "person": "second"},
            "budgets": {
                "patches_per_turn": patches_per_turn,
                "new_terms_per_turn": 1,
            },
            "allowed_ops": allowed,
            "stability_defaults": {
                "add_memory": "campaign",
                "add_clue": "scene",
                "add_location": "scene",
                "add_character": "scene",
                "add_item": "scene",
                "add_quest_beat": "chapter",
            },
        }
    )


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
            "clue_existing": GraphNode(
                id="clue_existing",
                type="knowledge",
                properties={"kind": "clue"},
            ),
        },
        edges={
            "located_at:player_01:loc_fog_harbor": GraphEdge(
                id="located_at:player_01:loc_fog_harbor",
                type="located_at",
                from_node_id="player_01",
                to_node_id="loc_fog_harbor",
            )
        },
    )


def test_validator_accepts_single_valid_patch() -> None:
    response = StoryWriteResponse.model_validate(
        {
            "reason": "accepted",
            "patches": [
                {
                    "op": "add_clue",
                    "id": "clue_wet_ticket_001",
                    "title": "젖은 승선표",
                    "summary": "표가 바닥에 붙어 있습니다.",
                    "anchor_id": "loc_fog_harbor",
                }
            ],
        }
    )

    result = validate_story_write_response(response, graph=_graph(), contract=_contract())

    assert result.ok is True
    assert result.reasons == []


def test_validator_rejects_whole_response_for_budget_excess() -> None:
    response = StoryWriteResponse.model_validate(
        {
            "reason": "too much",
            "patches": [
                {"op": "add_memory", "id": "mem_one", "summary": "첫 기억입니다."},
                {"op": "add_memory", "id": "mem_two", "summary": "둘째 기억입니다."},
            ],
        }
    )

    result = validate_story_write_response(response, graph=_graph(), contract=_contract())

    assert result.ok is False
    assert "budget_exceeded" in result.reasons


def test_validator_rejects_missing_anchor() -> None:
    response = StoryWriteResponse.model_validate(
        {
            "reason": "bad anchor",
            "patches": [
                {
                    "op": "add_clue",
                    "id": "clue_missing_anchor_001",
                    "title": "없는 곳",
                    "summary": "참조가 없습니다.",
                    "anchor_id": "loc_missing",
                }
            ],
        }
    )

    result = validate_story_write_response(response, graph=_graph(), contract=_contract())

    assert result.ok is False
    assert "missing_anchor:loc_missing" in result.reasons


def test_validator_rejects_duplicate_node_id() -> None:
    response = StoryWriteResponse.model_validate(
        {
            "reason": "duplicate",
            "patches": [
                {
                    "op": "add_clue",
                    "id": "clue_existing",
                    "title": "기존 단서",
                    "summary": "이미 있습니다.",
                }
            ],
        }
    )

    result = validate_story_write_response(
        response,
        graph=_graph(),
        contract=_contract(patches_per_turn=2),
    )

    assert result.ok is False
    assert "duplicate_id:clue_existing" in result.reasons


def test_validator_rejects_contract_forbidden_text_in_patch() -> None:
    response = StoryWriteResponse.model_validate(
        {
            "reason": "forbidden",
            "patches": [
                {
                    "op": "add_clue",
                    "id": "clue_forbidden_destination_001",
                    "title": "조기 공개",
                    "summary": "흰섬의 결말을 조기 공개하지 않습니다.",
                    "anchor_id": "loc_fog_harbor",
                }
            ],
        }
    )

    result = validate_story_write_response(
        response,
        graph=_graph(),
        contract=_contract(),
    )

    assert result.ok is False
    assert "contract_forbidden" in result.reasons


def test_validator_rejects_contract_forbidden_text_in_new_terms() -> None:
    response = StoryWriteResponse.model_validate(
        {
            "reason": "forbidden term",
            "patches": [],
            "new_terms": ["흰섬의 결말을 조기 공개하지 않습니다."],
        }
    )

    result = validate_story_write_response(
        response,
        graph=_graph(),
        contract=_contract(),
    )

    assert result.ok is False
    assert "contract_forbidden" in result.reasons


def test_validator_accepts_location_connected_from_existing_location() -> None:
    response = StoryWriteResponse.model_validate(
        {
            "reason": "new place",
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

    result = validate_story_write_response(
        response,
        graph=_graph(),
        contract=_contract(allowed_ops=["add_memory", "add_clue", "add_location"]),
    )

    assert result.ok is True


def test_validator_rejects_location_missing_connect_from() -> None:
    response = StoryWriteResponse.model_validate(
        {
            "reason": "bad place",
            "patches": [
                {
                    "op": "add_location",
                    "id": "loc_back_alley_001",
                    "name": "창고 뒤 골목",
                    "description": "젖은 밧줄이 놓인 좁은 골목입니다.",
                    "connect_from": "loc_missing",
                }
            ],
        }
    )

    result = validate_story_write_response(
        response,
        graph=_graph(),
        contract=_contract(allowed_ops=["add_memory", "add_clue", "add_location"]),
    )

    assert result.ok is False
    assert "missing_connect_from:loc_missing" in result.reasons


def test_validator_accepts_character_at_existing_location() -> None:
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

    result = validate_story_write_response(
        response,
        graph=_graph(),
        contract=_contract(allowed_ops=["add_character"]),
    )

    assert result.ok is True


def test_validator_rejects_character_missing_location() -> None:
    response = StoryWriteResponse.model_validate(
        {
            "reason": "bad witness",
            "patches": [
                {
                    "op": "add_character",
                    "id": "char_silent_child_001",
                    "name": "말없는 아이",
                    "role": "witness",
                    "location_id": "loc_missing",
                }
            ],
        }
    )

    result = validate_story_write_response(
        response,
        graph=_graph(),
        contract=_contract(allowed_ops=["add_character"]),
    )

    assert result.ok is False
    assert "missing_location:loc_missing" in result.reasons


def test_validator_accepts_item_owned_by_existing_character() -> None:
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

    result = validate_story_write_response(
        response,
        graph=_graph(),
        contract=_contract(allowed_ops=["add_item"]),
    )

    assert result.ok is True


def test_validator_rejects_item_without_valid_placement() -> None:
    response = StoryWriteResponse.model_validate(
        {
            "reason": "bad item",
            "patches": [
                {
                    "op": "add_item",
                    "id": "item_half_ticket_001",
                    "name": "찢어진 승선표 반쪽",
                    "description": "이름 없는 승선표의 반쪽입니다.",
                    "location_id": "loc_missing",
                }
            ],
        }
    )

    result = validate_story_write_response(
        response,
        graph=_graph(),
        contract=_contract(allowed_ops=["add_item"]),
    )

    assert result.ok is False
    assert "missing_item_location:loc_missing" in result.reasons


def test_validator_rejects_generated_entity_name_collision() -> None:
    response = StoryWriteResponse.model_validate(
        {
            "reason": "duplicate name",
            "patches": [
                {
                    "op": "add_character",
                    "id": "char_player_copy_001",
                    "name": "당신",
                    "role": "bystander",
                    "location_id": "loc_fog_harbor",
                }
            ],
        }
    )

    result = validate_story_write_response(
        response,
        graph=_graph(),
        contract=_contract(allowed_ops=["add_character"]),
    )

    assert result.ok is False
    assert "duplicate_name:당신" in result.reasons


def test_validator_accepts_quest_beat() -> None:
    response = StoryWriteResponse.model_validate(
        {
            "reason": "lead",
            "patches": [
                {
                    "op": "add_quest_beat",
                    "id": "quest_follow_wet_rope_001",
                    "title": "젖은 밧줄을 따라간다",
                    "summary": "밧줄의 물기가 이어지는 방향을 확인합니다.",
                }
            ],
        }
    )

    result = validate_story_write_response(
        response,
        graph=_graph(),
        contract=_contract(allowed_ops=["add_quest_beat"]),
    )

    assert result.ok is True
