import pytest

from src.game.domain.entities import Character, Location, Race, Skill, Stats
from src.game.domain.memory import PendingCheck
from src.game.domain.state import GameState
from src.game.flow.level_up import run_level_up


class _FakeRepo:
    """No-op SaveRepo — finalize.flush() is a coroutine chain we don't exercise here."""

    async def save_entity(self, *a, **kw):
        pass

    async def append_log_entries(self, *a, **kw):
        pass

    async def append_history_entries(self, *a, **kw):
        pass

    async def append_dialogue_entries(self, *a, **kw):
        pass

    async def save_meta(self, *a, **kw):
        pass

    async def load_game(self, *a, **kw):
        pass


def _player_state(*, xp_pool: int = 200, pending_check=None) -> GameState:
    state = GameState(
        game_id="g_test",
        profile="p_test",
        player_id="player_01",
    )
    state.locations["loc_01"] = Location(id="loc_01", name="광장")
    state.races["race_human"] = Race(id="race_human", name="인간", description="")
    p = Character(
        id="player_01",
        name="당신",
        race_id="race_human",
        location_id="loc_01",
        stats=Stats(STR=10, CHA=10),
        is_player=True,
        level=2,
        xp_pool=xp_pool,
    )
    p.max_hp = p.hp = 28
    p.max_mp = p.mp = 11
    state.characters["player_01"] = p
    state.pending_check = pending_check
    return state


@pytest.mark.asyncio
async def test_run_level_up_applies_stat_change_and_emits_log_entry(monkeypatch):
    state = _player_state()

    # narrate is heavy and LLM-dependent — stub it out.
    from src.game.flow import level_up as level_up_mod

    async def _no_narrate(*a, **kw):
        if False:
            yield None  # async-gen marker

    monkeypatch.setattr(level_up_mod, "run_narrate", _no_narrate)

    events = []
    async for ev in run_level_up(
        client=None,
        state=state,
        scenario_repo=None,
        save_repo=_FakeRepo(),
        stat_up="STR",
        skill_id=None,
    ):
        events.append(ev)

    p = state.characters["player_01"]
    assert p.level == 3
    assert p.stats.STR == 11
    assert p.stats.CHA == 9
    log_kinds = [ev["data"].get("kind") for ev in events if ev["type"] == "log_entry"]
    assert "act" in log_kinds


@pytest.mark.asyncio
async def test_run_level_up_rejects_when_pending_check_active(monkeypatch):
    state = _player_state(
        pending_check=PendingCheck(
            kind="stat",
            dc=10,
            stat="STR",
            mod=0,
            required_roll=10,
            tier="normal",
            target="player_01",
            reason="t",
            targets=[],
            player_input="t",
            created_at="2026-01-01T00:00:00Z",
        )
    )

    events = [
        ev
        async for ev in run_level_up(
            client=None,
            state=state,
            scenario_repo=None,
            save_repo=_FakeRepo(),
            stat_up="STR",
            skill_id=None,
        )
    ]

    error_events = [ev for ev in events if ev["type"] == "error"]
    assert len(error_events) == 1
    assert "PendingCheckActive" in error_events[0]["data"]["code"]
    p = state.characters["player_01"]
    assert p.level == 2  # unchanged


@pytest.mark.asyncio
async def test_run_level_up_learns_skill_when_id_provided(monkeypatch):
    state = _player_state()
    state.skills["skill_test"] = Skill(
        id="skill_test",
        name="강타",
        type="attack",
        target="single",
        primary_stat="STR",
    )

    from src.game.flow import level_up as level_up_mod

    async def _no_narrate(*a, **kw):
        if False:
            yield None

    monkeypatch.setattr(level_up_mod, "run_narrate", _no_narrate)

    async for _ in run_level_up(
        client=None,
        state=state,
        scenario_repo=None,
        save_repo=_FakeRepo(),
        stat_up="STR",
        skill_id="skill_test",
    ):
        pass

    p = state.characters["player_01"]
    assert "skill_test" in p.learned_skill_ids


@pytest.mark.asyncio
async def test_run_level_up_invalid_stat_emits_error(monkeypatch):
    state = _player_state(xp_pool=0)  # not enough xp

    events = [
        ev
        async for ev in run_level_up(
            client=None,
            state=state,
            scenario_repo=None,
            save_repo=_FakeRepo(),
            stat_up="STR",
            skill_id=None,
        )
    ]

    error_events = [ev for ev in events if ev["type"] == "error"]
    assert len(error_events) >= 1
    assert error_events[0]["data"]["code"] == "LevelUpInvalid"


@pytest.mark.asyncio
async def test_run_level_up_yields_error_and_finalizes_when_narrate_fails(monkeypatch):
    """Narrate-side LLM failure must not abort before finalize — stat change is already
    committed engine-side and must be persisted."""
    from src.game.domain.errors import LLMUnavailable
    from src.game.flow import level_up as level_up_mod

    state = _player_state()

    async def _failing_narrate(*a, **kw):
        raise LLMUnavailable("simulated provider outage")
        if False:
            yield None  # async-gen marker

    monkeypatch.setattr(level_up_mod, "run_narrate", _failing_narrate)

    class _Stub:
        pass

    events = [
        ev
        async for ev in run_level_up(
            client=_Stub(),
            state=state,
            scenario_repo=_Stub(),
            save_repo=_FakeRepo(),
            stat_up="STR",
            skill_id=None,
        )
    ]

    error_events = [ev for ev in events if ev["type"] == "error"]
    done_events = [ev for ev in events if ev["type"] == "done"]
    assert len(error_events) == 1
    assert error_events[0]["data"]["code"] == "LLMUnavailable"
    assert len(done_events) == 1  # finalize still ran
    p = state.characters["player_01"]
    assert p.level == 3  # stat change committed
