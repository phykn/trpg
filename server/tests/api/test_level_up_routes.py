"""Tests for the level-up routes (preview + commit)."""

import json

import pytest
from httpx import ASGITransport, AsyncClient

from run_api import build_app
from tests._fakes import make_default_storage, make_save_repo, make_scenario_repo


# Recommend agent returns 3 SkillCandidate-shape objects.
_RECOMMEND_OUTPUT = json.dumps({
    "candidates": [
        {
            "name": "강타",
            "description": "근력 기반 일격",
            "type": "attack",
            "target": "single",
            "primary_stat": "STR",
            "special_effect": "추가 피해",
        },
        {
            "name": "방패막기",
            "description": "한 턴 피해 절반",
            "type": "buff",
            "target": "self",
            "primary_stat": "CON",
            "special_effect": "방어 증가",
        },
        {
            "name": "전투 함성",
            "description": "주변 적 사기 약화",
            "type": "debuff",
            "target": "area",
            "primary_stat": "CHA",
            "special_effect": "공격력 감소",
        },
    ],
}, ensure_ascii=False)


# Narrate stub for /level_up — minimal body + valid JSON tail.
_NARRATE_BODY = "당신의 손에 새로운 힘이 깃듭니다."
_NARRATE_OUTPUT_JSON = json.dumps(
    {"turn_summary": "레벨업", "memorable": False, "suggestions": []},
    ensure_ascii=False,
)
_NARRATE_FULL = f"{_NARRATE_BODY}---JSON---{_NARRATE_OUTPUT_JSON}"


class _MockLLM:
    """Returns recommend payload from chat(), narrate stream from chat_stream()."""

    async def chat(self, messages, think=False, agent=None, temperature=None):
        return {"answer": _RECOMMEND_OUTPUT, "think": ""}

    async def chat_stream(self, messages, think=False, agent=None, temperature=None):
        mid = len(_NARRATE_FULL) // 2
        for piece in (_NARRATE_FULL[:mid], _NARRATE_FULL[mid:]):
            yield {"answer": piece, "think": ""}


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


async def _seed_levelable_player(client) -> str:
    """Init a session via the real /session/init route, then patch the player
    so they can level up (xp_pool >= xp_for_next_level(level))."""
    init_res = await client.post(
        "/session/init",
        json={
            "profile": "default",
            "player": {"name": "테스터", "race_id": "human", "gender": "male"},
        },
    )
    assert init_res.status_code == 200, init_res.text
    game_id = init_res.json()["game_id"]

    # Patch the persisted state's player to be levelable.
    app = client._transport.app
    save_repo = app.state.save_repo
    state_obj = await save_repo.load_game(game_id)
    p = state_obj.characters[state_obj.player_id]
    p.xp_pool = 9999  # plenty for several levels
    await save_repo.save_entity(state_obj, "characters", p.id)
    await save_repo.save_meta(state_obj)

    return game_id


@pytest.mark.asyncio
async def test_level_up_preview_returns_three_candidates():
    app = _build_app()
    async with _client(app) as client:
        game_id = await _seed_levelable_player(client)
        res = await client.get(f"/session/{game_id}/level_up_preview")
        assert res.status_code == 200, res.text
        body = res.json()
        assert len(body["skill_candidates"]) == 3
        for c in body["skill_candidates"]:
            assert "id" in c and c["id"]
            assert "name" in c
            assert "type" in c
            assert "target" in c
            assert "primary_stat" in c


async def _drain(response):
    events = []
    async for line in response.aiter_lines():
        if line.startswith("data: "):
            events.append(json.loads(line[6:]))
    return events


@pytest.mark.asyncio
async def test_level_up_post_streams_events_and_commits():
    app = _build_app()
    async with _client(app) as client:
        game_id = await _seed_levelable_player(client)

        async with client.stream(
            "POST",
            f"/session/{game_id}/level_up",
            json={"stat_up": "STR", "skill_id": None, "think": False},
        ) as response:
            assert response.status_code == 200, await response.aread()
            events = await _drain(response)

        kinds = [ev["type"] for ev in events]
        assert "log_entry" in kinds  # level-up act log entry
        assert "done" in kinds

        # Verify state mutation persisted.
        save_repo = app.state.save_repo
        state_obj = await save_repo.load_game(game_id)
        p = state_obj.characters[state_obj.player_id]
        assert p.level == 1  # bumped from 0
