import json
import asyncio
import time

import pytest
from httpx import ASGITransport, AsyncClient

from run_api import build_app
from src.db.graph_local_fs import LocalFsGraphRepo
from src.game.domain.graph import GraphEdge, GraphNode
from src.game.engines.growth import xp_for_next_level
from tests._fakes import make_default_storage, make_scenario_repo


class _MockLLM:
    def __init__(
        self,
        payload: dict | None = None,
        *,
        intro_answer: str = "당신은 광장에 처음 발을 들입니다.",
        intro_delay: float = 0.0,
    ) -> None:
        self.payload = payload or {"actions": [{"verb": "pass"}]}
        self.intro_answer = intro_answer
        self.intro_delay = intro_delay
        self.calls: list[dict] = []

    async def chat(
        self,
        messages,
        think=False,
        agent=None,
        temperature=None,
        use_fallback=False,
    ):
        self.calls.append({"agent": agent, "messages": messages})
        if agent == "graph_intro":
            if self.intro_delay:
                await asyncio.sleep(self.intro_delay)
            return {"answer": self.intro_answer, "think": ""}
        if agent == "graph_narrate":
            return {"answer": "장면의 긴장이 짧게 가라앉습니다.", "think": ""}
        return {"answer": json.dumps(self.payload, ensure_ascii=False), "think": ""}


def _extend_default_storage_for_movement(storage) -> None:
    storage.objects["default/locations/loc_01.json"] = json.dumps(
        {
            "id": "loc_01",
            "name": "광장",
            "description": "테스트 광장",
            "connections": [{"target_id": "loc_02"}],
        },
        ensure_ascii=False,
    ).encode("utf-8")
    storage.objects["default/locations/loc_02.json"] = json.dumps(
        {
            "id": "loc_02",
            "name": "숲길",
            "description": "테스트 숲길",
        },
        ensure_ascii=False,
    ).encode("utf-8")


def _build_app(
    tmp_path,
    *,
    llm_payload: dict | None = None,
    intro_answer: str = "당신은 광장에 처음 발을 들입니다.",
    intro_delay: float = 0.0,
):
    storage = make_default_storage()
    _extend_default_storage_for_movement(storage)
    scenario_repo, _ = make_scenario_repo(storage)
    return build_app(
        llm=_MockLLM(
            llm_payload,
            intro_answer=intro_answer,
            intro_delay=intro_delay,
        ),
        basic_auth_user="t",
        basic_auth_pass="t",
        scenario_repo=scenario_repo,
        graph_repo=LocalFsGraphRepo(str(tmp_path / "graph")),
        cors_origins=[],
    )


def _client(app):
    return AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://t",
        auth=("t", "t"),
        timeout=30.0,
    )


async def _init_graph_session(client) -> str:
    response = await client.post(
        "/session/graph/init",
        json={
            "profile": "default",
            "player": {"name": "테스터", "race_id": "human", "gender": "female"},
        },
    )
    assert response.status_code == 200, response.text
    return response.json()["game_id"]


@pytest.mark.asyncio
async def test_graph_init_persists_graph_and_returns_front_state(tmp_path):
    app = _build_app(tmp_path)

    async with _client(app) as client:
        response = await client.post(
            "/session/graph/init",
            json={
                "profile": "default",
                "player": {
                    "name": "테스터",
                    "race_id": "human",
                    "gender": "female",
                },
            },
        )

    assert response.status_code == 200, response.text
    body = response.json()
    graph = await app.state.graph_repo.load_graph(body["game_id"])
    progress = await app.state.graph_repo.load_progress(body["game_id"])

    assert graph.nodes["player_01"].properties["name"] == "테스터"
    assert progress.player_id == "player_01"
    assert body["state"]["hero"]["id"] == "player_01"
    assert body["state"]["place"]["id"] == "loc_01"


