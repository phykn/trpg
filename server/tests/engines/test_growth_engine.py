"""Growth engine — xp curve, level_up pair-trade, HP/MP recompute, invariant checks."""

import pytest

from src.domain.entities import Character, Stats
from src.domain.errors import LevelUpInvalid
from src.domain.types import STAT_PAIRS
from src.domain.state import GameState
from src.engines.growth import (
    award_kill_xp,
    calc_max_hp,
    calc_max_mp,
    can_afford_level_up,
    grant_roll_xp,
    grant_xp,
    level_up,
    recalc_max_hp_mp,
    xp_for_grade,
    xp_for_next_level,
)
from src.rules import RULES


def _player(level=0, stats=None, **kw):
    p = Character(
        id="player_01",
        name="주",
        race_id="human",
        is_player=True,
        stats=stats or Stats(),
        level=level,
    )
    p.max_hp = calc_max_hp(level, p.stats.CON)
    p.max_mp = calc_max_mp(level, p.stats.INT)
    p.hp = p.max_hp
    p.mp = p.max_mp
    for k, v in kw.items():
        setattr(p, k, v)
    return p


def test_starting_max_hp_mp_at_level_zero_with_default_stats():
    p = _player(level=0, stats=Stats())
    assert p.max_hp == 20  # (10+10) + 0*(5+10//4)
    assert p.max_mp == 15  # (5+10) + 0*(3+10//4)


def test_xp_curve_linear():
    base = RULES.growth.base_xp
    assert xp_for_next_level(0) == base
    assert xp_for_next_level(1) == base
    assert xp_for_next_level(2) == base * 2
    assert xp_for_next_level(5) == base * 5
    assert xp_for_next_level(RULES.growth.max_level) == 0  # max level → 0


def test_can_afford_level_up_threshold():
    p = _player(level=0)
    p.xp_pool = RULES.growth.base_xp - 1
    assert not can_afford_level_up(p)
    p.xp_pool = RULES.growth.base_xp
    assert can_afford_level_up(p)


def test_level_up_pair_trade_str_cha():
    p = _player(level=0)
    p.xp_pool = 1000
    level_up(p, "STR", "CHA")
    assert p.level == 1
    assert p.stats.STR == 11
    assert p.stats.CHA == 9
    # pair sum preserved
    assert p.stats.STR + p.stats.CHA == 20
    assert p.xp_pool == 1000 - RULES.growth.base_xp


def test_level_up_recalculates_max_hp_when_con_changes():
    p = _player(level=0)
    p.xp_pool = 1000
    # Reducing CON shrinks max_hp immediately.
    level_up(p, "INT", "CON")
    expected = calc_max_hp(p.level, p.stats.CON)
    assert p.max_hp == expected
    # hp is clamped if it exceeds the new max
    assert p.hp <= p.max_hp


def test_recalc_clamps_current_hp_mp_when_max_drops():
    """If current hp/mp exceed the new max, they clamp down."""
    p = _player(level=5, stats=Stats(CON=14, INT=14))  # max_hp ~ 60
    p.hp = p.max_hp
    p.mp = p.max_mp
    # Force-mutate stats as if pair-trade was applied.
    p.stats.CON = 4
    p.stats.INT = 4
    recalc_max_hp_mp(p)
    assert p.hp == p.max_hp  # clamped to new max
    assert p.mp == p.max_mp


def test_level_up_rejects_wrong_pair():
    p = _player(level=0)
    p.xp_pool = 1000
    with pytest.raises(LevelUpInvalid):
        level_up(p, "STR", "DEX")  # STR's pair is CHA


def test_level_up_rejects_when_stat_at_cap():
    p = _player(level=0, stats=Stats(STR=20, CHA=0))
    p.xp_pool = 1000
    with pytest.raises(LevelUpInvalid):
        level_up(p, "STR", "CHA")  # STR already at 20


def test_level_up_rejects_when_pair_at_zero():
    p = _player(level=0, stats=Stats(STR=20, CHA=0))
    p.xp_pool = 1000
    with pytest.raises(LevelUpInvalid):
        level_up(p, "STR", "CHA")


def test_level_up_rejects_at_max_level():
    p = _player(level=RULES.growth.max_level)
    p.xp_pool = 999_999
    with pytest.raises(LevelUpInvalid):
        level_up(p, "STR", "CHA")


