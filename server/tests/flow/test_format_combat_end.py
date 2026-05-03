from server.src.flow.format import format_combat_end_text


def test_victory_kill_all_enemies_dead():
    """모든 적 HP 0 → 처치"""
    result = format_combat_end_text(outcome="victory", enemies_remaining=[])
    assert "처치" in result


def test_victory_rout_some_enemies_alive():
    """적 일부 HP > 0 (도주) → 물리쳤"""
    enemies = [{"id": "goblin_1", "hp": 7, "hp_max": 34}]
    result = format_combat_end_text(outcome="victory", enemies_remaining=enemies)
    assert "물리쳤" in result


def test_player_fled():
    """주인공 도주 → 전투에서 이탈"""
    result = format_combat_end_text(outcome="fled", enemies_remaining=[])
    assert "이탈" in result


def test_defeat():
    """주인공 사망 → 패배"""
    result = format_combat_end_text(outcome="defeat", enemies_remaining=[])
    assert "패배" in result
