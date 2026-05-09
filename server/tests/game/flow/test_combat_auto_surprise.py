"""Surprise round-1 enemy skip — when combat opens with a player ambush
(distraction, sleeping enemy, dark approach), the enemy doesn't act in
round 1. After round 1, combat proceeds normally."""

import random

import pytest

from src.game.domain.entities import Character, CombatBehavior, Stats
from src.game.flow.combat_auto import PlayerAction, run_auto_combat
from src.game.flow.dirty import Dirty
from src.game.engines import combat as combat_engine
from src.llm.calls.classify.schema import Verb
from src.game.flow.turn import run_turn
from src.db.local_fs import LocalFsSaveRepo, LocalFsScenarioRepo


@pytest.fixture
def two_party_state(fresh_state):
    fresh_state.characters["player_01"] = Character(
        id="player_01",
        name="주인공",
        race_id="human",
        is_player=True,
        location_id="plaza_01",
        stats=Stats(STR=14, DEX=12, CON=10, INT=10, WIS=10, CHA=10),
        hp=20,
        max_hp=20,
    )
    fresh_state.characters["goblin_01"] = Character(
        id="goblin_01",
        name="고블린",
        race_id="goblin",
        location_id="plaza_01",
        stats=Stats(STR=10, DEX=12, CON=10, INT=10, WIS=10, CHA=10),
        hp=80,
        max_hp=80,
        combat_behavior=CombatBehavior(attack_priority="nearest"),
    )
    return fresh_state


def test_player_surprise_skips_enemy_round_one(two_party_state):
    """surprise='player' → enemy emits a single 'pass' event in round 1, no attack."""
    state = two_party_state
    combat_engine.start_combat(
        state,
        ["goblin_01"],
        rng=random.Random(0),
        surprise="player",
    )
    # Force order so we can predict which actor emits round-1 pass.
    state.combat_state.turn_order = ["player_01", "goblin_01"]
    state.combat_state.current_turn = 0

    dirty = Dirty()
    result = run_auto_combat(
        state,
        dirty,
        player_action=PlayerAction(kind="attack", targets=["goblin_01"]),
        rng=random.Random(1),
        cap=1,  # one round only — verifies surprise applies on round 1
    )

    # AutoCombatResult should record the surprise so narrate can reflect it
    assert result.player_surprise is True

    round_one_events = [e for e in result.events if e.round_no == 1]
    goblin_round_one = [e for e in round_one_events if e.actor == "고블린"]
    # Goblin's round 1 event must be a pass (skipped by surprise) — never attack/skill/miss.
    assert all(e.action == "pass" for e in goblin_round_one)
    # And there must be at least one pass event for the goblin (the skip itself).
    assert any(e.action == "pass" for e in goblin_round_one)

    # turn_events parallel: same actor/round → action='pass'.
    goblin_turn_events = [
        t for t in result.turn_events if t["actor"] == "goblin_01" and t["round"] == 1
    ]
    assert all(t["action"] == "pass" for t in goblin_turn_events)


def test_no_surprise_enemy_acts_round_one(two_party_state):
    """surprise=None → enemy's round-1 turn is normal (attack/miss, not pass)."""
    state = two_party_state
    combat_engine.start_combat(
        state,
        ["goblin_01"],
        rng=random.Random(0),
        surprise=None,
    )
    state.combat_state.turn_order = ["player_01", "goblin_01"]
    state.combat_state.current_turn = 0

    dirty = Dirty()
    result = run_auto_combat(
        state,
        dirty,
        player_action=PlayerAction(kind="attack", targets=["goblin_01"]),
        rng=random.Random(1),
        cap=1,
    )

    assert result.player_surprise is False
    goblin_round_one = [
        e for e in result.events if e.round_no == 1 and e.actor == "고블린"
    ]
    # Without surprise, goblin actually acts — the action is not 'pass'
    # (could be attack/miss; both are fine, the point is it's not the surprise skip).
    assert any(e.action != "pass" for e in goblin_round_one)


async def test_combat_action_surprise_routes_through_to_combat_state(
    two_party_state, tmp_data, judge_returns, collect
):
    """End-to-end: judge returns CombatAction(surprise=True) → combat_state is
    booted with surprise='player' and the auto-sim records player_surprise."""
    judge_returns(
        Verb(name="attack", target_ids=["goblin_01"], modifiers={"surprise": True})
    )
    events = await collect(
        run_turn(
            client=None,
            state=two_party_state,
            scenario_repo=LocalFsScenarioRepo(profile_dir="<unused>"),
            save_repo=LocalFsSaveRepo(saves_dir=str(tmp_data)),
            player_input="잠든 고블린을 친다",
            rng=random.Random(5),
        )
    )

    combat_start = [e for e in events if e["type"] == "combat_start"]
    assert combat_start
    assert combat_start[0]["data"]["surprise"] == "player"
