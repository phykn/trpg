"""Regression: /roll on a `combat_roll` pending check must run end-to-end.

The combat_roll arm of `_resolve_combat_roll` reaches `sigmoid_required_roll`
through `compute_grade`'s third arg. A previous version forgot to import
that name from `..rules.dc` — the live combat path then NameError'd the
moment a pending combat roll resolved. No end-to-end test exercised the arm,
so the suite stayed green while production was broken.
"""
import random
import tempfile

import pytest

from src.domain.entities import Character, Stats
from src.domain.memory import PendingCheck
from src.flow.roll import run_roll


@pytest.fixture
def tmp_data():
    with tempfile.TemporaryDirectory() as d:
        yield d


@pytest.fixture
def combat_roll_state(fresh_state):
    player = Character(
        id="player_01",
        name="주인공",
        race_id="human",
        is_player=True,
        location_id="plaza_01",
        stats=Stats(STR=14, DEX=12, CON=10, INT=10, WIS=10, CHA=10),
        hp=20,
        max_hp=20,
    )
    goblin = Character(
        id="goblin_01",
        name="고블린",
        race_id="goblin",
        location_id="plaza_01",
        stats=Stats(STR=10, DEX=12, CON=10, INT=10, WIS=10, CHA=10),
        hp=8,
        max_hp=8,
    )
    fresh_state.characters["player_01"] = player
    fresh_state.characters["goblin_01"] = goblin
    fresh_state.player_id = "player_01"
    fresh_state.pending_check = PendingCheck(
        player_input="고블린을 친다",
        kind="combat_roll",
        tier="보통",
        stat="STR",
        target="goblin_01",
        targets=["goblin_01"],
        dc=12,
        mod=2,
        required_roll=10,
        reason="combat",
        created_at="2025-01-01T00:00:00Z",
    )
    return fresh_state


async def test_combat_roll_resolves_without_nameerror(combat_roll_state, tmp_data):
    """client=None skips narration; the math + outcome path must not raise."""
    events = []
    async for ev in run_roll(
        client=None,
        state=combat_roll_state,
        profile_dir="<unused>",
        saves_dir=tmp_data,
        rng=random.Random(42),
    ):
        events.append(ev)

    types = [e["type"] for e in events]
    assert "log_entry" in types  # the d20 roll was recorded
    assert combat_roll_state.pending_check is None  # combat_roll cleared after resolution
