from src.flow.combat_auto import (
    AutoCombatResult,
    EnemyHit,
    PlayerNarrateSnapshot,
)
from src.flow.format import (
    format_combat_enemy_hit,
    format_combat_enemy_killed,
    format_combat_outcome_summary,
    format_combat_player_hit,
    format_combat_revived,
)


def test_format_combat_enemy_killed():
    assert format_combat_enemy_killed("고블린", 8) == "고블린 8 피해 — 쓰러짐"


def test_format_combat_enemy_hit():
    assert format_combat_enemy_hit("고블린", 5, 3, 10) == "고블린 5 피해 (HP 3/10)"


def test_format_combat_player_hit():
    assert format_combat_player_hit("당신", 4, 16, 20) == "당신 4 피해 (HP 16/20)"


def test_format_combat_revived():
    assert format_combat_revived(2, 3) == "가까스로 일어남 (Revival 2/3)"


def _result(
    *,
    enemy_hits: list[EnemyHit] | None = None,
    player_damage_total: int = 0,
    player_revived: bool = False,
    player_start_name: str = "당신",
    player_hp_after: int = 20,
    player_max_hp: int = 20,
    player_revive_coins_after: int = 3,
    player_revive_coins_max: int = 3,
) -> AutoCombatResult:
    return AutoCombatResult(
        events=[],
        turn_events=[],
        rounds_run=1,
        outcome="victory",
        enemy_hits=enemy_hits or [],
        player_damage_total=player_damage_total,
        player_revived=player_revived,
        player_revive_coins_after=player_revive_coins_after,
        player_revive_coins_max=player_revive_coins_max,
        player_hp_after=player_hp_after,
        player_max_hp=player_max_hp,
        enemy_starts=[],
        player_start=PlayerNarrateSnapshot(name=player_start_name, alive=True),
    )


def test_format_combat_outcome_summary_empty_returns_none():
    assert format_combat_outcome_summary(_result()) is None


def test_format_combat_outcome_summary_single_kill():
    result = _result(
        enemy_hits=[
            EnemyHit(id="goblin", name="고블린", damage_total=8, hp_after=0, max_hp=10, killed=True),
        ],
    )
    text = format_combat_outcome_summary(result)
    assert text is not None
    assert text.startswith("전투 결과\n")
    assert "고블린 8 피해 — 쓰러짐" in text


def test_format_combat_outcome_summary_with_player_damage():
    result = _result(
        enemy_hits=[
            EnemyHit(id="goblin", name="고블린", damage_total=3, hp_after=7, max_hp=10, killed=False),
        ],
        player_damage_total=4,
        player_hp_after=16,
        player_max_hp=20,
    )
    text = format_combat_outcome_summary(result)
    assert text is not None
    assert "고블린 3 피해 (HP 7/10)" in text
    assert "당신 4 피해 (HP 16/20)" in text


def test_format_combat_outcome_summary_revived():
    result = _result(
        enemy_hits=[],
        player_damage_total=12,
        player_revived=True,
        player_hp_after=1,
        player_max_hp=20,
        player_revive_coins_after=2,
        player_revive_coins_max=3,
    )
    text = format_combat_outcome_summary(result)
    assert text is not None
    assert "당신 12 피해 (HP 1/20)" in text
    assert "가까스로 일어남 (Revival 2/3)" in text


def test_format_combat_outcome_summary_player_start_none_uses_fallback():
    result = _result(
        player_damage_total=4,
        player_hp_after=16,
        player_max_hp=20,
    )
    result.player_start = None  # type: ignore[assignment]
    text = format_combat_outcome_summary(result)
    assert text is not None
    assert "주인공 4 피해" in text
