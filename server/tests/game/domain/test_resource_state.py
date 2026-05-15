from src.game.domain.resource_state import hp_state, mp_state


def test_hp_state_thresholds():
    assert hp_state(10, 10) == "healthy"
    assert hp_state(6, 10) == "hurt"
    assert hp_state(2, 10) == "critical"
    assert hp_state(0, 10) == "critical"


def test_mp_state_thresholds():
    assert mp_state(10, 10) == "ready"
    assert mp_state(5, 10) == "strained"
    assert mp_state(2, 10) == "drained"
    assert mp_state(0, 10) == "drained"
    assert mp_state(0, 0) is None
