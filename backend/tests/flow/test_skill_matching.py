"""§2.6 S2 — judge semantic-matching integration. Mocks the case where judge supplies skill_id."""
import random
import tempfile

import pytest

from src.domain.entities import (
    Character,
    CombatBehavior,
    Location,
    Skill,
    Stats,
)
from src.agents.dc_judge.schema import CombatAction
from src.flow import judge as judge_mod
from src.flow import combat_phase as combat_phase_mod
from src.flow import turn as turn_mod
from src.context import build_surroundings
from src.flow.turn import run_turn


@pytest.fixture
def tmp_data():
    with tempfile.TemporaryDirectory() as d:
        yield d


def _judge_returns(monkeypatch, action_obj):
    async def fake_judge(client, state, player_input):
        return action_obj
    monkeypatch.setattr(judge_mod, "run_judge", fake_judge)
    monkeypatch.setattr(turn_mod, "run_judge", fake_judge)
    monkeypatch.setattr(combat_phase_mod, "run_judge", fake_judge)


async def _collect(it):
    return [ev async for ev in it]


def _seed_skill_state(fresh_state):
    skill = Skill(
        id="fireball",
        name="화염구",
        description="불꽃을 한 방울로 모아 던지는 마법",
        type="attack",
        target="single",
        primary_stat="INT",
        power=12,
        mp_cost=4,
        level=1,
        special_effect="화염 폭발",
    )
    p = Character(
        id="player_01",
        name="주",
        race_id="human",
        is_player=True,
        stats=Stats(STR=12, DEX=10, INT=14),
        level=3,
        hp=20,
        max_hp=20,
        mp=15,
        max_mp=15,
        location_id="plaza_01",
        learned_skill_ids=[skill.id],
    )
    fresh_state.skills[skill.id] = skill
    g = Character(
        id="goblin_01",
        name="고블린",
        race_id="goblin",
        stats=Stats(),
        hp=15,
        max_hp=15,
        location_id="plaza_01",
        combat_behavior=CombatBehavior(attack_priority="nearest"),
    )
    fresh_state.characters["player_01"] = p
    fresh_state.characters["goblin_01"] = g
    fresh_state.locations["plaza_01"] = Location(id="plaza_01", name="광장")
    return fresh_state


# --- surroundings exposure ------------------------------------------------


def test_build_surroundings_includes_learned_skills(fresh_state):
    state = _seed_skill_state(fresh_state)
    s = build_surroundings(state, "player_01")
    assert "skills" in s
    skills = s["skills"]
    assert len(skills) == 1
    assert skills[0]["id"] == "fireball"
    assert skills[0]["name"] == "화염구"
    assert skills[0]["type"] == "attack"
    assert skills[0]["source"] == "learned"


def test_build_surroundings_filters_skills_above_level(fresh_state):
    state = _seed_skill_state(fresh_state)
    state.characters["player_01"].level = 0  # below the skill's level=1
    s = build_surroundings(state, "player_01")
    assert s["skills"] == []


def test_build_surroundings_filters_skills_when_mp_insufficient(fresh_state):
    state = _seed_skill_state(fresh_state)
    state.characters["player_01"].mp = 1  # below mp_cost=4
    s = build_surroundings(state, "player_01")
    assert s["skills"] == []


def test_build_surroundings_includes_racial_skills(fresh_state):
    """Racial skills are also auto-matched candidates — distinguished by the source field."""
    state = _seed_skill_state(fresh_state)
    racial = Skill(
        id="bite",
        name="물기",
        type="attack",
        target="single",
        primary_stat="STR",
        level=0,
    )
    state.skills[racial.id] = racial
    state.characters["player_01"].racial_skill_ids = [racial.id]
    s = build_surroundings(state, "player_01")
    by_id = {sk["id"]: sk for sk in s["skills"]}
    assert by_id["bite"]["source"] == "racial"
    assert by_id["fireball"]["source"] == "learned"


# --- skill cast in the combat branch --------------------------------------


async def test_combat_with_skill_id_triggers_cast_at_combat_start(
    fresh_state, tmp_data, monkeypatch
):
    """Out-of-combat → judge returns combat + skill_id → cast on the first turn after start_combat."""
    state = _seed_skill_state(fresh_state)
    _judge_returns(
        monkeypatch,
        CombatAction(action="combat", targets=["goblin_01"], skill_id="fireball"),
    )
    events = await _collect(
        run_turn(
            client=None,
            state=state,
            profile_dir="<unused>",
            saves_dir=tmp_data,
            player_input="화염구를 던진다",
            rng=random.Random(0),
        )
    )

    types = [e["type"] for e in events]
    assert "combat_start" in types
    skill_events = [
        e for e in events
        if e["type"] == "combat_turn" and e["data"].get("action") == "skill"
    ]
    assert len(skill_events) >= 1
    assert skill_events[0]["data"]["skill_id"] == "fireball"
    # Either damage landed (in effects) or MP was deducted
    p = state.characters["player_01"]
    assert p.mp == 15 - 4
    g = state.characters["goblin_01"]
    assert g.hp < 15


async def test_combat_without_skill_id_runs_plain_attack(
    fresh_state, tmp_data, monkeypatch
):
    """Without skill_id, fall through to the regular attack branch."""
    state = _seed_skill_state(fresh_state)
    _judge_returns(
        monkeypatch, CombatAction(action="combat", targets=["goblin_01"])
    )
    events = await _collect(
        run_turn(
            client=None,
            state=state,
            profile_dir="<unused>",
            saves_dir=tmp_data,
            player_input="고블린을 친다",
            rng=random.Random(0),
        )
    )
    types_actions = [
        e["data"].get("action") for e in events if e["type"] == "combat_turn"
    ]
    # No skill action should appear
    assert "skill" not in types_actions
    # MP unchanged
    assert state.characters["player_01"].mp == 15


async def test_combat_during_combat_with_skill_id(
    fresh_state, tmp_data, monkeypatch
):
    """combat_state already active and on the player's turn — skill_id matches."""
    from src.engines import combat as combat_engine

    state = _seed_skill_state(fresh_state)
    combat_engine.start_combat(state, ["goblin_01"], rng=random.Random(0))
    state.combat_state.turn_order = ["player_01", "goblin_01"]
    state.combat_state.current_turn = 0

    _judge_returns(
        monkeypatch,
        CombatAction(action="combat", targets=["goblin_01"], skill_id="fireball"),
    )
    await _collect(
        run_turn(
            client=None,
            state=state,
            profile_dir="<unused>",
            saves_dir=tmp_data,
            player_input="화염구를 던진다",
            rng=random.Random(0),
        )
    )
    p = state.characters["player_01"]
    assert p.mp == 15 - 4
