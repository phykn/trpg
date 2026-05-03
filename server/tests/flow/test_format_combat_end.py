from server.src.flow.format import format_combat_end_text


def test_victory_kill_all_enemies_dead():
    """All enemies dead → 처치 label."""
    result = format_combat_end_text(outcome="victory", enemies_remaining=[])
    assert "처치" in result


def test_victory_rout_some_enemies_alive():
    """At least one enemy alive (rout) → 물리쳤 label."""
    enemies = [{"id": "goblin_1", "hp": 7, "hp_max": 34}]
    result = format_combat_end_text(outcome="victory", enemies_remaining=enemies)
    assert "물리쳤" in result


def test_player_fled():
    """Player flee → 이탈 label."""
    result = format_combat_end_text(outcome="fled", enemies_remaining=[])
    assert "이탈" in result


def test_defeat():
    """Player defeat → 패배 label."""
    result = format_combat_end_text(outcome="defeat", enemies_remaining=[])
    assert "패배" in result


def test_downed():
    """Downed outcome → 의식을 되찾았습니다 label, enemies list ignored."""
    result = format_combat_end_text(outcome="downed", enemies_remaining=[{"id": "goblin_1", "hp": 10, "hp_max": 34}])
    assert "의식" in result
