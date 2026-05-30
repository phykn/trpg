import pytest

from src.game.domain.graph import GraphEdge, GraphNode
from src.game.domain.story_patch_ledger import StoryPatchLedgerEntry

from .route_test_helpers import _build_app, _client, _init_graph_session

@pytest.mark.asyncio
async def test_story_patch_entries_route_returns_ledger(tmp_path):
    app = _build_app(tmp_path)

    async with _client(app) as client:
        game_id = await _init_graph_session(client)
        await app.state.graph_repo.append_story_patch_entries(
            game_id,
            [
                StoryPatchLedgerEntry(
                    turn=1,
                    status="accepted",
                    intent_kind="clue_candidate",
                    reason="found",
                    patches=[
                        {
                            "op": "add_clue",
                            "id": "clue_wet_ticket",
                            "title": "젖은 표",
                            "summary": "표가 젖어 있습니다.",
                        }
                    ],
                    changed_node_ids=["clue_wet_ticket"],
                    changed_edge_ids=["has_knowledge:loc_01:clue_wet_ticket"],
                )
            ],
        )
        response = await client.get(f"/session/{game_id}/story/patches")

    assert response.status_code == 200, response.text
    assert response.json() == {
        "game_id": game_id,
        "entries": [
            {
                "turn": 1,
                "status": "accepted",
                "intent_kind": "clue_candidate",
                "reason": "found",
                "patches": [
                    {
                        "op": "add_clue",
                        "id": "clue_wet_ticket",
                        "title": "젖은 표",
                        "summary": "표가 젖어 있습니다.",
                    }
                ],
                "rejected_reasons": [],
                "changed_node_ids": ["clue_wet_ticket"],
                "changed_edge_ids": ["has_knowledge:loc_01:clue_wet_ticket"],
            }
        ],
    }


@pytest.mark.asyncio
async def test_story_patch_timeline_route_returns_ledger(tmp_path):
    app = _build_app(tmp_path)

    async with _client(app) as client:
        game_id = await _init_graph_session(client)
        await app.state.graph_repo.append_story_patch_entries(
            game_id,
            [
                StoryPatchLedgerEntry(
                    turn=2,
                    status="rejected",
                    intent_kind="both",
                    reason="invalid proposal",
                    rejected_reasons=["contract_forbidden"],
                )
            ],
        )
        response = await client.get(f"/session/{game_id}/story/timeline")

    assert response.status_code == 200, response.text
    assert response.json() == {
        "game_id": game_id,
        "entries": [
            {
                "turn": 2,
                "status": "rejected",
                "intent_kind": "both",
                "reason": "invalid proposal",
                "patches": [],
                "rejected_reasons": ["contract_forbidden"],
                "changed_node_ids": [],
                "changed_edge_ids": [],
            }
        ],
    }


@pytest.mark.asyncio
async def test_story_patch_entries_route_missing_game_returns_404(tmp_path):
    app = _build_app(tmp_path)

    async with _client(app) as client:
        response = await client.get("/session/missing/story/patches")

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_story_patch_timeline_route_missing_game_returns_404(tmp_path):
    app = _build_app(tmp_path)

    async with _client(app) as client:
        response = await client.get("/session/missing/story/timeline")

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_story_debt_route_reports_generated_debt(tmp_path):
    app = _build_app(tmp_path)

    async with _client(app) as client:
        game_id = await _init_graph_session(client)
        graph = await app.state.graph_repo.load_graph(game_id)
        graph.nodes["clue_unresolved"] = GraphNode(
            id="clue_unresolved",
            type="knowledge",
            properties={
                "kind": "clue",
                "title": "젖은 표",
                "summary": "표가 젖어 있습니다.",
                "stability": "scene",
                "turn_id": 2,
            },
        )
        graph.nodes["clue_resolved"] = GraphNode(
            id="clue_resolved",
            type="knowledge",
            properties={
                "kind": "clue",
                "title": "해결된 표",
                "summary": "이미 회수됐습니다.",
                "stability": "scene",
                "turn_id": 3,
                "resolved": True,
            },
        )
        graph.nodes["char_orphan"] = GraphNode(
            id="char_orphan",
            type="character",
            properties={
                "name": "떠도는 목격자",
                "stability": "scene",
                "turn_id": 4,
            },
        )
        graph.nodes["item_orphan"] = GraphNode(
            id="item_orphan",
            type="item",
            properties={
                "name": "빈 병",
                "description": "놓인 곳이 없습니다.",
                "stability": "chapter",
                "turn_id": 5,
            },
        )
        graph.nodes["quest_loose"] = GraphNode(
            id="quest_loose",
            type="quest",
            properties={
                "title": "느슨한 실마리",
                "description": "아직 열린 동적 beat입니다.",
                "status": "pending",
                "stability": "chapter",
                "turn_id": 6,
            },
        )
        await app.state.graph_repo.save_graph(game_id, graph)

        response = await client.get(f"/session/{game_id}/story/debt")

    assert response.status_code == 200, response.text
    assert response.json() == {
        "game_id": game_id,
        "debt": {
            "unresolved_clues": [
                {
                    "id": "clue_unresolved",
                    "title": "젖은 표",
                    "turn": 2,
                    "reason": "generated clue is not marked resolved",
                }
            ],
            "orphan_characters": [
                {
                    "id": "char_orphan",
                    "title": "떠도는 목격자",
                    "turn": 4,
                    "reason": "generated character has no location",
                }
            ],
            "orphan_items": [
                {
                    "id": "item_orphan",
                    "title": "빈 병",
                    "turn": 5,
                    "reason": "generated item has no location or owner",
                }
            ],
            "dangling_quest_beats": [
                {
                    "id": "quest_loose",
                    "title": "느슨한 실마리",
                    "turn": 6,
                    "reason": "generated quest beat is still open",
                }
            ],
        },
    }


