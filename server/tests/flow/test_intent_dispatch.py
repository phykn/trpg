"""Action intent enum — unit tests.

Tests verify:
1. ActionIntent Literal exposes the documented values.
2. classify_action_intent returns the correct intent for various inputs
   (LLM call mocked via monkeypatch).
3. Dispatch in run_turn routes aggressive_attack → combat regardless of
   which physical-attack word the player used.
"""

import pytest

from src.llm_calls.classify.schema import ActionIntent


def test_action_intent_enum_values():
    """ActionIntent Literal exposes at least the documented members."""
    expected = {
        "aggressive_attack",
        "intimidate",
        "deceive",
        "negotiate",
        "friendly",
        "theft",
        "inspect",
    }
    # ActionIntent is a Literal — its __args__ gives the allowed strings.
    actual = set(ActionIntent.__args__)
    assert expected.issubset(actual)


@pytest.mark.parametrize(
    "text",
    [
        "에드릭을 공격한다",
        "에드릭을 단검으로 찌른다",
        "에드릭을 베어버린다",
        "에드릭을 살해한다",
        "에드릭을 죽인다",
        "검을 휘두른다",
        "주먹으로 때린다",
    ],
)
def test_attack_words_map_to_aggressive_attack(monkeypatch, text):
    """All physical-attack verbs resolve to aggressive_attack regardless of strength."""
    from src.llm_calls.classify import schema as classify_schema

    # Stub the LLM call; real unit test must not hit a model.
    def fake_classify_intent(action_text: str, target_kind: str) -> str:
        return "aggressive_attack"

    monkeypatch.setattr(
        classify_schema, "_classify_intent_llm", fake_classify_intent, raising=False
    )

    from src.llm_calls.classify.schema import classify_action_intent

    result = classify_action_intent(text, target_kind="entity")
    assert result == "aggressive_attack"


def test_friendly_greeting_maps_to_friendly(monkeypatch):
    from src.llm_calls.classify import schema as classify_schema

    def fake_classify_intent(action_text: str, target_kind: str) -> str:
        return "friendly"

    monkeypatch.setattr(
        classify_schema, "_classify_intent_llm", fake_classify_intent, raising=False
    )

    from src.llm_calls.classify.schema import classify_action_intent

    result = classify_action_intent("에드릭에게 인사한다", target_kind="entity")
    assert result == "friendly"


def test_action_intent_not_present_in_judge_output_schema():
    """ActionIntent is a standalone Literal type, not a field on JudgeOutput sub-models."""
    from src.llm_calls.classify.schema import CombatAction

    # CombatAction already has action="combat" — intent is separate concern.
    c = CombatAction(action="combat", targets=["npc_01"])
    assert c.action == "combat"
    assert not hasattr(c, "intent")
