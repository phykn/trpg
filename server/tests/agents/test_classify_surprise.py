"""CombatAction.surprise is an optional bool defaulting to False; the judge
sets it true when build-up in history/recent_dialogue ambushes the enemy."""

import json

from src.llm_calls.classify.schema import CombatAction, output_adapter


def test_combat_action_surprise_defaults_false():
    c = CombatAction(action="combat", targets=["g"])
    assert c.surprise is False


def test_combat_action_accepts_surprise_true():
    raw = json.dumps(
        {"action": "combat", "targets": ["goblin_01"], "surprise": True},
        ensure_ascii=False,
    )
    out = output_adapter.validate_json(raw)
    assert isinstance(out, CombatAction)
    assert out.surprise is True


def test_combat_action_omitting_surprise_is_false():
    raw = json.dumps({"action": "combat", "targets": ["g"]}, ensure_ascii=False)
    out = output_adapter.validate_json(raw)
    assert isinstance(out, CombatAction)
    assert out.surprise is False


def test_combat_action_surprise_with_skill_id():
    raw = json.dumps(
        {
            "action": "combat",
            "targets": ["g"],
            "skill_id": "fireball",
            "surprise": True,
        },
        ensure_ascii=False,
    )
    out = output_adapter.validate_json(raw)
    assert isinstance(out, CombatAction)
    assert out.surprise is True
    assert out.skill_id == "fireball"
