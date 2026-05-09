from src.game.flow.format import format_level_up_log


def test_format_level_up_log_uses_korean_stat_labels():
    text = format_level_up_log(
        actor_name="당신",
        level=3,
        stat_up="STR",
        stat_down="CHA",
        max_hp=33,
        max_mp=14,
    )
    assert "근력" in text
    assert "매력" in text
    assert "STR" not in text
    assert "CHA" not in text
    assert "레벨 3" in text
    assert "HP 33" in text
    assert "MP 14" in text
