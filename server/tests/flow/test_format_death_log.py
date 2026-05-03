from src.flow.format import format_death_log


def test_format_death_log_basic():
    assert format_death_log("고블린") == "고블린 사망"


def test_format_death_log_player_name():
    assert format_death_log("당신") == "당신 사망"
