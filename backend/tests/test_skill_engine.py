"""스킬 cast — 검증·효과 적용·grade 보정·ActiveBuff tick (§2.6 S1 핵심)."""
import pytest

from src.domain.entities import Character, Skill, Stats
from src.errors import SkillInvalid
from src.pipeline import skill as skill_eng
from src.rules import RULES


def _player(skills=None, racial=None, **kw):
    p = Character(
        id="player_01",
        name="주",
        race_id="human",
        is_player=True,
        stats=Stats(),
        level=5,
        hp=20,
        max_hp=20,
        mp=20,
        max_mp=20,
        learned_skills=skills or [],
        racial_skills=racial or [],
        location_id="plaza_01",
    )
    for k, v in kw.items():
        setattr(p, k, v)
    return p


def _enemy(eid="goblin_01", **kw):
    e = Character(
        id=eid,
        name="고블린",
        race_id="goblin",
        stats=Stats(),
        hp=20,
        max_hp=20,
        location_id="plaza_01",
    )
    for k, v in kw.items():
        setattr(e, k, v)
    return e


def _attack_skill(**kw):
    return Skill(
        id="fireball",
        name="화염구",
        type="attack",
        target="single",
        primary_stat="INT",
        power=10,
        mp_cost=5,
        range=10.0,
        level=0,
        **kw,
    )


def _heal_skill(**kw):
    return Skill(
        id="heal_01",
        name="치유",
        type="heal",
        target="single",
        primary_stat="WIS",
        power=8,
        mp_cost=4,
        level=0,
        **kw,
    )


def _buff_skill(**kw):
    return Skill(
        id="bless",
        name="축복",
        type="buff",
        target="self",
        primary_stat="WIS",
        power=0,
        mp_cost=3,
        duration=3,
        special_effect="공격 굴림에 +2",
        level=0,
        **kw,
    )


def _state(fresh_state, **chars):
    for cid, c in chars.items():
        fresh_state.characters[cid] = c
    return fresh_state


def test_cast_attack_applies_damage_and_costs_mp(fresh_state):
    p = _player(skills=[_attack_skill()])
    e = _enemy()
    state = _state(fresh_state, player_01=p, goblin_01=e)
    fresh_state.player_id = "player_01"

    result = skill_eng.cast(p, "fireball", state, ["goblin_01"])

    # power 10 + INT mod 0 = 10
    assert result["effects"][0]["damage"] == 10
    assert e.hp == 10
    assert p.mp == 15


def test_cast_attack_uses_primary_stat_modifier(fresh_state):
    p = _player(skills=[_attack_skill()], stats=Stats(INT=14))
    e = _enemy()
    state = _state(fresh_state, player_01=p, goblin_01=e)
    fresh_state.player_id = "player_01"

    result = skill_eng.cast(p, "fireball", state, ["goblin_01"])
    # INT 14 → mod +2; damage = 10 + 2 = 12
    assert result["effects"][0]["damage"] == 12


def test_cast_heal_caps_at_max_hp(fresh_state):
    p = _player(skills=[_heal_skill()])
    ally = _enemy(eid="ally_01")
    ally.hp = 18  # max 20
    state = _state(fresh_state, player_01=p, ally_01=ally)
    fresh_state.player_id = "player_01"

    result = skill_eng.cast(p, "heal_01", state, ["ally_01"])
    # power 8 — 그러나 max 20 까지만
    assert result["effects"][0]["healed"] == 2
    assert ally.hp == 20


def test_cast_buff_appends_to_active_buffs(fresh_state):
    p = _player(skills=[_buff_skill()])
    state = _state(fresh_state, player_01=p)
    fresh_state.player_id = "player_01"

    result = skill_eng.cast(p, "bless", state, [])
    assert len(p.active_buffs) == 1
    assert p.active_buffs[0].duration == 3
    assert "공격 굴림" in p.active_buffs[0].description
    assert result["effects"][0]["kind"] == "buff"


def test_cast_self_target_ignores_requested_targets(fresh_state):
    p = _player(skills=[_buff_skill()])
    state = _state(fresh_state, player_01=p)
    skill_eng.cast(p, "bless", state, ["whatever_id"])
    assert len(p.active_buffs) == 1


def test_cast_area_hits_all_other_alive_in_location(fresh_state):
    skill = Skill(
        id="firestorm",
        name="화염폭풍",
        type="attack",
        target="area",
        primary_stat="INT",
        power=5,
        mp_cost=8,
        level=0,
    )
    p = _player(skills=[skill])
    g1 = _enemy(eid="g1")
    g2 = _enemy(eid="g2")
    g_far = _enemy(eid="g_far", location_id="other_loc")
    g_dead = _enemy(eid="g_dead", hp=0, alive=False)
    state = _state(fresh_state, player_01=p, g1=g1, g2=g2, g_far=g_far, g_dead=g_dead)
    fresh_state.player_id = "player_01"

    result = skill_eng.cast(p, "firestorm", state, [])
    targets = {e["target"] for e in result["effects"]}
    assert targets == {"g1", "g2"}  # 다른 location, 죽은 적 제외