@pytest.mark.asyncio
async def test_graph_init_adds_intro_narration_but_move_and_offer_stay_system_card_only(
    tmp_path,
):
    intro = "당신은 광장의 낮은 소음 속에서 첫 발을 내딛습니다."
    app = _build_app(tmp_path, intro_answer=intro)

    async with _client(app) as client:
        init_response = await client.post(
            "/session/graph/init",
            json={
                "profile": "default",
                "player": {
                    "name": "테스터",
                    "race_id": "human",
                    "gender": "female",
                },
            },
        )
        assert init_response.status_code == 200, init_response.text
        game_id = init_response.json()["game_id"]

        move_response = await client.post(
            f"/session/{game_id}/graph/turn",
            json={"action": {"verb": "move", "to": "loc_02"}},
        )

    assert move_response.status_code == 200, move_response.text
    init_body = init_response.json()
    move_body = move_response.json()
    logs = await app.state.graph_repo.load_log_entries(game_id)
    progress = await app.state.graph_repo.load_progress(game_id)

    assert init_body["state"]["log"] == [{"id": 1, "kind": "gm", "text": intro}]
    assert [entry.kind for entry in logs] == ["gm", "act", "act"]
    assert [entry.id for entry in logs] == [1, 2, 3]
    assert logs[0].text == intro
    assert logs[1].text == "당신은 숲길로 이동합니다."
    assert logs[2].text == "새 의뢰가 도착합니다: 마을의 부탁."
    assert move_body["state"]["log"][-1]["kind"] == "act"
    assert progress.next_log_id == 4
    assert [call["agent"] for call in app.state.llm.calls].count("graph_intro") == 1


