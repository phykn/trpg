"""emit_cast — out-of-combat heal/buff cast wrapper around apply_skill_action.

Covers the success path (act log + entity dirty + turn_log placement),
SkillInvalid fail path (_engine_fail yield), and ally vs self turn_log
de-duplication (apply_skill_action already pushes for cross-target casts)."""

import random

from src.game.domain.entities import Character, Location, Skill, Stats
from src.game.flow.actions import emit_cast
from src.game.flow.dirty import Dirty


def _seed(fresh_state, *, skill_type: str, target: str = "self", mp: int = 10):
    heal_skill = Skill(
        id="minor_heal",
        name="치유",
        description="가벼운 상처를 회복",
        type=skill_type,
        target=target,
        primary_stat="WIS",
        power=8,
        mp_cost=4,
        level=1,
        duration=3 if skill_type == "buff" else 0,
        special_effect="회복" if skill_type == "heal" else "방어 강화",
    )
    fresh_state.skills[heal_skill.id] = heal_skill
    p = Character(
        id="player_01",
        name="주",
        race_id="human",
        is_player=True,
        stats=Stats(STR=10, DEX=10, INT=10, WIS=14, CON=10, CHA=10),
        level=3,
        hp=10,
        max_hp=20,
        mp=mp,
        max_mp=20,
        location_id="plaza_01",
        learned_skill_ids=[heal_skill.id],
    )
    ally = Character(
        id="ally_01",
        name="동료",
        race_id="human",
        stats=Stats(),
        hp=5,
        max_hp=20,
        location_id="plaza_01",
    )
    fresh_state.characters["player_01"] = p
    fresh_state.characters["ally_01"] = ally
    fresh_state.locations["plaza_01"] = Location(id="plaza_01", name="광장")
    fresh_state.player_id = "player_01"
    return fresh_state


async def _drain(gen):
    out = []
    async for ev in gen:
        out.append(ev)
    return out


async def test_emit_cast_self_heal_happy(fresh_state):
    state = _seed(fresh_state, skill_type="heal", target="self")
    dirty = Dirty()
    rng = random.Random(0)

    events = await _drain(
        emit_cast(state, "player_01", "minor_heal", ["player_01"], dirty, rng=rng)
    )

    # Engine: HP healed, MP spent, both player and self target dirtied.
    assert state.characters["player_01"].hp > 10
    assert state.characters["player_01"].mp == 6  # 10 - 4
    assert ("characters", "player_01") in dirty.entities

    # SSE: exactly one act log_entry, no _engine_fail.
    act_events = [e for e in events if e.get("type") == "log_entry"]
    fail_events = [e for e in events if e.get("type") == "_engine_fail"]
    assert len(act_events) == 1
    assert fail_events == []
    assert "치유" in act_events[0]["data"]["text"]
    # Self-cast emits a turn_log line via push_act's turn_summary.
    self_turn_logs = [t for t in state.turn_log if "자가 시전" in t.summary]
    assert len(self_turn_logs) == 1


async def test_emit_cast_self_buff_happy(fresh_state):
    state = _seed(fresh_state, skill_type="buff", target="self")
    dirty = Dirty()
    events = await _drain(
        emit_cast(state, "player_01", "minor_heal", ["player_01"], dirty)
    )
    assert len(state.characters["player_01"].active_buffs) == 1
    assert any(e.get("type") == "log_entry" for e in events)
    assert not any(e.get("type") == "_engine_fail" for e in events)


async def test_emit_cast_ally_heal_no_duplicate_turn_log(fresh_state):
    """apply_skill_action already pushes turn_log for cross-target. emit_cast
    must not add another entry, otherwise cross-target ally heal logs twice."""
    state = _seed(fresh_state, skill_type="heal", target="single")
    dirty = Dirty()

    await _drain(emit_cast(state, "player_01", "minor_heal", ["ally_01"], dirty))

    assert state.characters["ally_01"].hp > 5
    cast_logs = [t for t in state.turn_log if "치유" in t.summary]
    assert len(cast_logs) == 1


async def test_emit_cast_skill_invalid_emits_engine_fail(fresh_state):
    """MP shortage → SkillInvalid → fail line + _engine_fail yield."""
    state = _seed(fresh_state, skill_type="heal", target="self", mp=1)
    dirty = Dirty()

    events = await _drain(
        emit_cast(state, "player_01", "minor_heal", ["player_01"], dirty)
    )

    fail_events = [e for e in events if e.get("type") == "_engine_fail"]
    act_events = [e for e in events if e.get("type") == "log_entry"]
    assert len(fail_events) == 1
    assert len(act_events) == 1  # the fail line
    # MP unchanged (engine refused before deduction).
    assert state.characters["player_01"].mp == 1
    # HP unchanged.
    assert state.characters["player_01"].hp == 10
