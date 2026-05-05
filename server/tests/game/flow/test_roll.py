import random

import pytest

from src.game.domain.entities import Character, Connection, Location, Stats
from src.game.domain.memory import PendingCheck
from src.game.flow.dirty import Dirty
from src.game.flow.roll import _apply_movement_roll_outcome, run_roll
from src.db.local_fs import LocalFsSaveRepo, LocalFsScenarioRepo


def _build_state(fresh_state):
    fresh_state.player_id = "player_01"
    fresh_state.locations["plaza_01"] = Location(
        id="plaza_01",
        name="광장",
        connections=[Connection(target_id="gate_01")],
    )
    fresh_state.locations["gate_01"] = Location(
        id="gate_01",
        name="성문",
        connections=[Connection(target_id="plaza_01")],
    )
    fresh_state.characters["player_01"] = Character(
        id="player_01",
        name="주",
        race_id="human",
        stats=Stats(),
        location_id="plaza_01",
    )
    return fresh_state


def _pending(targets: list[str], **overrides) -> PendingCheck:
    base = dict(
        player_input="가본다",
        tier="normal",
        stat="DEX",
        target="gate_01",
        targets=targets,
        dc=10,
        mod=0,
        required_roll=10,
        reason="",
        created_at="2026-01-01T00:00:00Z",
    )
    base.update(overrides)
    return PendingCheck(**base)


def test_roll_movement_marks_destination_visited(fresh_state):
    # Movement-roll path goes through apply_changes with a `move` state_change.
    # The engine-level fix in _apply_move now centralizes the visited update
    # so this caller doesn't need to remember it.
    state = _build_state(fresh_state)
    pending = _pending(["gate_01"])
    _apply_movement_roll_outcome(state, pending, "success", Dirty())
    assert state.characters["player_01"].location_id == "gate_01"
    assert "gate_01" in state.characters["player_01"].visited_location_ids


def test_roll_movement_failure_does_not_visit(fresh_state):
    # A failed movement roll keeps the player in place — no visit recorded.
    state = _build_state(fresh_state)
    pending = _pending(["gate_01"])
    _apply_movement_roll_outcome(state, pending, "failure", Dirty())
    assert state.characters["player_01"].location_id == "plaza_01"
    assert "gate_01" not in state.characters["player_01"].visited_location_ids


# ---------------------------------------------------------------------------
# bonus_breakdown — the result label must explain how die + bonuses sum.


class _NullRng:
    """rng.randint(1, 20) returns the value we picked at construction time."""

    def __init__(self, value: int) -> None:
        self._value = value

    def randint(self, a: int, b: int) -> int:
        return self._value


@pytest.fixture
def stub_narrate(monkeypatch):
    from src.game.flow import roll as roll_mod

    async def _noop(*a, **kw):
        if False:
            yield None  # async-gen marker

    monkeypatch.setattr(roll_mod, "run_narrate", _noop)


@pytest.fixture
def stub_consume_narrate(monkeypatch):
    from src.game.flow import roll as roll_mod

    async def _noop(*a, **kw):
        if False:
            yield None

    monkeypatch.setattr(roll_mod, "consume_narrate", _noop)


async def _drain(it):
    return [ev async for ev in it]


@pytest.fixture
def repos(tmp_data):
    save_repo = LocalFsSaveRepo(tmp_data)
    scenario_repo = LocalFsScenarioRepo(tmp_data)
    return save_repo, scenario_repo


@pytest.mark.asyncio
async def test_bonus_breakdown_includes_die_and_stat_modifier(
    fresh_state, repos, stub_narrate, stub_consume_narrate
):
    """Player CHA 14 → +2 stat modifier. Result row must show
    `주사위 14, 매력 +2` so the stat sheet visibly contributes to the math."""
    save_repo, scenario_repo = repos
    state = _build_state(fresh_state)
    state.characters["player_01"].stats = Stats(CHA=14)
    state.pending_check = _pending(
        ["gate_01"], stat="CHA", target="player_01", dc=12, mod=0, required_roll=10
    )

    events = await _drain(
        run_roll(
            client=None,
            state=state,
            scenario_repo=scenario_repo,
            save_repo=save_repo,
            rng=_NullRng(14),
        )
    )
    log_events = [e for e in events if e["type"] == "log_entry"]
    assert log_events, "no log_entry emitted"
    roll = log_events[0]["data"]
    assert roll["kind"] == "roll"
    assert roll["roll"] == 14
    assert roll["bonus_breakdown"] == [
        {"label": "주사위", "value": 14},
        {"label": "매력", "value": 2},
    ]


@pytest.mark.asyncio
async def test_bonus_breakdown_appends_social_when_nonzero(
    fresh_state, repos, stub_narrate, stub_consume_narrate
):
    """An NPC with high affinity grants +2 social bonus → the result row
    surfaces `호감 +2` alongside the die and stat rows."""
    save_repo, scenario_repo = repos
    state = _build_state(fresh_state)
    state.characters["player_01"].stats = Stats(CHA=10)
    state.pending_check = _pending(
        ["gate_01"], stat="CHA", target="player_01", dc=10, mod=2, required_roll=8
    )

    events = await _drain(
        run_roll(
            client=None,
            state=state,
            scenario_repo=scenario_repo,
            save_repo=save_repo,
            rng=_NullRng(8),
        )
    )
    roll = next(e["data"] for e in events if e["type"] == "log_entry")
    assert roll["bonus_breakdown"] == [
        {"label": "주사위", "value": 8},
        {"label": "매력", "value": 0},
        {"label": "호감", "value": 2},
    ]


@pytest.mark.asyncio
async def test_bonus_breakdown_omits_social_when_zero(
    fresh_state, repos, stub_narrate, stub_consume_narrate
):
    """No social bonus → only die + stat rows. We don't emit `호감 +0`."""
    save_repo, scenario_repo = repos
    state = _build_state(fresh_state)
    state.characters["player_01"].stats = Stats(STR=10)
    state.pending_check = _pending(
        ["gate_01"], stat="STR", target="gate_01", dc=10, mod=0, required_roll=10
    )

    events = await _drain(
        run_roll(
            client=None,
            state=state,
            scenario_repo=scenario_repo,
            save_repo=save_repo,
            rng=_NullRng(10),
        )
    )
    roll = next(e["data"] for e in events if e["type"] == "log_entry")
    labels = [b["label"] for b in roll["bonus_breakdown"]]
    assert labels == ["주사위", "근력"]


def test_bonus_breakdown_sum_matches_total_against_dc(fresh_state):
    """Math invariant: sum(breakdown) − DC equals the displayed margin."""
    from src.game.domain.memory import BonusItem, RollLogEntry
    from src.game.engines.combat import stat_modifier
    from src.game.rules.dc import compute_required_roll

    stat_value = 14
    dice = 12
    social = 2
    dc = 11

    required = compute_required_roll(dc, stat_value)  # 11 - 2 = 9
    total = dice + social  # 14, vs required 9 → margin +5
    breakdown = [
        BonusItem(label="주사위", value=dice),
        BonusItem(label="매력", value=stat_modifier(stat_value)),
        BonusItem(label="호감", value=social),
    ]
    entry = RollLogEntry(
        id=1,
        kind="roll",
        check="매력",
        roll=dice,
        margin=total - required,
        result="success",
        bonus_breakdown=breakdown,
    )
    assert sum(b.value for b in entry.bonus_breakdown) - dc == entry.margin


# Silence unused-import warnings — the random module is a placeholder for
# future test cases that need real RNG; _NullRng covers the deterministic ones.
_ = random