@pytest.mark.asyncio
async def test_story_debt_route_missing_game_returns_404(tmp_path):
    app = _build_app(tmp_path)

    async with _client(app) as client:
        response = await client.get("/session/missing/story/debt")

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_story_graph_route_returns_raw_graph(tmp_path):
    app = _build_app(tmp_path)

    async with _client(app) as client:
        game_id = await _init_graph_session(client)
        response = await client.get(f"/session/{game_id}/story/dev/graph")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["game_id"] == game_id
    assert "player_01" in body["graph"]["nodes"]
    assert "edges" in body["graph"]


@pytest.mark.asyncio
async def test_story_graph_route_missing_game_returns_404(tmp_path):
    app = _build_app(tmp_path)

    async with _client(app) as client:
        response = await client.get("/session/missing/story/dev/graph")

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_story_contract_route_returns_active_contract(tmp_path):
    app = _build_app(tmp_path, generated_contract=True)

    async with _client(app) as client:
        game_id = await _init_graph_session(client)
        response = await client.get(f"/session/{game_id}/story/dev/contract")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["game_id"] == game_id
    assert body["contract"]["id"] == "default"
    assert "add_clue" in body["contract"]["allowed_ops"]


@pytest.mark.asyncio
async def test_story_contract_route_without_contract_returns_409(tmp_path):
    app = _build_app(tmp_path)

    async with _client(app) as client:
        game_id = await _init_graph_session(client)
        response = await client.get(f"/session/{game_id}/story/dev/contract")

    assert response.status_code == 409


@pytest.mark.asyncio
async def test_story_contract_route_missing_game_returns_404(tmp_path):
    app = _build_app(tmp_path)

    async with _client(app) as client:
        response = await client.get("/session/missing/story/dev/contract")

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_story_contract_preview_route_validates_contract(tmp_path):
    app = _build_app(tmp_path, generated_contract=True)

    async with _client(app) as client:
        game_id = await _init_graph_session(client)
        response = await client.post(
            f"/session/{game_id}/story/dev/preview_contract",
            json={
                "contract": {
                    "id": "white_isle",
                    "world": {"title": "흰섬으로 가는 안개 바다", "locale": "ko"},
                    "fixed": ["엘리는 시작부터 동행합니다."],
                    "forbid": ["결말을 조기 공개하지 않습니다."],
                    "tone": {"register": "합니다체", "person": "second"},
                    "budgets": {"patches_per_turn": 1, "new_terms_per_turn": 1},
                    "allowed_ops": ["add_clue"],
                    "stability_defaults": {
                        "add_memory": "campaign",
                        "add_clue": "scene",
                        "add_location": "scene",
                        "add_character": "scene",
                        "add_item": "scene",
                        "add_quest_beat": "chapter",
                    },
                }
            },
        )

    assert response.status_code == 200, response.text
    assert response.json()["ok"] is True
    assert response.json()["contract"]["allowed_ops"] == ["add_clue"]


