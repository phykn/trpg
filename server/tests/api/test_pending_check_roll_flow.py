"""Regression guard: /roll requires a JSON body.

The QA harness once called `client.stream("POST", ".../roll")` with no body,
which FastAPI rejected as 422 (RollRequest is a required model). The 422
arrived as `application/json` not SSE, so the harness's `_drain_sse` saw zero
"data: " lines and returned 0 events. The server-side pending_check stayed
armed and the next /turn raised PendingCheckActive (provocateur T4 / mourner
T20).

This test pins the contract: empty `json={}` works (harness path), no-body
returns 422 (the trap that bit us — keep it visible so future contract
relaxation is a deliberate choice, not silent regression).
"""

import json

import pytest
from httpx import ASGITransport, AsyncClient

from run_api import build_app
from tests._fakes import make_default_storage, make_save_repo, make_scenario_repo


_JUDGE_ROLL = json.dumps(
    {
        "action": "roll",
        "tier": "쉬움",
        "stat": "CHA",
        "targets": ["edrik_chief"],
        "reason": "테스트",
    },
    ensure_ascii=False,
)

_NARRATE_BODY = "당신은 에드릭에게 인사합니다."
_NARRATE_OUTPUT_JSON = json.dumps(
    {"turn_summary": "인사", "memorable": False},
    ensure_ascii=False,
)
_NARRATE_FULL = f"{_NARRATE_BODY}---JSON---{_NARRATE_OUTPUT_JSON}"


class _MockLLM:
    async def chat(self, messages, think=False, agent=None, temperature=None, use_fallback=False):
        return {"answer": _JUDGE_ROLL, "think": ""}

    async def chat_stream(self, messages, think=False, agent=None, temperature=None, use_fallback=False):
        mid = len(_NARRATE_FULL) // 2
        for piece in (_NARRATE_FULL[:mid], _NARRATE_FULL[mid:]):
            yield {"answer": piece, "think": ""}


async def _drain(response):
    events = []
    async for line in response.aiter_lines():
        if line.startswith("data: "):
            events.append(json.loads(line[6:]))
    return events


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


async def _init_and_arm_pending_check(client):
    init = await client.post(
        "/session/init",
        json={
            "profile": "default",
            "player": {"name": "P", "race_id": "human", "gender": "male"},
        },
    )
    assert init.status_code == 200, init.text
    gid = init.json()["game_id"]

    async with client.stream(
        "POST",
        f"/session/{gid}/turn",
        json={"player_input": "에드릭에게 인사한다"},
    ) as r:
        turn_events = await _drain(r)
    assert any(e["type"] == "pending_check" for e in turn_events), (
        f"setup failed — expected pending_check; got {[e['type'] for e in turn_events]}"
    )
    return gid


@pytest.mark.asyncio
async def test_roll_with_empty_json_body_streams_events():
    """The fix path: harness now sends `json={}` and gets a real SSE stream."""
    app = _build_app()
    async with _client(app) as client:
        gid = await _init_and_arm_pending_check(client)

        async with client.stream("POST", f"/session/{gid}/roll", json={}) as r:
            assert r.status_code == 200
            events = await _drain(r)

    types = [e["type"] for e in events]
    assert "log_entry" in types, f"missing roll log_entry; got {types}"
    assert "narrative_delta" in types, f"missing narrative_delta; got {types}"


@pytest.mark.asyncio
async def test_roll_without_body_is_422_not_sse():
    """The trap: no body → 422 application/json, not SSE. Pinning this so any
    future move to make the body optional is a deliberate, tested change."""
    app = _build_app()
    async with _client(app) as client:
        gid = await _init_and_arm_pending_check(client)

        resp = await client.post(f"/session/{gid}/roll")
        assert resp.status_code == 422
        assert resp.headers["content-type"].startswith("application/json")
        detail = resp.json()["detail"]
        assert any(d.get("loc") == ["body"] for d in detail)
