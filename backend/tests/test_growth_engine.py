"""성장 엔진 — xp 곡선, level_up 페어 트레이드, HP/MP 재계산, 불변식 검증."""
import pytest

from src.domain.entities import Character, Stats
from src.errors import LevelUpInvalid
from src.pipeline.growth import (
    PAIR_TRADE,
    assert_pair_trade_invariant,
    calc_max_hp,
    calc_max_mp,
    can_afford_level_up,
    grant_xp,
    level_up,
    recalc_max_hp_mp,
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
    assert xp_for_next_level(RULES.growth.max_level) == 0  # 만렙은 0


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
    # 페어 합 유지
    assert p.stats.STR + p.stats.CHA == 20
    assert p.xp_pool == 1000 - RULES.growth.base_xp


def test_level_up_recalculates_max_hp_when_con_changes():
    p = _player(level=0)
    p.xp_pool = 1000
    # CON 을 깎으면 max_hp 즉시 줄어든다.
    level_up(p, "INT", "CON")
    expected = calc_max_hp(p.level, p.stats.CON)
    assert p.max_hp == expected
    # hp 가 새 max 보다 크면 clamp
    assert p.hp <= p.max_hp


def test_recalc_clamps_current_hp_mp_when_max_drops():
    """현재 hp/mp 가 새 max 보다 크면 max 로 clamp."""
    p = _player(level=5, stats=Stats(CON=14, INT=14))  # max_hp ~ 60
    p.hp = p.max_hp
    p.mp = p.max_mp
    # 페어 트레이드 적용 후처럼 stat 강제 변경
    p.stats.CON = 4
    p.stats.INT = 4
    recalc_max_hp_mp(p)
    assert p.hp == p.max_hp  # 새 max 로 clamp
    assert p.mp == p.max_mp


def test_level_up_rejects_wrong_pair():
    p = _player(level=0)
    p.xp_pool = 1000
    with pytest.raises(LevelUpInvalid):
        level_up(p, "STR", "DEX")  # STR 의 페어는 CHA


def test_level_up_rejects_when_stat_at_cap():
    p = _player(level=0, stats=Stats(STR=20, CHA=0))
    p.xp_pool = 1000
    with pytest.raises(LevelUpInvalid):
        level_up(p, "STR", "CHA")  # STR 이미 20


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


def test_pair_trade_invariant_holds_for_default_stats():
    p = _player(level=0, stats=Stats())
    assert_pair_trade_invariant(p)  # 기본값은 모두 10 → 합 20


def test_pair_trade_invariant_holds_after_level_up():
    p = _player(level=0)
    p.xp_pool = 1000
    level_up(p, "DEX", "WIS")
    assert_pair_trade_invariant(p)


def test_pair_trade_invariant_violated_for_random_stats():
    p = _player(stats=Stats(STR=14, CHA=14))  # 합 28
    with pytest.raises(ValueError, match="STR.*CHA"):
        assert_pair_trade_invariant(p)


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
    """STR↔CHA, DEX↔WIS, CON↔INT — 양방향."""
    for a, b in PAIR_TRADE.items():
        assert PAIR_TRADE[b] == a


def test_recalc_max_hp_mp_uses_current_level_and_stats():
    p = _player(level=3, stats=Stats(CON=12, INT=8))
    p.max_hp = 0  # 거짓 초기값
    p.max_mp = 0
    recalc_max_hp_mp(p)
    assert p.max_hp == calc_max_hp(3, 12)
    assert p.max_mp == calc_max_mp(3, 8)