@pytest.mark.asyncio
async def test_story_contract_preview_route_returns_validation_reasons(tmp_path):
    app = _build_app(tmp_path, generated_contract=True)

    async with _client(app) as client:
        game_id = await _init_graph_session(client)
        response = await client.post(
            f"/session/{game_id}/story/dev/preview_contract",
            json={
                "contract": {
                    "id": "white_isle",
                    "world": {"title": "", "locale": "ko"},
                    "fixed": [],
                    "forbid": [],
                    "tone": {"register": "합니다체", "person": "second"},
                    "budgets": {"patches_per_turn": 9, "new_terms_per_turn": 1},
                    "allowed_ops": [],
                    "stability_defaults": {
                        "add_memory": "campaign",
                        "add_clue": "scene",
                        "add_location": "scene",
                        "add_character": "scene",
                        "add_item": "scene",
                        "add_quest_beat": "chapter",
                    },
                }
            },
        )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["ok"] is False
    assert body["reasons"]


@pytest.mark.asyncio
async def test_story_contract_preview_route_missing_game_returns_404(tmp_path):
    app = _build_app(tmp_path)

    async with _client(app) as client:
        response = await client.post(
            "/session/missing/story/dev/preview_contract",
            json={"contract": {}},
        )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_story_contract_update_route_saves_session_override(tmp_path):
    app = _build_app(tmp_path, generated_contract=True)

    async with _client(app) as client:
        game_id = await _init_graph_session(client)
        contract = {
            "id": "white_isle_override",
            "world": {"title": "흰섬으로 가는 안개 바다", "locale": "ko"},
            "fixed": ["엘리는 시작부터 동행합니다."],
            "forbid": ["결말을 조기 공개하지 않습니다."],
            "tone": {"register": "합니다체", "person": "second"},
            "budgets": {"patches_per_turn": 1, "new_terms_per_turn": 1},
            "allowed_ops": ["add_clue"],
            "stability_defaults": {
                "add_memory": "campaign",
                "add_clue": "scene",
                "add_location": "scene",
                "add_character": "scene",
                "add_item": "scene",
                "add_quest_beat": "chapter",
            },
        }
        response = await client.post(
            f"/session/{game_id}/story/dev/contract",
            json={"contract": contract},
        )
        reloaded = await client.get(f"/session/{game_id}/story/dev/contract")

    assert response.status_code == 200, response.text
    assert response.json()["contract"]["id"] == "white_isle_override"
    assert reloaded.status_code == 200, reloaded.text
    assert reloaded.json()["contract"]["id"] == "white_isle_override"
    progress = await app.state.graph_repo.load_progress(game_id)
    assert progress.story_contract_override is not None
    assert progress.story_contract_override["id"] == "white_isle_override"


@pytest.mark.asyncio
async def test_story_contract_update_route_rejects_invalid_contract(tmp_path):
    app = _build_app(tmp_path, generated_contract=True)

    async with _client(app) as client:
        game_id = await _init_graph_session(client)
        response = await client.post(
            f"/session/{game_id}/story/dev/contract",
            json={"contract": {"id": "broken"}},
        )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_story_contract_update_route_missing_game_returns_404(tmp_path):
    app = _build_app(tmp_path)

    async with _client(app) as client:
        response = await client.post(
            "/session/missing/story/dev/contract",
            json={"contract": {}},
        )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_story_rollback_route_removes_last_accepted_patch(tmp_path):
    app = _build_app(tmp_path)

    async with _client(app) as client:
        game_id = await _init_graph_session(client)
        graph = await app.state.graph_repo.load_graph(game_id)
        graph.nodes["clue_rollback"] = GraphNode(
            id="clue_rollback",
            type="knowledge",
            properties={
                "kind": "clue",
                "title": "되돌릴 단서",
                "summary": "롤백 대상입니다.",
                "stability": "scene",
                "turn_id": 2,
            },
        )
        graph.edges["has_knowledge:loc_01:clue_rollback"] = GraphEdge(
            id="has_knowledge:loc_01:clue_rollback",
            type="has_knowledge",
            from_node_id="loc_01",
            to_node_id="clue_rollback",
        )
        await app.state.graph_repo.save_graph(game_id, graph)
        await app.state.graph_repo.append_story_patch_entries(
            game_id,
            [
                StoryPatchLedgerEntry(
                    turn=2,
                    status="accepted",
                    intent_kind="clue_candidate",
                    reason="found",
                    patches=[
                        {
                            "op": "add_clue",
                            "id": "clue_rollback",
                            "title": "되돌릴 단서",
                            "summary": "롤백 대상입니다.",
                        }
                    ],
                    changed_node_ids=["clue_rollback"],
                    changed_edge_ids=["has_knowledge:loc_01:clue_rollback"],
                )
            ],
        )

        response = await client.post(f"/session/{game_id}/story/rollback")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["game_id"] == game_id
    assert body["entry"]["status"] == "rolled_back"
    assert body["entry"]["changed_node_ids"] == ["clue_rollback"]
    graph = await app.state.graph_repo.load_graph(game_id)
    assert "clue_rollback" not in graph.nodes
    assert "has_knowledge:loc_01:clue_rollback" not in graph.edges


