import json

import pytest
from pydantic import ValidationError

from src.agents.dc_judge.schema import (
    CombatAction,
    PassAction,
    RollAction,
    output_adapter,
)
from src.agents.dc_judge.semantics import (
    JudgeSemanticError,
    check_semantics,
    collect_valid_ids,
)


def test_korean_tier_accepted():
    r = output_adapter.validate_json(
        json.dumps(
            {
                "action": "roll",
                "tier": "보통",
                "stat": "CHA",
                "targets": ["g"],
                "reason": "설득 시도",
            },
            ensure_ascii=False,
        )
    )
    assert isinstance(r, RollAction) and r.tier == "보통" and r.reason == "설득 시도"


def test_old_english_tier_rejected():
    with pytest.raises(ValidationError):
        output_adapter.validate_json(
            json.dumps(
                {
                    "action": "roll",
                    "tier": "normal",
                    "stat": "CHA",
                    "targets": ["g"],
                    "reason": "x",
                }
            )
        )


def test_all_seven_tiers_accepted():
    for tier in ("매우 쉬움", "쉬움", "보통", "어려움", "매우 어려움", "전설", "신화"):
        output_adapter.validate_json(
            json.dumps(
                {
                    "action": "roll",
                    "tier": tier,
                    "stat": "STR",
                    "targets": ["x"],
                    "reason": "테스트",
                },
                ensure_ascii=False,
            )
        )


def test_roll_requires_reason():
    with pytest.raises(ValidationError):
        output_adapter.validate_json(
            json.dumps(
                {"action": "roll", "tier": "보통", "stat": "CHA", "targets": ["g"]},
                ensure_ascii=False,
            )
        )


def test_roll_rejects_empty_reason():
    with pytest.raises(ValidationError):
        output_adapter.validate_json(
            json.dumps(
                {
                    "action": "roll",
                    "tier": "보통",
                    "stat": "CHA",
                    "targets": ["g"],
                    "reason": "",
                },
                ensure_ascii=False,
            )
        )


def test_combat_targets_only_no_extras():
    c = output_adapter.validate_json(json.dumps({"action": "combat", "targets": ["x"]}))
    assert isinstance(c, CombatAction)
    with pytest.raises(ValidationError):
        output_adapter.validate_json(
            json.dumps(
                {"action": "combat", "targets": ["x"], "tier": "보통"},
                ensure_ascii=False,
            )
        )


def test_pass_action_no_extras():
    p = output_adapter.validate_json(json.dumps({"action": "pass"}))
    assert isinstance(p, PassAction)
    with pytest.raises(ValidationError):
        output_adapter.validate_json(
            json.dumps({"action": "pass", "tier": "보통"}, ensure_ascii=False)
        )


def test_collect_valid_ids():
    sur = {
        "location": {"id": "tavern"},
        "entities": [{"id": "g"}, {"id": "i"}],
    }
    assert collect_valid_ids(sur) == {"tavern", "g", "i"}


def test_semantic_check_passes_when_targets_in_surroundings():
    sur = {"location": {"id": "tavern"}, "entities": [{"id": "g"}]}
    r = output_adapter.validate_json(
        json.dumps(
            {
                "action": "roll",
                "tier": "보통",
                "stat": "CHA",
                "targets": ["g"],
                "reason": "설득",
            },
            ensure_ascii=False,
        )
    )
    check_semantics(r, sur)


def test_semantic_check_rejects_hallucinated_target():
    sur = {"location": {"id": "tavern"}, "entities": [{"id": "g"}]}
    bad = output_adapter.validate_json(
        json.dumps(
            {
                "action": "roll",
                "tier": "보통",
                "stat": "CHA",
                "targets": ["ghost"],
                "reason": "설득",
            },
            ensure_ascii=False,
        )
    )
    with pytest.raises(JudgeSemanticError):
        check_semantics(bad, sur)
