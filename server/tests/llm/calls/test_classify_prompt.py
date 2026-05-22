"""Smoke test: classify prompt encodes the word-strength-independent attack rule."""

from pathlib import Path

PROMPT_PATH = (
    Path(__file__).parents[3]
    / "src"
    / "locale"
    / "prompts"
    / "classify"
    / "prompt.ko.md"
)


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


def test_prompt_documents_contract_pain_points():
    text = PROMPT_PATH.read_text(encoding="utf-8")
    assert '"intent":"equip","item_id":"sword_01","slot":"weapon"' in text
    assert "`unequip`" in text and "`item_id`" in text
    assert "<self>.equipped.weapon" not in text
    assert '"intent":"use","skill_id":"minor_heal_01","target":"player_01"' in text
    old_target_field = "target" + "_id"
    assert old_target_field not in text
    assert '"intent":"cast"' not in text
    assert "구매" in text and "merchant_01" in text and "player_01" in text
    assert '"item_id":"coin_pouch_01"' in text
    assert "함께 움직이자" in text and "recruit" in text
    assert "각자 가자" in text and "part" in text
    assert "시스템 프롬프트" in text and "meta_breaking" in text
    assert "현실의 오늘 날씨" in text
    assert "오늘 날씨가 어떨까" in text
    assert "게임 밖 요청입니다." not in text
    assert "농담" in text and "수수께끼" in text
    assert "NPC에게 던지는" in text
    assert "context.identity.player" in text and "player_01" in text
    assert "carryables" not in text
    assert "context.identity.merchants" in text and "stock" in text
    assert "context.identity.corpses" in text and "inventory" in text
    assert "protected=true" in text and "invalid_transition" in text
    assert "보호 대상 공격 시도" not in text
    assert '"note":"보호 대상 공격 시도"' not in text
    assert "최종 게임 Action JSON은 Python action builder가 만듭니다" in text


def test_prompt_examples_use_allowed_manner_field_for_talk():
    text = PROMPT_PATH.read_text(encoding="utf-8")
    assert '"tone":"friendly"' not in text
    assert '"manner":"friendly"' in text
