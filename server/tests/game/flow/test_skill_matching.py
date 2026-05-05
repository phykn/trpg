"""§2.6 S2 — judge semantic-matching integration. Mocks the case where judge supplies skill_id."""

import random

from src.game.domain.entities import (
    Character,
    CombatBehavior,
    Location,
    Skill,
    Stats,
)
from src.llm.calls.classify.schema import Verb
from src.persistence.local_fs import LocalFsSaveRepo, LocalFsScenarioRepo
from src.llm.context import build_surroundings
from src.game.flow.turn import run_turn


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
    """Racial skills are auto-matched candidates alongside learned skills."""
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
    assert "bite" in by_id
    assert "fireball" in by_id


# --- skill cast in the combat branch --------------------------------------


async def test_combat_with_skill_id_runs_auto_sim_and_burns_mp(
    fresh_state, tmp_data, judge_returns, collect
):
    """Auto-mode: CombatAction with skill_id triggers start_combat + auto-sim.
    The first round casts the skill, so MP is consumed at least once."""
    state = _seed_skill_state(fresh_state)
    judge_returns(
        Verb(name="attack", target_ids=["goblin_01"], modifiers={"skill_id": "fireball"}),
    )
    events = await collect(
        run_turn(
            client=None,
            state=state,
            scenario_repo=LocalFsScenarioRepo(profile_dir="<unused>"),
            save_repo=LocalFsSaveRepo(saves_dir=str(tmp_data)),
            player_input="화염구를 던진다",
            rng=random.Random(0),
        )
    )

    types = [e["type"] for e in events]
    assert "combat_start" in types
    assert state.pending_check is None
    # Fireball cast at least once → MP dropped from 15 by a multiple of 4.
    assert state.characters["player_01"].mp <= 15 - 4


async def test_combat_without_skill_id_runs_basic_attack_loop(
    fresh_state, tmp_data, judge_returns, collect
):
    """Without skill_id, the auto-sim runs basic weapon attacks. MP is
    untouched."""
    state = _seed_skill_state(fresh_state)
    judge_returns(Verb(name="attack", target_ids=["goblin_01"]))
    events = await collect(
        run_turn(
            client=None,
            state=state,
            scenario_repo=LocalFsScenarioRepo(profile_dir="<unused>"),
            save_repo=LocalFsSaveRepo(saves_dir=str(tmp_data)),
            player_input="고블린을 친다",
            rng=random.Random(0),
        )
    )
    types = [e["type"] for e in events]
    assert "combat_start" in types
    assert state.pending_check is None
    assert state.characters["player_01"].mp == 15


async def test_combat_during_combat_with_skill_id(
    fresh_state, tmp_data, judge_returns, collect
):
    """combat_state already active and on the player's turn — skill_id matches.
    Auto-sim casts fireball at least once, MP burns by mp_cost."""
    from src.game.engines import combat as combat_engine

    state = _seed_skill_state(fresh_state)
    combat_engine.start_combat(state, ["goblin_01"], rng=random.Random(0))
    state.combat_state.turn_order = ["player_01", "goblin_01"]
    state.combat_state.current_turn = 0

    judge_returns(
        Verb(name="attack", target_ids=["goblin_01"], modifiers={"skill_id": "fireball"}),
    )
    await collect(
        run_turn(
            client=None,
            state=state,
            scenario_repo=LocalFsScenarioRepo(profile_dir="<unused>"),
            save_repo=LocalFsSaveRepo(saves_dir=str(tmp_data)),
            player_input="화염구를 던진다",
            rng=random.Random(0),
        )
    )
    p = state.characters["player_01"]
    assert p.mp <= 15 - 4
