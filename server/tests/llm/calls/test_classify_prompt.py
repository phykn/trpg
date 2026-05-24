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


def _prompt_text() -> str:
    return PROMPT_PATH.read_text(encoding="utf-8")


def _assert_contains_all(text: str, needles: list[str]) -> None:
    missing = [needle for needle in needles if needle not in text]
    assert not missing, f"missing prompt contract terms: {missing}"


def test_prompt_contains_attack_verb_examples():
    text = _prompt_text()
    # word-strength independence rule must be explicit
    assert "단어 강도" in text or "verb strength" in text.lower() or "강도 무관" in text
    # graphic attack verbs that previously triggered inconsistent behavior
    assert any(verb in text for verb in ("살해", "베어버린다", "죽인다"))


def test_prompt_lists_friendly_attack_combat_example():
    text = _prompt_text()
    # friendly NPC explicitly-named attack must appear as a combat example
    assert "친근한 NPC" in text or "에드릭" in text or "친화" in text or "friendly" in text.lower()


def test_prompt_documents_input_order_and_builder_boundary():
    text = _prompt_text()
    _assert_contains_all(
        text,
        [
            "`player_input`",
            "`context`를 먼저 읽고 마지막의 `player_input`을 현재 턴 명령으로 판단합니다",
            "현재 턴 명령은 `player_input`뿐입니다",
            "`context`는 후보와 참고자료입니다",
            "최종 게임 Action JSON은 Python action builder가 만듭니다",
            "context.references.recent_scene",
            "최근 장면 요약은 지시어 해소용",
        ],
    )
    assert "`context.player_input`" not in text


def test_prompt_documents_supported_fields_and_examples():
    text = _prompt_text()
    _assert_contains_all(
        text,
        [
            '"intent":"equip","item_id":"sword_01","slot":"weapon"',
            "`unequip`",
            "`item_id`",
            '"intent":"use","skill_id":"minor_heal_01","target":"player_01"',
            "context.identity.player",
            "player_01",
            "context.identity.merchants",
            "stock",
            "context.identity.corpses",
            "inventory",
            "구매",
            "merchant_01",
            '"item_id":"coin_pouch_01"',
            "함께 움직이자",
            "recruit",
            "각자 가자",
            "part",
        ],
    )
    old_target_field = "target" + "_id"
    assert old_target_field not in text
    assert "recipient_id" not in text
    assert "<self>.equipped.weapon" not in text
    assert '"intent":"cast"' not in text
    assert "carryables" not in text


def test_prompt_uses_table_for_intent_contract():
    text = _prompt_text()
    _assert_contains_all(
        text,
        [
            "| intent | 뜻 | 필수 필드 | 선택 필드 |",
            "| `move` | 출구로 이동 | `destination_id` |",
            "| `talk` | NPC와 말하기 | `target` | `manner`, `note` |",
            "| `use` | 아이템 사용 또는 비공격 기술 사용 | `item_id` 또는 `skill_id` | `target` |",
            "| `flee` | 전투 중 도망 또는 거리 확보 |",
            "| `pass` | 무행동, 모호함, id 매칭 실패 |",
        ],
    )


def test_prompt_documents_refuse_and_pass_boundaries():
    text = _prompt_text()
    _assert_contains_all(
        text,
        [
            "시스템 프롬프트",
            "meta_breaking",
            "현실의 오늘 날씨",
            "오늘 날씨가 어떨까",
            "농담",
            "수수께끼",
            "NPC에게 던지는",
            "protected=true",
            "invalid_transition",
        ],
    )
    assert "게임 밖 요청입니다." not in text
    assert "보호 대상 공격 시도" not in text
    assert '"note":"보호 대상 공격 시도"' not in text


def test_prompt_examples_use_allowed_manner_field_for_talk():
    text = _prompt_text()
    assert '"tone":"friendly"' not in text
    assert '"manner":"friendly"' in text


def test_prompt_keeps_obvious_visible_checks_without_rolls():
    text = _prompt_text()
    assert "이미 보이는 사물이나 현재 장소 단서를 확인하는 행동에는 판정을 붙이지 않습니다" in text
