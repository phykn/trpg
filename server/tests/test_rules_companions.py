from src.rules import RULES


def test_companions_defaults():
    c = RULES.companions
    assert c.max_companions == 3
    assert c.recruit_base_dc == 12
    assert c.recruit_affinity_crit_success == 10
    assert c.recruit_affinity_success == 3
    assert c.recruit_affinity_crit_failure == -5
