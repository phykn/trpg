import pytest
from pydantic import ValidationError

from src.game.domain.action import ActionOutput


def _validate(action: dict, *, in_combat: bool = False) -> ActionOutput:
    return ActionOutput.model_validate(
        {"actions": [action]},
        context={"in_combat": in_combat},
    )


def test_move_requires_destination_outside_combat():
    with pytest.raises(ValidationError, match="move"):
        _validate({"verb": "move"})


def test_move_destination_passes():
    _validate({"verb": "move", "to": "loc_01"})


def test_move_in_combat_destination_optional():
    _validate({"verb": "move", "how": "hasty"}, in_combat=True)


def test_transfer_required_keys():
    with pytest.raises(ValidationError, match="transfer.from"):
        _validate({"verb": "transfer", "to": "player_01", "how": "trade"})


def test_transfer_complete():
    _validate(
        {
            "verb": "transfer",
            "from": "merchant_01",
            "to": "player_01",
            "how": "trade",
            "what": "potion_01",
        }
    )


def test_transfer_unknown_mode_rejected():
    with pytest.raises(ValidationError, match="transfer.how"):
        _validate(
            {
                "verb": "transfer",
                "from": "a",
                "to": "b",
                "how": "barter",
            }
        )


def test_transfer_equip_uses_slot_destination_without_actor_refs():
    _validate({"verb": "transfer", "what": "sword_01", "to": "weapon", "how": "equip"})


def test_transfer_equip_rejects_unknown_slot():
    with pytest.raises(ValidationError, match="transfer.to"):
        _validate(
            {"verb": "transfer", "what": "sword_01", "to": "backpack", "how": "equip"}
        )


def test_transfer_unequip_requires_item_but_not_actor_refs():
    _validate({"verb": "transfer", "what": "sword_01", "how": "unequip"})


def test_use_requires_item_id():
    with pytest.raises(ValidationError, match="use.what"):
        _validate({"verb": "use"})


def test_use_with_item_id():
    _validate({"verb": "use", "what": "potion_01"})


def test_attack_requires_targets():
    with pytest.raises(ValidationError, match="attack.what"):
        _validate({"verb": "attack", "what": []})


def test_attack_with_target():
    _validate({"verb": "attack", "what": ["goblin_01"]})


def test_cast_is_rejected_as_legacy_top_level_action():
    with pytest.raises(ValidationError):
        _validate({"verb": "cast", "with": "heal_01"})


def test_speak_requires_intent():
    with pytest.raises(ValidationError, match="speak.how"):
        _validate({"verb": "speak"})


def test_speak_intent_friendly():
    _validate({"verb": "speak", "how": "friendly"})


def test_speak_intent_unknown_rejected():
    with pytest.raises(ValidationError, match="speak.how"):
        _validate({"verb": "speak", "how": "confused"})


def test_perceive_optional_target():
    _validate({"verb": "perceive", "what": "loc_01"})
    _validate({"verb": "perceive"})


def test_decide_requires_quest_and_choice():
    _validate({"verb": "decide", "what": "quest_01", "how": "record"})
    with pytest.raises(ValidationError, match="decide.what"):
        _validate({"verb": "decide", "how": "record"})
    with pytest.raises(ValidationError, match="decide.how"):
        _validate({"verb": "decide", "what": "quest_01"})


def test_query_action_rejected_by_literal():
    with pytest.raises(ValidationError):
        _validate({"verb": "query", "what": "exits"})


def test_unknown_action_rejected_by_literal():
    with pytest.raises(ValidationError):
        _validate({"verb": "fly"})
