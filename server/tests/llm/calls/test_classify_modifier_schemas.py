"""Modifier-rule regression tests: required keys, enum values, target_ids
cardinality. The rules live in `Verb._check_modifiers` (game/domain/verb.py)
and fire on `Verb.model_validate(data, context={"in_combat": ...})` — a missing
context skips the check, matching the save/load round-trip path."""

import pytest
from pydantic import ValidationError

from src.game.domain.verb import _MODIFIER_SCHEMAS, Verb


def _validate(name: str, *, in_combat: bool = False, **kwargs) -> Verb:
    data = {"name": name, **kwargs}
    return Verb.model_validate(data, context={"in_combat": in_combat})


def test_all_nine_verbs_have_schemas():
    expected = {
        "move",
        "transfer",
        "use",
        "attack",
        "cast",
        "speak",
        "perceive",
        "rest",
        "wait",
    }
    assert set(_MODIFIER_SCHEMAS.keys()) == expected


def test_move_required_destination_outside_combat():
    with pytest.raises(ValidationError, match="destination"):
        _validate("move", modifiers={})


def test_move_destination_passes():
    _validate("move", modifiers={"destination": "loc_01"})


def test_move_in_combat_destination_optional():
    _validate("move", in_combat=True, modifiers={"manner": "hasty"})


def test_transfer_required_keys():
    with pytest.raises(ValidationError):
        _validate("transfer", modifiers={"from_id": "a", "to_id": "b"})


def test_transfer_complete():
    _validate(
        "transfer",
        modifiers={
            "from_id": "merchant_01",
            "to_id": "player_01",
            "mode": "trade",
            "item_id": "potion_01",
            "price": 5,
        },
    )


def test_transfer_unknown_mode_rejected():
    with pytest.raises(ValidationError, match="mode"):
        _validate(
            "transfer",
            modifiers={
                "from_id": "a",
                "to_id": "b",
                "mode": "barter",
            },
        )


def test_use_requires_item_id():
    with pytest.raises(ValidationError, match="item_id"):
        _validate("use", modifiers={})


def test_use_with_item_id():
    _validate("use", modifiers={"item_id": "potion_01"})


def test_attack_requires_target_ids():
    with pytest.raises(ValidationError, match="target_id"):
        _validate("attack", target_ids=[])


def test_attack_with_target():
    _validate("attack", target_ids=["goblin_01"])


def test_attack_force_enum():
    with pytest.raises(ValidationError, match="force"):
        _validate("attack", target_ids=["a"], modifiers={"force": "kill"})


def test_attack_subdue_force_passes():
    _validate("attack", target_ids=["a"], modifiers={"force": "subdue"})


def test_cast_requires_skill_id():
    with pytest.raises(ValidationError, match="skill_id"):
        _validate("cast", modifiers={})


def test_cast_with_skill():
    _validate("cast", modifiers={"skill_id": "heal_01"})


def test_speak_requires_intent():
    with pytest.raises(ValidationError, match="intent"):
        _validate("speak", modifiers={})


def test_speak_intent_friendly():
    _validate("speak", modifiers={"intent": "friendly"})


def test_speak_intent_unknown_rejected():
    with pytest.raises(ValidationError, match="intent"):
        _validate("speak", modifiers={"intent": "confused"})


def test_speak_kind_enum():
    with pytest.raises(ValidationError, match="kind"):
        _validate(
            "speak",
            modifiers={"intent": "recruit", "kind": "fellowship"},
        )


def test_perceive_optional_target():
    _validate("perceive", target_ids=["loc_01"])
    _validate("perceive")


def test_rest_no_modifiers():
    _validate("rest")


def test_rest_forbids_targets():
    with pytest.raises(ValidationError, match="target_ids"):
        _validate("rest", target_ids=["loc_01"])


def test_wait_no_modifiers():
    _validate("wait")


def test_wait_with_tail_intent():
    _validate("wait", modifiers={"tail_intent": "잠시 숨을 고른다."})


def test_unknown_modifier_silently_dropped():
    v = _validate(
        "speak",
        modifiers={"intent": "friendly", "ghost_key": "x"},
    )
    assert "ghost_key" not in v.modifiers


def test_no_context_skips_modifier_check():
    """Save/load path: model_validate without context must not run the
    in_combat-dependent modifier rules — saved verbs are already validated."""
    Verb.model_validate({"name": "move", "modifiers": {"manner": "hasty"}})


def test_unknown_verb_name_rejected_by_literal():
    with pytest.raises(ValidationError):
        Verb.model_validate(
            {"name": "fly", "modifiers": {}},
            context={"in_combat": False},
        )