def test_cast_rejects_when_level_too_low(fresh_state):
    s = _attack_skill()
    s.level = 10
    p = _player(skills=[s], level=2)
    state = _state(fresh_state, player_01=p, goblin_01=_enemy())
    fresh_state.player_id = "player_01"
    with pytest.raises(SkillInvalid, match="level"):
        skill_eng.cast(p, "fireball", state, ["goblin_01"])


def test_cast_rejects_when_mp_insufficient(fresh_state):
    p = _player(skills=[_attack_skill()], mp=2)
    state = _state(fresh_state, player_01=p, goblin_01=_enemy())
    fresh_state.player_id = "player_01"
    with pytest.raises(SkillInvalid, match="mp"):
        skill_eng.cast(p, "fireball", state, ["goblin_01"])


def test_cast_rejects_target_in_other_location(fresh_state):
    p = _player(skills=[_attack_skill()])
    e = _enemy(location_id="other_loc")
    state = _state(fresh_state, player_01=p, goblin_01=e)
    fresh_state.player_id = "player_01"
    with pytest.raises(SkillInvalid, match="range"):
        skill_eng.cast(p, "fireball", state, ["goblin_01"])


def test_cast_rejects_unknown_skill(fresh_state):
    p = _player()
    state = _state(fresh_state, player_01=p, goblin_01=_enemy())
    fresh_state.player_id = "player_01"
    with pytest.raises(SkillInvalid, match="no such skill"):
        skill_eng.cast(p, "missing", state, ["goblin_01"])


def test_find_skill_includes_racial_and_learned(fresh_state):
    racial = Skill(
        id="bite", name="물기", type="attack", target="single",
        primary_stat="STR", level=0,
    )
    learned = _attack_skill()
    p = _player(skills=[learned], racial=[racial])
    assert skill_eng.find_skill(p, "bite").name == "물기"
    assert skill_eng.find_skill(p, "fireball").name == "화염구"


def test_grade_multiplier_applied(fresh_state):
    p = _player(skills=[_attack_skill()])
    e = _enemy()
    state = _state(fresh_state, player_01=p, goblin_01=e)

    # critical_success → 2.0 ×
    result = skill_eng.cast(
        p, "fireball", state, ["goblin_01"], grade="critical_success"
    )
    assert result["multiplier"] == 2.0
    assert result["effects"][0]["damage"] == 20  # 10 × 2


def test_grade_failure_zeros_damage(fresh_state):
    p = _player(skills=[_attack_skill()])
    e = _enemy()
    state = _state(fresh_state, player_01=p, goblin_01=e)
    result = skill_eng.cast(p, "fireball", state, ["goblin_01"], grade="failure")
    assert result["effects"][0]["damage"] == 0
    assert e.hp == 20


def test_attack_target_dies_when_hp_zeroes(fresh_state):
    skill = _attack_skill()
    skill.power = 100
    p = _player(skills=[skill])
    e = _enemy()
    state = _state(fresh_state, player_01=p, goblin_01=e)
    result = skill_eng.cast(p, "fireball", state, ["goblin_01"])
    assert e.hp == 0
    assert not e.alive
    assert result["effects"][0].get("dead") is True


def test_dirty_set_includes_actor_and_targets(fresh_state):
    p = _player(skills=[_attack_skill()])
    e = _enemy()
    state = _state(fresh_state, player_01=p, goblin_01=e)
    dirty: set[tuple[str, str]] = set()
    skill_eng.cast(p, "fireball", state, ["goblin_01"], dirty=dirty)
    assert ("characters", "player_01") in dirty
    assert ("characters", "goblin_01") in dirty


def test_tick_active_buffs_decrements_and_removes_expired(fresh_state):
    p = _player(skills=[_buff_skill()])
    state = _state(fresh_state, player_01=p)
    skill_eng.cast(p, "bless", state, [])  # duration=3
    skill_eng.cast(p, "bless", state, [])  # +1 buff stack, duration=3
    p.mp = 20  # reset mp 충분히
    assert all(b.duration == 3 for b in p.active_buffs)

    skill_eng.tick_active_buffs(p)
    assert all(b.duration == 2 for b in p.active_buffs)
    skill_eng.tick_active_buffs(p)
    skill_eng.tick_active_buffs(p)
    # 3 tick 후 duration=0, 제거됨
    assert p.active_buffs == []


def test_tick_active_buffs_returns_removed_count(fresh_state):
    p = _player(skills=[_buff_skill()])
    state = _state(fresh_state, player_01=p)
    skill_eng.cast(p, "bless", state, [])  # duration 3
    skill_eng.tick_active_buffs(p)
    skill_eng.tick_active_buffs(p)
    # 마지막 tick 에서 제거
    removed = skill_eng.tick_active_buffs(p)
    assert removed == 1


def test_tick_active_buffs_no_op_on_empty():
    p = _player()
    assert skill_eng.tick_active_buffs(p) == 0