@pytest.mark.asyncio
async def test_story_rollback_route_without_patch_returns_409(tmp_path):
    app = _build_app(tmp_path)

    async with _client(app) as client:
        game_id = await _init_graph_session(client)
        response = await client.post(f"/session/{game_id}/story/rollback")

    assert response.status_code == 409


@pytest.mark.asyncio
async def test_story_rollback_route_missing_game_returns_404(tmp_path):
    app = _build_app(tmp_path)

    async with _client(app) as client:
        response = await client.post("/session/missing/story/rollback")

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_story_patch_preview_route_returns_changed_ids(tmp_path):
    app = _build_app(tmp_path, generated_contract=True)

    async with _client(app) as client:
        game_id = await _init_graph_session(client)
        response = await client.post(
            f"/session/{game_id}/story/dev/preview_patch",
            json={
                "proposal": {
                    "reason": "preview",
                    "patches": [
                        {
                            "op": "add_clue",
                            "id": "clue_preview",
                            "title": "미리보기 단서",
                            "summary": "저장 전 검증입니다.",
                        }
                    ],
                    "narration_brief": "단서를 보여주세요.",
                }
            },
        )

    assert response.status_code == 200, response.text
    assert response.json() == {
        "game_id": game_id,
        "ok": True,
        "reasons": [],
        "changed_node_ids": ["clue_preview"],
        "changed_edge_ids": ["has_knowledge:loc_01:clue_preview"],
    }


@pytest.mark.asyncio
async def test_story_patch_preview_route_returns_validation_reasons(tmp_path):
    app = _build_app(tmp_path, generated_contract=True)

    async with _client(app) as client:
        game_id = await _init_graph_session(client)
        response = await client.post(
            f"/session/{game_id}/story/dev/preview_patch",
            json={
                "proposal": {
                    "reason": "금지된 결말을 말합니다.",
                    "patches": [
                        {
                            "op": "add_clue",
                            "id": "clue_forbidden",
                            "title": "금지된 결말",
                            "summary": "계약 위반입니다.",
                        }
                    ],
                }
            },
        )

    assert response.status_code == 200, response.text
    assert response.json()["ok"] is False
    assert "contract_forbidden" in response.json()["reasons"]


@pytest.mark.asyncio
async def test_story_patch_preview_route_without_contract_returns_409(tmp_path):
    app = _build_app(tmp_path)

    async with _client(app) as client:
        game_id = await _init_graph_session(client)
        response = await client.post(
            f"/session/{game_id}/story/dev/preview_patch",
            json={"proposal": {"reason": "preview", "patches": []}},
        )

    assert response.status_code == 409


@pytest.mark.asyncio
async def test_story_patch_preview_route_missing_game_returns_404(tmp_path):
    app = _build_app(tmp_path)

    async with _client(app) as client:
        response = await client.post(
            "/session/missing/story/dev/preview_patch",
            json={"proposal": {"reason": "preview", "patches": []}},
        )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_story_prompt_replay_route_returns_writer_prompt(tmp_path):
    app = _build_app(tmp_path, generated_contract=True)

    async with _client(app) as client:
        game_id = await _init_graph_session(client)
        response = await client.post(
            f"/session/{game_id}/story/dev/replay_prompt",
            json={
                "player_input": "표를 살핍니다.",
                "action": {"verb": "perceive", "what": "item_blank_ticket"},
            },
        )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["game_id"] == game_id
    assert body["agent"] == "story_write"
    assert body["intent"]["kind"] in {"clue_candidate", "both"}
    assert body["system_prompt"]
    assert body["user_payload"]["player_input"] == "표를 살핍니다."
    assert body["user_payload"]["action"] == {
        "verb": "perceive",
        "what": "item_blank_ticket",
    }


@pytest.mark.asyncio
async def test_story_prompt_replay_route_without_contract_returns_409(tmp_path):
    app = _build_app(tmp_path)

    async with _client(app) as client:
        game_id = await _init_graph_session(client)
        response = await client.post(
            f"/session/{game_id}/story/dev/replay_prompt",
            json={"player_input": "기다립니다.", "action": {"verb": "pass"}},
        )

    assert response.status_code == 409


@pytest.mark.asyncio
async def test_story_prompt_replay_route_missing_game_returns_404(tmp_path):
    app = _build_app(tmp_path)

    async with _client(app) as client:
        response = await client.post(
            "/session/missing/story/dev/replay_prompt",
            json={"player_input": "기다립니다.", "action": {"verb": "pass"}},
        )

    assert response.status_code == 404


