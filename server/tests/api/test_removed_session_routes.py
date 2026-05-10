import pytest
from httpx import ASGITransport, AsyncClient

from run_api import build_app
from src.db.graph_local_fs import LocalFsGraphRepo
from tests._fakes import make_default_storage, make_scenario_repo


class _NoopLLM:
    async def chat(
        self,
        messages,
        think=False,
        agent=None,
        temperature=None,
        use_fallback=False,
    ):
        if agent == "graph_intro":
            return {"answer": "당신은 광장에 들어섭니다.", "think": ""}
        return {"answer": "{}", "think": ""}


def _build_test_app(tmp_path):
    scenario_repo, _ = make_scenario_repo(make_default_storage())
    return build_app(
        llm=_NoopLLM(),
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


@pytest.mark.asyncio
async def test_removed_session_routes_are_not_mounted(tmp_path):
    app = _build_test_app(tmp_path)

    async with _client(app) as client:
        init_response = await client.post("/session/init", json={})
        turn_response = await client.post("/session/game-1/turn", json={})
        roll_response = await client.post("/session/game-1/roll", json={})
        intro_response = await client.post("/session/game-1/intro", json={})
        preview_response = await client.get("/session/game-1/level_up_preview")
        level_up_response = await client.post("/session/game-1/level_up", json={})

    assert init_response.status_code == 404
    assert turn_response.status_code == 404
    assert roll_response.status_code == 404
    assert intro_response.status_code == 404
    assert preview_response.status_code == 404
    assert level_up_response.status_code == 404


@pytest.mark.asyncio
async def test_graph_session_routes_remain_mounted(tmp_path):
    app = _build_test_app(tmp_path)

    async with _client(app) as client:
        response = await client.post(
            "/session/graph/init",
            json={
                "profile": "default",
                "player": {"name": "테스터", "race_id": "human", "gender": "female"},
            },
        )

    assert response.status_code == 200, response.text
