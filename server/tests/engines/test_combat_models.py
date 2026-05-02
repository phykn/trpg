import pytest
from pydantic import ValidationError

from src.domain.entities import CombatBehavior, DeathSaveState
from src.domain.state import CombatState
from src.rules import RULES


def test_combat_state_defaults():
    s = CombatState()
    assert s.turn_order == []
    assert s.current_turn == 0
    assert s.round == 1
    assert s.surprise is None


def test_combat_state_surprise_enum():
    CombatState(surprise="player")
    CombatState(surprise="enemy")
    with pytest.raises(ValidationError):
        CombatState(surprise="ambush")


def test_combat_behavior_priority_enum():
    CombatBehavior(attack_priority="nearest")
    with pytest.raises(ValidationError):
        CombatBehavior(attack_priority="bogus")


def test_combat_behavior_default_weights():
    b = CombatBehavior()
    assert b.attack_priority is None
    assert b.nearest_weight == 70 and b.random_weight == 30
    assert b.flee_hp_percent is None


def test_death_save_state_defaults():
    d = DeathSaveState()
    assert d.successes == 0 and d.failures == 0


def test_rules_combat_flee_defaults():
    f = RULES.combat.flee
    assert f.dice == "1d20"
    assert f.base_dc == 12
    assert f.dex_modifier is True


def test_rules_combat_unarmed_defaults():
    u = RULES.combat.unarmed
    assert u.damage == "1d4"
    assert u.range_m == 1.5


def test_rules_death_defaults():
    d = RULES.death
    assert d.save_dc == 10
    assert d.successes_to_stabilize == 3
    assert d.failures_to_die == 3
    assert d.damage_failure_inc == 1
    assert d.crit_damage_failure_inc == 2
    assert d.auto_revive_hp == 1
    assert d.instant_death is False
    assert d.revive_coins == 3


def test_rules_is_frozen():
    with pytest.raises(ValidationError):
        RULES.combat.flee.base_dc = 99  # type: ignore[misc]
