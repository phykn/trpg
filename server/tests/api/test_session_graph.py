import pytest
from httpx import ASGITransport, AsyncClient

from run_api import build_app
from tests._fakes import make_default_storage, make_save_repo, make_scenario_repo


class _MockLLM:
    async def chat(self, messages, think=False, agent=None):
        return {"answer": "{}", "think": ""}

    async def chat_stream(self, messages, think=False, agent=None):
        if False:
            yield {"answer": "", "think": ""}


def _build_app():
    save_repo, _ = make_save_repo()
    scenario_repo, _ = make_scenario_repo(make_default_storage())
    return build_app(
        llm=_MockLLM(),
        basic_auth_user="t",
        basic_auth_pass="t",
        save_repo=save_repo,
        scenario_repo=scenario_repo,
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
async def test_session_graph_returns_story_graph_payload():
    app = _build_app()
    async with _client(app) as client:
        init = await client.post(
            "/session/init",
            json={
                "profile": "default",
                "player": {"name": "P", "race_id": "human", "gender": "male"},
            },
        )
        assert init.status_code == 200, init.text
        game_id = init.json()["game_id"]

        resp = await client.get(f"/session/{game_id}/graph")

    assert resp.status_code == 200, resp.text
    payload = resp.json()
    assert set(payload) == {"nodes", "edges", "summary"}
    assert payload["summary"].startswith("주인공")
    assert any(node["kind"] == "hero" for node in payload["nodes"])
    assert any(edge["label"] == "현재 위치" for edge in payload["edges"])


@pytest.mark.asyncio
async def test_session_graph_missing_game_is_404():
    app = _build_app()
    async with _client(app) as client:
        resp = await client.get("/session/missing/graph")

    assert resp.status_code == 404
