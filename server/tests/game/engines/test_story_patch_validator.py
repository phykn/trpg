from src.game.domain.graph import Graph, GraphEdge, GraphNode
from src.game.domain.story_contract import StoryContract
from src.game.domain.story_patch import StoryWriteResponse
from src.game.engines.story_patch_validator import validate_story_write_response


def _contract(*, patches_per_turn: int = 1) -> StoryContract:
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
            "allowed_ops": ["add_memory", "add_clue"],
            "stability_defaults": {
                "add_memory": "campaign",
                "add_clue": "scene",
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
