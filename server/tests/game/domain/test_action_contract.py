import pytest
from pydantic import ValidationError

from src.game.domain.action import Action, action_to_verb, verb_to_action
from src.game.domain.verb import Verb


def test_action_accepts_from_and_with_aliases():
    action = Action.model_validate(
        {
            "verb": "transfer",
            "what": "sword_01",
            "from": "<self>.inventory",
            "to": "<self>.equipped.weapon",
            "with": "both_hands",
            "how": "gift",
        }
    )

    assert action.from_ == "<self>.inventory"
    assert action.with_ == "both_hands"
    dumped = action.model_dump(by_alias=True)
    assert dumped["from"] == "<self>.inventory"
    assert dumped["with"] == "both_hands"


def test_action_rejects_result_fields():
    with pytest.raises(ValidationError, match="success"):
        Action.model_validate({"verb": "attack", "what": "goblin_01", "success": True})


def test_pass_action_converts_to_wait_verb():
    verb = action_to_verb(Action(verb="pass", note="숨을 고른다."))

    assert verb.name == "wait"
    assert verb.modifiers["tail_intent"] == "숨을 고른다."


def test_transfer_action_converts_to_legacy_verb():
    verb = action_to_verb(
        Action.model_validate(
            {
                "verb": "transfer",
                "what": "coin_01",
                "from": "merchant_01",
                "to": "player_01",
                "how": "trade",
            }
        )
    )

    assert verb.name == "transfer"
    assert verb.modifiers == {
        "from_id": "merchant_01",
        "to_id": "player_01",
        "mode": "trade",
        "item_id": "coin_01",
    }


def test_attack_action_converts_targets_and_skill():
    verb = action_to_verb(
        Action.model_validate(
            {
                "verb": "attack",
                "what": ["goblin_01", "orc_01"],
                "with": "fireball",
                "how": "surprise",
            }
        )
    )

    assert verb.name == "attack"
    assert verb.target_ids == ["goblin_01", "orc_01"]
    assert verb.modifiers == {"skill_id": "fireball", "surprise": True}


def test_query_action_converts_topic():
    verb = action_to_verb(Action(verb="query", what="exits"))

    assert verb.name == "query"
    assert verb.modifiers == {"topic": "exits"}


def test_legacy_verb_converts_back_to_action():
    action = verb_to_action(
        Verb(
            name="transfer",
            modifiers={
                "from_id": "<self>.inventory",
                "to_id": "<self>.equipped.weapon",
                "mode": "gift",
                "item_id": "sword_01",
            },
        )
    )

    assert action.verb == "transfer"
    assert action.what == "sword_01"
    assert action.from_ == "<self>.inventory"
    assert action.to == "<self>.equipped.weapon"
    assert action.how == "gift"