def test_level_up_rejects_when_xp_insufficient():
    p = _player(level=0)
    p.xp_pool = 1
    with pytest.raises(LevelUpInvalid):
        level_up(p, "STR", "CHA")


def test_level_up_does_not_modify_state_on_failure():
    p = _player(level=0, stats=Stats(STR=20, CHA=0))
    p.xp_pool = 9999
    snapshot = p.model_dump_json()
    with pytest.raises(LevelUpInvalid):
        level_up(p, "STR", "CHA")
    assert p.model_dump_json() == snapshot


def test_grant_xp_appends_to_pool_and_dirty():
    p = _player()
    dirty: set[tuple[str, str]] = set()
    grant_xp(p, 50, dirty=dirty)
    assert p.xp_pool == 50
    assert ("characters", "player_01") in dirty


def test_grant_xp_rejects_negative():
    p = _player()
    with pytest.raises(ValueError):
        grant_xp(p, -10)


def test_pair_trade_table_is_symmetric():
    """STR↔CHA, DEX↔WIS, CON↔INT — bidirectional."""
    for a, b in STAT_PAIRS.items():
        assert STAT_PAIRS[b] == a


def test_recalc_max_hp_mp_uses_current_level_and_stats():
    p = _player(level=3, stats=Stats(CON=12, INT=8))
    p.max_hp = 0  # bogus seed value
    p.max_mp = 0
    recalc_max_hp_mp(p)
    assert p.max_hp == calc_max_hp(3, 12)
    assert p.max_mp == calc_max_mp(3, 8)


def test_xp_for_grade_lookup():
    assert xp_for_grade("critical_success") == RULES.growth.roll_xp["critical_success"]
    assert xp_for_grade("success") == RULES.growth.roll_xp["success"]
    assert xp_for_grade("failure") == 0
    assert xp_for_grade("nonsense") == 0


def test_grant_roll_xp_awards_to_player():
    p = _player()
    state = GameState(game_id="t", profile="t", player_id="player_01")
    state.characters["player_01"] = p
    dirty: set[tuple[str, str]] = set()
    amount = grant_roll_xp(state, "success", dirty=dirty)
    assert amount == RULES.growth.roll_xp["success"]
    assert p.xp_pool == amount
    assert ("characters", "player_01") in dirty


def test_grant_roll_xp_zero_for_failure():
    p = _player()
    state = GameState(game_id="t", profile="t", player_id="player_01")
    state.characters["player_01"] = p
    amount = grant_roll_xp(state, "failure")
    assert amount == 0
    assert p.xp_pool == 0


def test_award_kill_xp_player_killer():
    p = _player()
    enemy = _player(level=0)
    enemy.id = "rat_01"
    enemy.is_player = False
    enemy.xp_reward = 30
    state = GameState(game_id="t", profile="t", player_id="player_01")
    state.characters["player_01"] = p
    state.characters["rat_01"] = enemy
    dirty: set[tuple[str, str]] = set()
    amount = award_kill_xp(state, "player_01", "rat_01", dirty=dirty)
    assert amount == 30
    assert p.xp_pool == 30
    assert ("characters", "player_01") in dirty


def test_award_kill_xp_no_op_for_npc_killer():
    """NPC-on-NPC kills don't create xp out of thin air."""
    enemy = _player()
    enemy.id = "rat_01"
    enemy.is_player = False
    enemy.xp_reward = 30
    npc = _player()
    npc.id = "ma_zhong"
    npc.is_player = False
    state = GameState(game_id="t", profile="t", player_id="player_01")
    state.characters["rat_01"] = enemy
    state.characters["ma_zhong"] = npc
    state.characters["player_01"] = _player()
    amount = award_kill_xp(state, "ma_zhong", "rat_01")
    assert amount == 0
    assert npc.xp_pool == 0


def test_award_kill_xp_zero_reward_skipped():
    p = _player()
    npc = _player()
    npc.id = "old_owner"
    npc.is_player = False
    npc.xp_reward = 0
    state = GameState(game_id="t", profile="t", player_id="player_01")
    state.characters["player_01"] = p
    state.characters["old_owner"] = npc
    amount = award_kill_xp(state, "player_01", "old_owner")
    assert amount == 0
    assert p.xp_pool == 0
