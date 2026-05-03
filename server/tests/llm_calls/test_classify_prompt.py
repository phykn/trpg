"""Smoke test: judge prompt encodes the word-strength-independent attack rule."""

from pathlib import Path

PROMPT_PATH = Path(__file__).parents[2] / "src" / "llm_calls" / "classify" / "prompt.md"


def test_prompt_contains_attack_verb_examples():
    text = PROMPT_PATH.read_text(encoding="utf-8")
    # word-strength independence rule must be explicit
    assert "단어 강도" in text or "verb strength" in text.lower() or "강도 무관" in text
    # graphic attack verbs that previously triggered inconsistent behavior
    assert any(verb in text for verb in ("살해", "베어버린다", "죽인다"))


def test_prompt_lists_friendly_attack_combat_example():
    text = PROMPT_PATH.read_text(encoding="utf-8")
    # friendly NPC explicitly-named attack must appear as a combat example
    assert "에드릭" in text or "친화" in text or "friendly" in text.lower()
