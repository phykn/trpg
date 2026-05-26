import json
import asyncio
import time

import httpx
import pytest
from httpx import ASGITransport, AsyncClient
from openai import RateLimitError

from run_api import build_app
from src.db.graph.local_fs import LocalFsGraphRepo
from src.game.domain.graph import GraphEdge, GraphNode
from src.game.domain.story_patch_ledger import StoryPatchLedgerEntry
from src.game.engines.growth import xp_for_next_level
from tests._fakes import make_default_storage, make_scenario_repo


class _MockLLM:
    def __init__(
        self,
        payload: dict | None = None,
        *,
        intro_answer: str = "당신은 광장에 처음 발을 들입니다.",
        intro_delay: float = 0.0,
        intro_error: Exception | None = None,
        narration_meta: dict | None = None,
    ) -> None:
        self.payload = payload or {"actions": [{"verb": "pass"}]}
        self.intro_answer = intro_answer
        self.intro_delay = intro_delay
        self.intro_error = intro_error
        self.narration_meta = narration_meta
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
            if self.intro_error is not None:
                raise self.intro_error
            if self.intro_delay:
                await asyncio.sleep(self.intro_delay)
            return {"answer": self.intro_answer, "think": ""}
        if agent in {"graph_narrate", "combat_narrate"}:
            return {"answer": self._narration_answer(), "think": ""}
        return {"answer": json.dumps(self.payload, ensure_ascii=False), "think": ""}

    async def chat_stream(
        self,
        messages,
        think=False,
        agent=None,
        temperature=None,
        use_fallback=False,
    ):
        self.calls.append({"agent": agent, "messages": messages})
        if agent == "graph_intro":
            if self.intro_error is not None:
                raise self.intro_error
            if self.intro_delay:
                await asyncio.sleep(self.intro_delay)
            midpoint = max(1, len(self.intro_answer) // 2)
            for chunk in (self.intro_answer[:midpoint], self.intro_answer[midpoint:]):
                yield {"answer": chunk, "think": None}
            return
        if agent in {"graph_narrate", "combat_narrate"}:
            answer = self._narration_answer()
            midpoint = max(1, len(answer) // 2)
            for chunk in (answer[:midpoint], answer[midpoint:]):
                yield {"answer": chunk, "think": None}
            return
        yield {
            "answer": json.dumps(self.payload, ensure_ascii=False),
            "think": None,
        }

    def _narration_answer(self) -> str:
        narration = "장면의 긴장이 짧게 가라앉습니다."
        if self.narration_meta is None:
            return narration
        return "\n".join(
            [
                narration,
                "---TRPG_META---",
                json.dumps(self.narration_meta, ensure_ascii=False),
            ]
        )


def _extend_default_storage_for_movement(storage) -> None:
    storage.objects["default/locations/loc_01.json"] = json.dumps(
        {
            "id": "loc_01",
            "name": "광장",
            "description": "테스트 광장",
            "connections": [{"target": "loc_02"}],
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
    start_intro_text: str | None = None,
    intro_delay: float = 0.0,
    intro_error: Exception | None = None,
    narration_meta: dict | None = None,
    generated_contract: bool = False,
):
    storage = make_default_storage()
    if generated_contract:
        storage.objects["default/contract.json"] = json.dumps(
            {
                "id": "default",
                "world": {"title": "생성형 테스트", "locale": "ko"},
                "fixed": [],
                "forbid": ["금지된 결말"],
                "tone": {"register": "합니다체", "person": "second"},
                "budgets": {"patches_per_turn": 1, "new_terms_per_turn": 1},
                "allowed_ops": ["add_memory", "add_clue", "add_location"],
                "stability_defaults": {
                    "add_memory": "campaign",
                    "add_clue": "scene",
                    "add_location": "scene",
                },
            },
            ensure_ascii=False,
        ).encode("utf-8")
    if start_intro_text is not None:
        start = json.loads(storage.objects["default/start.json"].decode("utf-8"))
        start["intro_text"] = start_intro_text
        storage.objects["default/start.json"] = json.dumps(
            start, ensure_ascii=False
        ).encode("utf-8")
    _extend_default_storage_for_movement(storage)
    scenario_repo, _ = make_scenario_repo(storage)
    return build_app(
        llm=_MockLLM(
            llm_payload,
            intro_answer=intro_answer,
            intro_delay=intro_delay,
            intro_error=intro_error,
            narration_meta=narration_meta,
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


def _rate_limit_error(message: str = "quota exceeded") -> RateLimitError:
    response = httpx.Response(
        status_code=429, request=httpx.Request("POST", "http://x")
    )
    return RateLimitError(message, response=response, body=None)


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
async def test_graph_intro_adds_initial_narration_and_first_visit_move_narration(
    tmp_path,
):
    app = _build_app(
        tmp_path,
        intro_answer="LLM 소개는 쓰이지 않습니다.",
        start_intro_text="데이터 소개는 init 응답을 막지 않습니다.",
    )

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

        intro_response = await client.post(f"/session/{game_id}/graph/intro")
        assert intro_response.status_code == 200, intro_response.text

        move_response = await client.post(
            f"/session/{game_id}/graph/turn",
            json={"action": {"verb": "move", "to": "loc_02"}},
        )

    assert move_response.status_code == 200, move_response.text
    init_body = init_response.json()
    intro_body = intro_response.json()
    move_body = move_response.json()
    logs = await app.state.graph_repo.load_log_entries(game_id)
    progress = await app.state.graph_repo.load_progress(game_id)

    assert init_body["state"]["log"] == []
    assert intro_body["state"]["log"] == [
        {"id": 1, "kind": "gm", "text": "데이터 소개는 init 응답을 막지 않습니다."}
    ]
    assert intro_body["outcome"] == "neutral"
    assert move_body["outcome"] == "neutral"
    assert [entry.kind for entry in logs] == ["gm", "act", "gm"]
    assert [entry.id for entry in logs] == [1, 2, 3]
    assert logs[0].text == "데이터 소개는 init 응답을 막지 않습니다."
    assert logs[1].text == "당신은 숲길로 이동합니다."
    assert move_body["state"]["log"][-1]["kind"] == "gm"
    assert move_body["state"]["log"][-1]["text"] == "테스트 숲길"
    assert progress.next_log_id == 4
    assert [call["agent"] for call in app.state.llm.calls].count("graph_intro") == 0
    assert [call["agent"] for call in app.state.llm.calls].count("graph_narrate") == 0


@pytest.mark.asyncio
async def test_graph_intro_rate_limited_llm_uses_fallback_narration(tmp_path):
    app = _build_app(tmp_path, intro_error=_rate_limit_error())

    async with _client(app) as client:
        game_id = await _init_graph_session(client)
        response = await client.post(f"/session/{game_id}/graph/intro")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["state"]["log"] == [
        {
            "id": 1,
            "kind": "gm",
            "text": "당신은 광장에 도착합니다. 테스트 광장",
        }
    ]
    assert body["outcome"] == "neutral"


@pytest.mark.asyncio
async def test_graph_init_emits_flow_debug_timing_logs(tmp_path, monkeypatch, capsys):
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
    stderr = capsys.readouterr().err

    assert "gid=" in stderr
    assert "turn=0" in stderr
    assert "t=" in stderr
    assert "engine" in stderr
    assert "graph:init" in stderr
    assert "graph:init_done" in stderr


@pytest.mark.asyncio
async def test_graph_init_does_not_block_on_slow_intro_narration(
    tmp_path,
):
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
    assert log == []
    assert [call["agent"] for call in app.state.llm.calls].count("graph_intro") == 0


@pytest.mark.asyncio
async def test_graph_intro_streams_result_before_initial_narration(tmp_path):
    app = _build_app(
        tmp_path,
        intro_answer="LLM 소개는 쓰이지 않습니다.",
        start_intro_text="문이 열리고 광장이 드러납니다.",
    )

    async with _client(app) as client:
        game_id = await _init_graph_session(client)
        response = await client.post(f"/session/{game_id}/graph/intro/stream")

    assert response.status_code == 200, response.text
    lines = [json.loads(line) for line in response.text.splitlines() if line.strip()]

    assert [line["type"] for line in lines] == [
        "result",
        "narration_delta",
        "final",
    ]
    assert lines[0]["payload"]["status"] == "executed"
    assert lines[0]["payload"]["outcome"] == "neutral"
    assert lines[0]["payload"]["state"]["log"] == []
    assert lines[1]["text"] == "문이 열리고 광장이 드러납니다."
    assert lines[-1]["payload"]["state"]["log"] == [
        {"id": 1, "kind": "gm", "text": "문이 열리고 광장이 드러납니다."}
    ]
    assert lines[-1]["payload"]["suggestions"] == [
        {
            "label": "talk",
            "input_text": "에드릭에게 말을 겁니다",
            "intent": "talk",
            "action": None,
        },
        {
            "label": "move",
            "input_text": "숲길로 이동합니다",
            "intent": "move",
            "action": None,
        },
        {
            "label": "inspect",
            "input_text": "주변을 살핍니다",
            "intent": "inspect",
            "action": None,
        },
    ]
    assert [call["agent"] for call in app.state.llm.calls].count("graph_intro") == 0


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
async def test_graph_turn_stream_returns_result_then_first_visit_move_narration(
    tmp_path,
):
    app = _build_app(tmp_path)

    async with _client(app) as client:
        game_id = await _init_graph_session(client)
        response = await client.post(
            f"/session/{game_id}/graph/turn/stream",
            json={"action": {"verb": "move", "to": "loc_02"}},
        )

    assert response.status_code == 200, response.text
    events = [json.loads(line) for line in response.text.splitlines()]

    assert [event["type"] for event in events] == [
        "result",
        "narration_delta",
        "final",
    ]
    assert events[1]["text"] == "테스트 숲길"
    assert events[0]["payload"]["status"] == "executed"
    assert events[0]["payload"]["outcome"] == "neutral"
    assert (
        events[0]["payload"]["state"]["log"][0]["text"] == "당신은 숲길로 이동합니다."
    )
    assert events[-1]["payload"]["status"] == "executed"
    assert events[-1]["payload"]["outcome"] == "neutral"
    assert events[-1]["payload"]["state"]["log"][-1]["kind"] == "gm"
    assert events[-1]["payload"]["state"]["place"]["id"] == "loc_02"


@pytest.mark.asyncio
async def test_graph_stream_returns_error_event_on_unexpected_failure():
    from src.api.session_graph_routes import _graph_action_streaming_response

    async def source():
        yield {"type": "narration_delta", "text": "루카가 입을 엽니다."}
        raise RuntimeError("boom")

    response = _graph_action_streaming_response("game-1", source)
    chunks = [
        chunk.decode("utf-8") if isinstance(chunk, bytes) else chunk
        async for chunk in response.body_iterator
    ]
    events = [json.loads(line) for line in "".join(chunks).splitlines()]

    assert [event["type"] for event in events] == ["narration_delta", "error"]
    assert events[-1]["status"] == 500
    assert events[-1]["message"] == "요청이 끊겼습니다. 같은 행동을 다시 시도해 주세요."


@pytest.mark.asyncio
async def test_graph_roll_stream_returns_result_then_roll_narration(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr("src.game.runtime.flow.roll.random.randint", lambda _a, _b: 13)
    app = _build_app(tmp_path)

    async with _client(app) as client:
        game_id = await _init_graph_session(client)
        pending_response = await client.post(
            f"/session/{game_id}/graph/turn",
            json={"action": {"verb": "perceive", "what": "loc_01"}},
        )
        assert pending_response.status_code == 200, pending_response.text
        roll_id = pending_response.json()["state"]["pendingRoll"]["id"]
        response = await client.post(
            f"/session/{game_id}/graph/roll/stream",
            json={"roll_id": roll_id},
        )

    assert response.status_code == 200, response.text
    events = [json.loads(line) for line in response.text.splitlines()]

    assert events[0]["type"] == "result"
    assert events[-1]["type"] == "final"
    assert all(event["type"] == "narration_delta" for event in events[1:-1])
    assert events[0]["payload"]["status"] == "executed"
    assert events[0]["payload"]["outcome"] == "success"
    assert events[0]["payload"]["state"]["pendingRoll"] is None
    assert [entry["kind"] for entry in events[0]["payload"]["state"]["log"]] == ["roll"]
    assert (
        "".join(event["text"] for event in events[1:-1])
        == "당신은 살펴본 끝에 지금 보이는 것들 사이의 의미 있는 단서를 확인합니다. 장면의 긴장이 짧게 가라앉습니다."
    )
    assert events[-1]["payload"]["state"]["log"][-1] == {
        "id": 2,
        "kind": "gm",
        "text": "당신은 살펴본 끝에 지금 보이는 것들 사이의 의미 있는 단서를 확인합니다. 장면의 긴장이 짧게 가라앉습니다.",
        "outcome": "success",
    }


@pytest.mark.asyncio
async def test_graph_turn_emits_flow_debug_timing_logs(tmp_path, monkeypatch, capsys):
    app = _build_app(tmp_path)

    async with _client(app) as client:
        game_id = await _init_graph_session(client)
        capsys.readouterr()
        response = await client.post(
            f"/session/{game_id}/graph/turn",
            json={"action": {"verb": "move", "to": "loc_02"}},
        )

    assert response.status_code == 200, response.text
    stderr = capsys.readouterr().err

    assert "gid=" in stderr
    assert "turn=0" in stderr
    assert "t=" in stderr
    assert "engine" in stderr
    assert "turn:start action='move'" in stderr
    assert "dispatch:done kind='move'" in stderr
    assert "turn:done status='executed'" in stderr


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
            json={"growth": {"kind": "max_hp"}, "think": False},
        )

    assert response.status_code == 200, response.text
    body = response.json()
    graph = await app.state.graph_repo.load_graph(game_id)
    progress = await app.state.graph_repo.load_progress(game_id)
    logs = await app.state.graph_repo.load_log_entries(game_id)
    player_props = graph.nodes["player_01"].properties

    assert player_props["level"] == level + 1
    assert player_props["xp_pool"] == 0
    assert player_props["max_hp"] == 6
    assert player_props["hp"] == 6
    assert body["outcome"] == "success"
    assert body["state"]["hero"]["level"] == level + 1
    assert body["state"]["hero"]["exp"] == 0
    assert body["state"]["log"] == [entry.model_dump() for entry in logs]
    assert logs[-1].kind == "act"
    assert "레벨이 올랐습니다" in logs[-1].text
    assert progress.next_log_id == logs[-1].id + 1


@pytest.mark.asyncio
async def test_graph_level_up_rejects_legacy_stat_payload(tmp_path):
    app = _build_app(tmp_path)

    async with _client(app) as client:
        game_id = await _init_graph_session(client)
        response = await client.post(
            f"/session/{game_id}/graph/level_up",
            json={"growth": {"kind": "stat", "stat_up": "body"}, "think": False},
        )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_graph_level_up_insufficient_xp_error_is_player_facing(tmp_path):
    app = _build_app(tmp_path)

    async with _client(app) as client:
        game_id = await _init_graph_session(client)
        response = await client.post(
            f"/session/{game_id}/graph/level_up",
            json={"growth": {"kind": "max_hp"}, "think": False},
        )

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail == "아직 레벨을 올릴 만큼 경험치가 충분하지 않습니다."
    assert "not enough xp" not in detail


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
    assert body["state"]["log"] == []
    assert body["suggestions"] == [
        {
            "label": "talk",
            "input_text": "에드릭에게 말을 겁니다",
            "intent": "talk",
            "action": None,
        },
        {
            "label": "move",
            "input_text": "숲길로 이동합니다",
            "intent": "move",
            "action": None,
        },
        {
            "label": "inspect",
            "input_text": "주변을 살핍니다",
            "intent": "inspect",
            "action": None,
        },
    ]


@pytest.mark.asyncio
async def test_graph_state_route_missing_game_returns_404(tmp_path):
    app = _build_app(tmp_path)

    async with _client(app) as client:
        response = await client.get("/session/missing/graph/state")

    assert response.status_code == 404


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
                    "id": "white_isle_llm",
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
                    "id": "white_isle_llm",
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
            "id": "white_isle_llm_override",
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
    assert response.json()["contract"]["id"] == "white_isle_llm_override"
    assert reloaded.status_code == 200, reloaded.text
    assert reloaded.json()["contract"]["id"] == "white_isle_llm_override"
    progress = await app.state.graph_repo.load_progress(game_id)
    assert progress.story_contract_override is not None
    assert progress.story_contract_override["id"] == "white_isle_llm_override"


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
        "changed_edge_ids": ["has_knowledge:loc_fog_harbor:clue_preview"],
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
async def test_graph_turn_invalid_move_error_is_player_facing(tmp_path):
    app = _build_app(tmp_path)

    async with _client(app) as client:
        game_id = await _init_graph_session(client)
        response = await client.post(
            f"/session/{game_id}/graph/turn",
            json={"action": {"verb": "move", "to": "missing_place"}},
        )

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail == "지금은 그 장소로 이동할 수 없습니다. 화면에 보이는 이동 경로를 선택해야 합니다."
    assert "not adjacent" not in detail


@pytest.mark.asyncio
async def test_graph_turn_locked_move_error_is_player_facing(tmp_path):
    app = _build_app(tmp_path)

    async with _client(app) as client:
        game_id = await _init_graph_session(client)
        graph = await app.state.graph_repo.load_graph(game_id)
        graph.edges["connects_to:loc_01:loc_02"].properties["requires_quest"] = "quest_01"
        await app.state.graph_repo.save_graph(game_id, graph)

        response = await client.post(
            f"/session/{game_id}/graph/turn",
            json={"action": {"verb": "move", "to": "loc_02"}},
        )

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail == "지금은 그 장소로 이동할 수 없습니다. 화면에 보이는 이동 경로를 선택해야 합니다."
    assert "locked from current location" not in detail


@pytest.mark.asyncio
async def test_graph_turn_protected_attack_error_is_player_facing(tmp_path):
    app = _build_app(tmp_path)

    async with _client(app) as client:
        game_id = await _init_graph_session(client)
        graph = await app.state.graph_repo.load_graph(game_id)
        graph.nodes["edrik_chief"].properties["protected"] = True
        await app.state.graph_repo.save_graph(game_id, graph)

        response = await client.post(
            f"/session/{game_id}/graph/turn",
            json={"action": {"verb": "attack", "what": "edrik_chief"}},
        )

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail == "보호받는 대상이라 지금은 공격할 수 없습니다. 대화하거나 주변을 살피면 다른 방법을 찾을 수 있습니다."
    assert "protected target" not in detail


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
    assert body["outcome"] == "neutral"
    assert "payload" not in body["state"]["pendingConfirmation"]
    assert progress.pending_confirmation["kind"] == "attack_start"
    assert progress.graph_combat_state is None
    assert progress.turn_count == 0


@pytest.mark.asyncio
async def test_graph_turn_pending_confirmation_error_is_player_facing(tmp_path):
    app = _build_app(tmp_path)

    async with _client(app) as client:
        game_id = await _init_graph_session(client)
        await client.post(
            f"/session/{game_id}/graph/turn",
            json={"action": {"verb": "attack", "what": "edrik_chief"}},
        )
        response = await client.post(
            f"/session/{game_id}/graph/turn",
            json={"action": {"verb": "move", "to": "loc_02"}},
        )

    assert response.status_code == 409
    detail = response.json()["detail"]
    assert detail == "먼저 현재 확인을 완료해야 합니다."
    assert "pending_confirmation" not in detail


@pytest.mark.asyncio
async def test_graph_input_pending_roll_error_is_player_facing(tmp_path):
    app = _build_app(tmp_path)

    async with _client(app) as client:
        game_id = await _init_graph_session(client)
        await client.post(
            f"/session/{game_id}/graph/turn",
            json={"action": {"verb": "perceive", "what": "loc_01"}},
        )
        response = await client.post(
            f"/session/{game_id}/graph/input",
            json={"player_input": "일단 숲길로 간다"},
        )

    assert response.status_code == 409
    detail = response.json()["detail"]
    assert detail == "먼저 현재 판정을 진행해야 합니다."
    assert "pending_roll" not in detail


@pytest.mark.asyncio
async def test_graph_confirm_missing_pending_error_is_player_facing(tmp_path):
    app = _build_app(tmp_path)

    async with _client(app) as client:
        game_id = await _init_graph_session(client)
        response = await client.post(
            f"/session/{game_id}/graph/confirm",
            json={"confirmation_id": "missing", "decision": "confirm"},
        )

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail == "현재 확인할 선택지가 없습니다."
    assert "pending_confirmation" not in detail


@pytest.mark.asyncio
async def test_graph_roll_mismatch_error_is_player_facing(tmp_path):
    app = _build_app(tmp_path)

    async with _client(app) as client:
        game_id = await _init_graph_session(client)
        await client.post(
            f"/session/{game_id}/graph/turn",
            json={"action": {"verb": "perceive", "what": "loc_01"}},
        )
        response = await client.post(
            f"/session/{game_id}/graph/roll",
            json={"roll_id": "stale"},
        )

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail == "현재 판정이 바뀌었습니다. 화면의 판정을 다시 선택해야 합니다."
    assert "roll id mismatch" not in detail


@pytest.mark.asyncio
async def test_graph_combat_rejects_when_not_in_combat(tmp_path):
    app = _build_app(tmp_path)

    async with _client(app) as client:
        game_id = await _init_graph_session(client)
        response = await client.post(
            f"/session/{game_id}/graph/combat",
            json={"command": "defend"},
        )

    assert response.status_code == 422
    assert "combat is not active" in response.text


@pytest.mark.asyncio
async def test_graph_combat_stream_rejects_when_not_in_combat(tmp_path):
    app = _build_app(tmp_path)

    async with _client(app) as client:
        game_id = await _init_graph_session(client)
        response = await client.post(
            f"/session/{game_id}/graph/combat/stream",
            json={"command": "defend"},
        )

    assert response.status_code == 200
    assert '"type": "error"' in response.text
    assert "combat is not active" in response.text


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
    assert body["state"]["combat"]["round"] == 1
    assert body["state"]["combat"]["lastRoll"] is None
    assert progress.pending_confirmation is None
    assert progress.graph_combat_state is not None
    assert progress.graph_combat_state.round == 1
    assert progress.graph_combat_state.last_roll is None
    assert progress.turn_count == 1


@pytest.mark.asyncio
async def test_graph_confirm_stream_returns_result_before_narration_deltas(tmp_path):
    app = _build_app(tmp_path)

    async with _client(app) as client:
        game_id = await _init_graph_session(client)
        attack_response = await client.post(
            f"/session/{game_id}/graph/turn",
            json={"action": {"verb": "attack", "what": "edrik_chief"}},
        )
        confirmation_id = attack_response.json()["state"]["pendingConfirmation"]["id"]
        response = await client.post(
            f"/session/{game_id}/graph/confirm/stream",
            json={"confirmation_id": confirmation_id, "decision": "confirm"},
        )

    assert response.status_code == 200, response.text
    events = [json.loads(line) for line in response.text.splitlines()]

    assert [event["type"] for event in events] == [
        "result",
        "narration_delta",
        "narration_delta",
        "final",
    ]
    assert events[0]["payload"]["status"] == "executed"
    assert events[0]["payload"]["outcome"] == "neutral"
    assert events[0]["payload"]["state"]["log"][-1]["kind"] == "act"
    assert (
        "".join(event["text"] for event in events[1:3])
        == "장면의 긴장이 짧게 가라앉습니다."
    )
    assert events[-1]["payload"]["status"] == "executed"
    assert events[-1]["payload"]["outcome"] == "neutral"
    assert (
        events[-1]["payload"]["state"]["log"][-1]["text"]
        == "장면의 긴장이 짧게 가라앉습니다."
    )


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
    assert body["state"]["combat"]["round"] == 2
    assert progress.graph_combat_state is not None
    assert progress.graph_combat_state.round == 2


@pytest.mark.asyncio
async def test_graph_turn_auto_skill_uses_known_skill_during_existing_combat(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr("src.game.engines.graph.combat.randint", lambda _a, _b: 20)
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
            json={"action": {"verb": "attack", "what": "edrik_chief", "how": "auto"}},
        )

    assert response.status_code == 200, response.text
    progress = await app.state.graph_repo.load_progress(game_id)

    assert progress.graph_combat_state is not None
    assert progress.graph_combat_state.last_support_id == "basic_strike"
    assert progress.graph_combat_state.last_support_kind == "skill"


@pytest.mark.asyncio
async def test_graph_turn_flee_success_ends_combat(tmp_path, monkeypatch):
    monkeypatch.setattr("src.game.engines.graph.combat.randint", lambda _a, _b: 20)
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
                "slot": "weapon",
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
                "effect": "heal",
                "amount": 8,
            },
        )
        graph.nodes["heal"] = GraphNode(
            id="heal",
            type="effect",
            properties={"kind": "heal"},
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
async def test_graph_input_refuse_returns_in_game_rejection_not_http_error(tmp_path):
    app = _build_app(
        tmp_path,
        llm_payload={
            "refuse": {
                "category": "out_of_game",
                "message_hint": "그 행동은 이 세계에서 처리할 수 없습니다.",
            }
        },
    )

    async with _client(app) as client:
        game_id = await _init_graph_session(client)
        response = await client.post(
            f"/session/{game_id}/graph/input",
            json={"player_input": "허리에서 권총을 꺼내 든다"},
        )

    assert response.status_code == 200, response.text
    body = response.json()
    progress = await app.state.graph_repo.load_progress(game_id)

    assert body["status"] == "rejected"
    assert body["outcome"] == "failure"
    assert body["state"]["pendingConfirmation"] is None
    assert body["state"]["pendingRoll"] is None
    assert progress.turn_count == 1


@pytest.mark.asyncio
async def test_graph_input_stream_returns_result_before_narration_deltas(tmp_path):
    app = _build_app(
        tmp_path,
        llm_payload={"actions": [{"verb": "speak", "what": "edrik_chief"}]},
    )

    async with _client(app) as client:
        game_id = await _init_graph_session(client)
        response = await client.post(
            f"/session/{game_id}/graph/input/stream",
            json={"player_input": "에드릭에게 말을 건다", "think": False},
        )

    assert response.status_code == 200, response.text
    events = [json.loads(line) for line in response.text.splitlines()]

    assert [event["type"] for event in events] == [
        "result",
        "narration_delta",
        "narration_delta",
        "final",
    ]
    assert events[0]["payload"]["game_id"] == game_id
    assert events[0]["payload"]["status"] == "executed"
    assert events[0]["payload"]["outcome"] == "neutral"
    assert events[0]["payload"]["state"]["log"] == [
        {
            "id": 1,
            "kind": "player",
            "text": "에드릭에게 말을 건다",
        }
    ]
    assert (
        "".join(event["text"] for event in events[1:3])
        == "장면의 긴장이 짧게 가라앉습니다."
    )
    assert events[-1]["payload"]["game_id"] == game_id
    assert events[-1]["payload"]["status"] == "executed"
    assert events[-1]["payload"]["state"]["log"][-1] == {
        "id": 2,
        "kind": "gm",
        "text": "장면의 긴장이 짧게 가라앉습니다.",
    }


@pytest.mark.asyncio
async def test_graph_input_returns_reflected_suggestions(tmp_path):
    app = _build_app(
        tmp_path,
        llm_payload={"actions": [{"verb": "speak", "what": "edrik_chief"}]},
        narration_meta={
            "turn_summary": "에드릭이 숲길의 의뢰를 암시했습니다.",
            "importance": 2,
            "suggestions": [
                {
                    "label": "숲길로",
                    "input_text": "숲길로 이동합니다",
                    "intent": "move",
                    "action": None,
                },
                {
                    "label": "보상 묻기",
                    "input_text": "에드릭에게 보상을 묻습니다",
                },
            ],
        },
    )

    async with _client(app) as client:
        game_id = await _init_graph_session(client)
        response = await client.post(
            f"/session/{game_id}/graph/input",
            json={"player_input": "에드릭에게 말을 건다", "think": False},
        )

    assert response.status_code == 200, response.text
    body = response.json()
    history = await app.state.graph_repo.load_history_entries(game_id)

    assert body["suggestions"] == [
        {
            "label": "숲길로",
            "input_text": "숲길로 이동합니다",
            "intent": "move",
            "action": None,
        }
    ]
    assert history[0].summary == "에드릭이 숲길의 의뢰를 암시했습니다."
    assert history[0].importance == 2


@pytest.mark.asyncio
async def test_graph_move_does_not_generate_auto_quest_with_graph_state(tmp_path):
    app = _build_app(tmp_path)

    async with _client(app) as client:
        game_id = await _init_graph_session(client)

        move_response = await client.post(
            f"/session/{game_id}/graph/turn",
            json={"action": {"verb": "move", "to": "loc_02"}},
        )
        assert move_response.status_code == 200, move_response.text
        move_body = move_response.json()

    graph = await app.state.graph_repo.load_graph(game_id)
    progress = await app.state.graph_repo.load_progress(game_id)
    logs = await app.state.graph_repo.load_log_entries(game_id)

    assert move_body["state"]["quest"] is None
    assert move_body["state"]["questOffers"] == []
    assert not any(node_id.startswith("auto_") for node_id in graph.nodes)
    assert progress.active_quest_id is None
    assert progress.graph_combat_state is None
    assert [entry.kind for entry in logs] == ["act", "gm"]
    assert logs[0].text == "당신은 숲길로 이동합니다."
