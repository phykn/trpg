from src.game.flow.combat_auto import (
    AutoCombatResult,
    EnemyHit,
)
from src.llm.calls.combat_narrate.schema import PlayerNarrateSnapshot
from src.game.flow.format import format_combat_outcome_summary


def _result(**kwargs) -> AutoCombatResult:
    defaults = dict(
        events=[],
        turn_events=[],
        rounds_run=1,
        outcome="victory",
        enemy_hits=[],
        player_damage_total=0,
        player_revived=False,
        player_revive_coins_after=3,
        player_revive_coins_max=3,
        player_hp_before=20,
        player_hp_after=20,
        player_max_hp=20,
        enemy_starts=[],
        player_start=PlayerNarrateSnapshot(alive=True),
        player_name="주인공",
    )
    defaults.update(kwargs)
    return AutoCombatResult(**defaults)


def test_normal_hit_single_line():
    """Plain hit (no revival) -> single line."""
    result = _result(
        player_damage_total=5,
        player_hp_before=20,
        player_hp_after=15,
    )
    text = format_combat_outcome_summary(result)
    assert text is not None
    lines = [ln for ln in text.strip().split("\n") if ln.strip() and ln != "전투 결과"]
    assert len(lines) == 1
    assert "5 피해" in lines[0]
    assert "20" in lines[0] and "15" in lines[0]


def test_revival_two_lines():
    """HP 0 + revival -> two lines, intermediate HP 0 surfaced."""
    result = _result(
        player_damage_total=1,
        player_revived=True,
        player_hp_before=1,
        player_hp_after=1,
        player_max_hp=20,
        player_revive_coins_after=2,
        player_revive_coins_max=3,
    )
    text = format_combat_outcome_summary(result)
    assert text is not None
    lines = [ln for ln in text.strip().split("\n") if ln.strip() and ln != "전투 결과"]
    assert len(lines) == 2
    assert "0" in lines[0] and "사망 직전" in lines[0]
    assert "소생 2" in lines[1] and "1" in lines[1]


def test_kill_event():
    """Enemy HP 0 -> 쓰러짐 marker."""
    result = _result(
        enemy_hits=[
            EnemyHit(
                id="goblin",
                name="고블린",
                damage_total=8,
                hp_after=0,
                max_hp=10,
                killed=True,
            ),
            EnemyHit(
                id="troll",
                name="에드릭",
                damage_total=46,
                hp_after=0,
                max_hp=46,
                killed=True,
            ),
        ],
    )
    text = format_combat_outcome_summary(result)
    assert text is not None
    assert "쓰러짐" in text or "처치" in text
