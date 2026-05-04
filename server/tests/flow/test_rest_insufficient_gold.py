"""C1 — run_rest catches RestInsufficientGold and emits Korean GM line."""

import pytest

from src.domain.entities import Character, Location, Race, Stats
from src.domain.state import GameState
from src.flow.dirty import Dirty
from src.flow.rest import run_rest
from src.persistence.local_fs import LocalFsSaveRepo, LocalFsScenarioRepo


def _make_state(gold: int = 0) -> GameState:
    state = GameState(game_id="t", profile="test", player_id="player")
    state.locations["safe_room"] = Location(
        id="safe_room",
        name="안전한 방",
        description="",
        sleep_risk="safe",
        sleep_encounters=[],
    )
    state.races["human"] = Race(id="human", name="인간", description="")
    actor = Character(
        id="player",
        name="주인공",
        race_id="human",
        stats=Stats(),
        gold=gold,
        hp=5,
        max_hp=20,
        mp=5,
        max_mp=15,
        location_id="safe_room",
    )
    state.characters[actor.id] = actor
    state.invalidate_graph()
    return state


@pytest.mark.asyncio
async def test_run_rest_with_insufficient_gold_emits_korean_refusal(tmp_path):
    """run_rest catches RestInsufficientGold and yields a Korean GM act
    line; HP/MP unchanged, no combat triggered."""
    state = _make_state(gold=5)
    actor = state.characters[state.player_id]

    save_repo = LocalFsSaveRepo(saves_dir=str(tmp_path / "saves"))
    scenario_repo = LocalFsScenarioRepo(profile_dir=str(tmp_path / "scenarios"))
    dirty = Dirty()

    events = []
    async for ev in run_rest(
        state, scenario_repo, save_repo, dirty, rng=None, to_front_fn=None
    ):
        events.append(ev)

    act_events = [
        e for e in events if e["type"] == "log_entry" and e["data"].get("kind") == "act"
    ]
    assert any(
        "금화가 부족합니다" in (e["data"].get("text") or "") for e in act_events
    ), f"No Korean refusal: {[e['data'].get('text') for e in act_events]}"

    assert actor.gold == 5
    assert actor.hp == 5
    assert actor.mp == 5
    # Rest did not advance the recovery branch — combat was never triggered.
    assert state.combat_state is None
