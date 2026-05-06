import pytest

from src.llm.calls.classify.errors import ModifierValidationError
from src.llm.calls.classify.modifiers import _MODIFIER_SCHEMAS, validate_modifiers
from src.llm.calls.classify.schema import Verb


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
    v = Verb(name="move", modifiers={})
    with pytest.raises(ModifierValidationError, match="destination"):
        validate_modifiers(v, in_combat=False)


def test_move_destination_passes():
    validate_modifiers(
        Verb(name="move", modifiers={"destination": "loc_01"}), in_combat=False
    )


def test_move_in_combat_destination_optional():
    validate_modifiers(Verb(name="move", modifiers={"manner": "hasty"}), in_combat=True)


def test_transfer_required_keys():
    v = Verb(name="transfer", modifiers={"from_id": "a", "to_id": "b"})
    with pytest.raises(ModifierValidationError):
        validate_modifiers(v, in_combat=False)


def test_transfer_complete():
    validate_modifiers(
        Verb(
            name="transfer",
            modifiers={
                "from_id": "merchant_01",
                "to_id": "player_01",
                "mode": "trade",
                "item_id": "potion_01",
                "price": 5,
            },
        ),
        in_combat=False,
    )


def test_attack_target_cardinality():
    v = Verb(name="attack", target_ids=[], modifiers={})
    with pytest.raises(ModifierValidationError, match="target"):
        validate_modifiers(v, in_combat=False)


def test_cast_target_optional_skill_required():
    validate_modifiers(
        Verb(name="cast", target_ids=[], modifiers={"skill_id": "heal_01"}),
        in_combat=True,
    )
    with pytest.raises(ModifierValidationError, match="skill_id"):
        validate_modifiers(Verb(name="cast"), in_combat=True)


def test_speak_required_intent():
    v = Verb(name="speak", modifiers={"target": "npc_01"})
    with pytest.raises(ModifierValidationError, match="intent"):
        validate_modifiers(v, in_combat=False)


def test_speak_unknown_modifier_silent_drop():
    v = Verb(
        name="speak", modifiers={"intent": "friendly", "target": "n", "garbage_key": 1}
    )
    validate_modifiers(v, in_combat=False)
    assert "garbage_key" not in v.modifiers


def test_speak_intent_invalid_value():
    v = Verb(name="speak", modifiers={"intent": "shout"})
    with pytest.raises(ModifierValidationError, match="intent"):
        validate_modifiers(v, in_combat=False)


def test_speak_intent_dead_values_rejected():
    """command/pray/ask/negotiate were dropped from the intent enum — narrate
    absorbs those player inputs via friendly/hostile fallback."""
    for dead in ("command", "pray", "ask", "negotiate"):
        v = Verb(name="speak", modifiers={"intent": dead})
        with pytest.raises(ModifierValidationError, match="intent"):
            validate_modifiers(v, in_combat=False)


def test_speak_intent_live_values_pass():
    for live in ("friendly", "hostile", "deceptive", "recruit", "part"):
        v = Verb(name="speak", modifiers={"intent": live, "target": "n_01"})
        validate_modifiers(v, in_combat=False)


def test_wait_target_cardinality_forbidden():
    v = Verb(name="wait", target_ids=["x"])
    with pytest.raises(ModifierValidationError, match="target_ids"):
        validate_modifiers(v, in_combat=False)


def test_alter_verb_no_longer_accepted():
    """alter was removed (10 → 9 verbs). Pydantic rejects the name at Verb
    construction — modifier validation never runs."""
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        Verb(name="alter", modifiers={"target": "door_01"})


def test_rest_no_modifier():
    validate_modifiers(Verb(name="rest"), in_combat=False)


def test_perceive_optional_target_ids():
    validate_modifiers(Verb(name="perceive", target_ids=[]), in_combat=False)
    validate_modifiers(
        Verb(name="perceive", target_ids=["loc_01"]),
        in_combat=False,
    )


def test_perceive_focus_silently_dropped():
    """focus enum was removed when perceive collapsed to a flavor verb. Stale
    LLM output carrying focus shouldn't crash — unknown modifier silent-drop
    handles it (same pattern as speak's garbage_key)."""
    v = Verb(name="perceive", modifiers={"focus": "hidden"})
    validate_modifiers(v, in_combat=False)
    assert "focus" not in v.modifiers