@pytest.mark.asyncio
async def test_graph_init_does_not_block_on_slow_intro_narration(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(
        "src.api.routes.session_graph._GRAPH_INIT_NARRATION_TIMEOUT_SECONDS",
        0.01,
        raising=False,
    )
    app = _build_app(tmp_path, intro_delay=0.25)

    started = time.perf_counter()
    async with _client(app) as client:
        response = await client.post(
            "/session/graph/init",
            json={
                "profile": "default",
                "player": {
                    "name": "테스터",
                    "race_id": "human",
                    "gender": "female",
                },
            },
        )
    elapsed = time.perf_counter() - started

    assert response.status_code == 200, response.text
    assert elapsed < 0.2
    log = response.json()["state"]["log"]
    assert log[0]["kind"] == "gm"
    assert "광장" in log[0]["text"]


@pytest.mark.asyncio
async def test_graph_turn_moves_player_and_persists_progress(tmp_path):
    app = _build_app(tmp_path)

    async with _client(app) as client:
        game_id = await _init_graph_session(client)
        response = await client.post(
            f"/session/{game_id}/graph/turn",
            json={"action": {"verb": "move", "to": "loc_02"}},
        )

    assert response.status_code == 200, response.text
    body = response.json()
    graph = await app.state.graph_repo.load_graph(game_id)
    progress = await app.state.graph_repo.load_progress(game_id)

    assert "located_at:player_01:loc_02" in graph.edges
    assert progress.turn_count == 1
    assert body["state"]["place"]["id"] == "loc_02"


@pytest.mark.asyncio
async def test_graph_level_up_commits_and_returns_state(tmp_path):
    app = _build_app(tmp_path)

    async with _client(app) as client:
        game_id = await _init_graph_session(client)
        graph = await app.state.graph_repo.load_graph(game_id)
        player = graph.nodes["player_01"]
        level = player.properties["level"]
        player.properties["xp_pool"] = xp_for_next_level(level)
        await app.state.graph_repo.save_graph(game_id, graph)

        response = await client.post(
            f"/session/{game_id}/graph/level_up",
            json={"stat_up": "body", "skill_id": None, "think": False},
        )

    assert response.status_code == 200, response.text
    body = response.json()
    graph = await app.state.graph_repo.load_graph(game_id)
    progress = await app.state.graph_repo.load_progress(game_id)
    logs = await app.state.graph_repo.load_log_entries(game_id)
    player_props = graph.nodes["player_01"].properties

    assert player_props["level"] == level + 1
    assert player_props["xp_pool"] == 0
    assert player_props["stats"]["body"] == 11
    assert player_props["stats"]["presence"] == 10
    assert body["state"]["hero"]["level"] == level + 1
    assert body["state"]["hero"]["exp"] == 0
    assert body["state"]["log"] == [entry.model_dump() for entry in logs]
    assert logs[-1].kind == "act"
    assert "레벨이 올랐습니다" in logs[-1].text
    assert progress.next_log_id == logs[-1].id + 1


@pytest.mark.asyncio
async def test_graph_state_route_restores_graph_session(tmp_path):
    app = _build_app(tmp_path)

    async with _client(app) as client:
        game_id = await _init_graph_session(client)
        response = await client.get(f"/session/{game_id}/graph/state")

    assert response.status_code == 200, response.text
    body = response.json()

    assert body["game_id"] == game_id
    assert body["state"]["hero"]["id"] == "player_01"
    assert body["state"]["place"]["id"] == "loc_01"
    assert body["state"]["log"][0]["kind"] == "gm"


@pytest.mark.asyncio
async def test_graph_state_route_missing_game_returns_404(tmp_path):
    app = _build_app(tmp_path)

    async with _client(app) as client:
        response = await client.get("/session/missing/graph/state")

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_graph_turn_missing_game_returns_404(tmp_path):
    app = _build_app(tmp_path)

    async with _client(app) as client:
        response = await client.post(
            "/session/missing/graph/turn",
            json={"action": {"verb": "move", "to": "loc_02"}},
        )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_graph_turn_rejects_query_without_advancing_turn(tmp_path):
    app = _build_app(tmp_path)

    async with _client(app) as client:
        game_id = await _init_graph_session(client)
        response = await client.post(
            f"/session/{game_id}/graph/turn",
            json={"action": {"verb": "query", "what": "status"}},
        )

    assert response.status_code == 200, response.text
    body = response.json()
    progress = await app.state.graph_repo.load_progress(game_id)

    assert body["status"] == "answered"
    assert body["message"]
    assert progress.turn_count == 0


@pytest.mark.asyncio
async def test_graph_turn_attack_returns_confirmation_without_starting_combat(tmp_path):
    app = _build_app(tmp_path)

    async with _client(app) as client:
        game_id = await _init_graph_session(client)
        response = await client.post(
            f"/session/{game_id}/graph/turn",
            json={"action": {"verb": "attack", "what": "edrik_chief"}},
        )

    assert response.status_code == 200, response.text
    body = response.json()
    progress = await app.state.graph_repo.load_progress(game_id)

    assert body["state"]["pendingConfirmation"]["kind"] == "attack_start"
    assert "payload" not in body["state"]["pendingConfirmation"]
    assert progress.pending_confirmation["kind"] == "attack_start"
    assert progress.graph_combat_state is None
    assert progress.turn_count == 0


@pytest.mark.asyncio
async def test_graph_confirm_confirm_executes_pending_attack(tmp_path):
    app = _build_app(tmp_path)

    async with _client(app) as client:
        game_id = await _init_graph_session(client)
        attack_response = await client.post(
            f"/session/{game_id}/graph/turn",
            json={"action": {"verb": "attack", "what": "edrik_chief"}},
        )
        confirmation_id = attack_response.json()["state"]["pendingConfirmation"]["id"]
        response = await client.post(
            f"/session/{game_id}/graph/confirm",
            json={"confirmation_id": confirmation_id, "decision": "confirm"},
        )

    assert response.status_code == 200, response.text
    body = response.json()
    progress = await app.state.graph_repo.load_progress(game_id)

    assert body["state"]["pendingConfirmation"] is None
    assert body["state"]["combat"] is not None
    assert progress.pending_confirmation is None
    assert progress.graph_combat_state is not None
    assert progress.turn_count == 1


@pytest.mark.asyncio
async def test_graph_confirm_cancel_clears_pending_attack(tmp_path):
    app = _build_app(tmp_path)

    async with _client(app) as client:
        game_id = await _init_graph_session(client)
        attack_response = await client.post(
            f"/session/{game_id}/graph/turn",
            json={"action": {"verb": "attack", "what": "edrik_chief"}},
        )
        confirmation_id = attack_response.json()["state"]["pendingConfirmation"]["id"]
        response = await client.post(
            f"/session/{game_id}/graph/confirm",
            json={"confirmation_id": confirmation_id, "decision": "cancel"},
        )

    assert response.status_code == 200, response.text
    body = response.json()
    progress = await app.state.graph_repo.load_progress(game_id)

    assert body["state"]["pendingConfirmation"] is None
    assert body["state"]["combat"] is None
    assert progress.pending_confirmation is None
    assert progress.graph_combat_state is None
    assert progress.turn_count == 0


@pytest.mark.asyncio
async def test_graph_turn_pass_defends_during_existing_combat(tmp_path):
    app = _build_app(tmp_path)

    async with _client(app) as client:
        game_id = await _init_graph_session(client)
        attack_response = await client.post(
            f"/session/{game_id}/graph/turn",
            json={"action": {"verb": "attack", "what": "edrik_chief"}},
        )
        confirmation_id = attack_response.json()["state"]["pendingConfirmation"]["id"]
        await client.post(
            f"/session/{game_id}/graph/confirm",
            json={"confirmation_id": confirmation_id, "decision": "confirm"},
        )
        response = await client.post(
            f"/session/{game_id}/graph/turn",
            json={"action": {"verb": "pass"}},
        )

    assert response.status_code == 200, response.text
    body = response.json()
    progress = await app.state.graph_repo.load_progress(game_id)

    assert body["state"]["combat"] is not None
    assert body["state"]["combat"]["round"] == 3
    assert progress.graph_combat_state is not None
    assert progress.graph_combat_state.round == 3


@pytest.mark.asyncio
async def test_graph_turn_flee_clears_existing_combat(tmp_path):
    app = _build_app(tmp_path)

    async with _client(app) as client:
        game_id = await _init_graph_session(client)
        attack_response = await client.post(
            f"/session/{game_id}/graph/turn",
            json={"action": {"verb": "attack", "what": "edrik_chief"}},
        )
        confirmation_id = attack_response.json()["state"]["pendingConfirmation"]["id"]
        await client.post(
            f"/session/{game_id}/graph/confirm",
            json={"confirmation_id": confirmation_id, "decision": "confirm"},
        )
        response = await client.post(
            f"/session/{game_id}/graph/turn",
            json={"action": {"verb": "move", "how": "flee"}},
        )

    assert response.status_code == 200, response.text
    body = response.json()
    progress = await app.state.graph_repo.load_progress(game_id)

    assert body["state"]["combat"] is None
    assert progress.graph_combat_state is None


@pytest.mark.asyncio
async def test_graph_turn_equips_carried_item_and_returns_actionable_state(tmp_path):
    app = _build_app(tmp_path)

    async with _client(app) as client:
        game_id = await _init_graph_session(client)
        graph = await app.state.graph_repo.load_graph(game_id)
        graph.nodes["training_sword"] = GraphNode(
            id="training_sword",
            type="item",
            properties={
                "name": "연습검",
                "effects": {"type": "weapon", "weapon_dice": "1d6"},
            },
        )
        graph.edges["carries:player_01:training_sword"] = GraphEdge(
            id="carries:player_01:training_sword",
            type="carries",
            from_node_id="player_01",
            to_node_id="training_sword",
        )
        await app.state.graph_repo.save_graph(game_id, graph)

        response = await client.post(
            f"/session/{game_id}/graph/turn",
            json={
                "action": {
                    "verb": "transfer",
                    "what": "training_sword",
                    "how": "equip",
                    "to": "weapon",
                }
            },
        )

    assert response.status_code == 200, response.text
    body = response.json()
    graph = await app.state.graph_repo.load_graph(game_id)
    progress = await app.state.graph_repo.load_progress(game_id)

    assert body["state"]["hero"]["equipment"]["weapon"] == {
        "id": "training_sword",
        "name": "연습검",
    }
    assert body["state"]["hero"]["inventory"] == []
    assert "equips:player_01:training_sword" in graph.edges
    assert "carries:player_01:training_sword" not in graph.edges
    assert progress.turn_count == 1


@pytest.mark.asyncio
async def test_graph_turn_uses_consumable_item_and_consumes_inventory_edge(tmp_path):
    app = _build_app(tmp_path)

    async with _client(app) as client:
        game_id = await _init_graph_session(client)
        graph = await app.state.graph_repo.load_graph(game_id)
        player = graph.nodes["player_01"]
        player.properties["hp"] = player.properties["max_hp"] - 5
        graph.nodes["healing_potion"] = GraphNode(
            id="healing_potion",
            type="item",
            properties={
                "name": "회복 물약",
                "consumable": True,
                "effects": {"type": "consumable", "effect": "heal", "amount": 8},
            },
        )
        graph.edges["carries:player_01:healing_potion"] = GraphEdge(
            id="carries:player_01:healing_potion",
            type="carries",
            from_node_id="player_01",
            to_node_id="healing_potion",
        )
        await app.state.graph_repo.save_graph(game_id, graph)

        response = await client.post(
            f"/session/{game_id}/graph/turn",
            json={"action": {"verb": "use", "what": "healing_potion"}},
        )

    assert response.status_code == 200, response.text
    body = response.json()
    graph = await app.state.graph_repo.load_graph(game_id)
    progress = await app.state.graph_repo.load_progress(game_id)

    hp = body["state"]["hero"]["resources"]["hp"]
    assert hp["current"] == hp["maximum"]
    assert body["state"]["hero"]["inventory"] == []
    assert "carries:player_01:healing_potion" not in graph.edges
    assert progress.turn_count == 1


@pytest.mark.asyncio
async def test_graph_input_classifies_text_and_returns_confirmation(tmp_path):
    app = _build_app(
        tmp_path,
        llm_payload={"actions": [{"verb": "attack", "what": "edrik_chief"}]},
    )

    async with _client(app) as client:
        game_id = await _init_graph_session(client)
        response = await client.post(
            f"/session/{game_id}/graph/input",
            json={"player_input": "에드릭을 공격한다"},
        )

    assert response.status_code == 200, response.text
    body = response.json()
    progress = await app.state.graph_repo.load_progress(game_id)

    assert body["state"]["pendingConfirmation"]["kind"] == "attack_start"
    assert progress.pending_confirmation["kind"] == "attack_start"
    assert progress.graph_combat_state is None


@pytest.mark.asyncio
async def test_graph_input_classifies_query_and_returns_message(tmp_path):
    app = _build_app(
        tmp_path,
        llm_payload={"actions": [{"verb": "query", "what": "exits"}]},
    )

    async with _client(app) as client:
        game_id = await _init_graph_session(client)
        response = await client.post(
            f"/session/{game_id}/graph/input",
            json={"player_input": "어디로 갈 수 있습니까?"},
        )

    assert response.status_code == 200, response.text
    body = response.json()
    progress = await app.state.graph_repo.load_progress(game_id)

    assert body["status"] == "answered"
    assert "숲길" in body["message"]
    assert progress.turn_count == 0


@pytest.mark.asyncio
async def test_graph_play_loop_reaches_quest_reward_without_legacy_state(tmp_path):
    app = _build_app(tmp_path)

    async with _client(app) as client:
        game_id = await _init_graph_session(client)

        move_response = await client.post(
            f"/session/{game_id}/graph/turn",
            json={"action": {"verb": "move", "to": "loc_02"}},
        )
        assert move_response.status_code == 200, move_response.text
        move_body = move_response.json()
        quest_id = move_body["state"]["questOffers"][0]["id"]

        accept_response = await client.post(
            f"/session/{game_id}/graph/turn",
            json={"action": {"verb": "transfer", "what": quest_id, "how": "accept"}},
        )
        assert accept_response.status_code == 200, accept_response.text
        accept_body = accept_response.json()
        accept_id = accept_body["state"]["pendingConfirmation"]["id"]

        accepted_response = await client.post(
            f"/session/{game_id}/graph/confirm",
            json={"confirmation_id": accept_id, "decision": "confirm"},
        )
        assert accepted_response.status_code == 200, accepted_response.text
        accepted_body = accepted_response.json()
        enemy_id = "auto_enemy_001"

        attack_response = await client.post(
            f"/session/{game_id}/graph/turn",
            json={"action": {"verb": "attack", "what": enemy_id}},
        )
        assert attack_response.status_code == 200, attack_response.text
        attack_body = attack_response.json()
        attack_id = attack_body["state"]["pendingConfirmation"]["id"]

        first_exchange_response = await client.post(
            f"/session/{game_id}/graph/confirm",
            json={"confirmation_id": attack_id, "decision": "confirm"},
        )
        assert first_exchange_response.status_code == 200, first_exchange_response.text
        first_exchange_body = first_exchange_response.json()

        final_response = await client.post(
            f"/session/{game_id}/graph/turn",
            json={"action": {"verb": "attack", "what": enemy_id}},
        )
        assert final_response.status_code == 200, final_response.text
        final_body = final_response.json()

    graph = await app.state.graph_repo.load_graph(game_id)
    progress = await app.state.graph_repo.load_progress(game_id)
    logs = await app.state.graph_repo.load_log_entries(game_id)

    assert accepted_body["state"]["quest"]["id"] == quest_id
    assert accepted_body["state"]["questOffers"] == []
    assert first_exchange_body["state"]["combat"] is not None
    assert final_body["state"]["combat"] is None
    assert final_body["state"]["quest"] is None
    assert final_body["state"]["questOffers"][0]["id"] == "auto_quest_002"
    assert final_body["state"]["hero"]["gold"] == 5
    assert final_body["state"]["hero"]["exp"] == 10
    assert final_body["state"]["hero"]["inventory"] == [
        {
            "id": "auto_reward_001",
            "name": "작은 보상",
            "qty": 1,
            "canUse": False,
            "equipSlots": [],
        }
    ]
    assert graph.nodes[quest_id].properties["status"] == "completed"
    assert graph.nodes[enemy_id].properties["status"] == ["defeated"]
    assert progress.active_quest_id is None
    assert progress.graph_combat_state is None
    assert [entry.kind for entry in logs[-3:]] == ["act", "act", "gm"]
    assert [entry.text for entry in logs[-3:]] == [
        "당신은 전투에서 승리합니다.",
        "새 의뢰가 도착합니다: 마을의 부탁.",
        "장면의 긴장이 짧게 가라앉습니다.",
    ]
