import pytest

from src.llm_calls.classify.schema import JudgeOutput, RefuseReason, Verb
from src.llm_calls.classify.semantics import JudgeSemanticError, check_semantics


def test_refuse_skips_check():
    output = JudgeOutput(refuse=RefuseReason(category="out_of_game", message_hint="x"))
    check_semantics(output, {"entities": []})


def test_attack_target_alive_check():
    output = JudgeOutput(actions=[Verb(name="attack", target_ids=["dead_01"])])
    surroundings = {"entities": [{"id": "dead_01", "type": "item"}]}
    with pytest.raises(JudgeSemanticError):
        check_semantics(output, surroundings)


def test_attack_friendly_npc_rejected():
    output = JudgeOutput(actions=[Verb(name="attack", target_ids=["n_01"])])
    surroundings = {"entities": [{"id": "n_01", "type": "npc", "friendly": True}]}
    with pytest.raises(JudgeSemanticError, match="friendly"):
        check_semantics(output, surroundings)


def test_attack_hostile_npc_passes():
    output = JudgeOutput(actions=[Verb(name="attack", target_ids=["n_01"])])
    surroundings = {"entities": [{"id": "n_01", "type": "npc", "friendly": False}]}
    check_semantics(output, surroundings)


def test_speak_recruit_target_in_entities_required():
    output = JudgeOutput(actions=[Verb(name="speak",
                                       modifiers={"intent": "recruit", "target": "ghost_npc"})])
    with pytest.raises(JudgeSemanticError):
        check_semantics(output, {"entities": []})


def test_speak_recruit_already_companion():
    output = JudgeOutput(actions=[Verb(name="speak",
                                       modifiers={"intent": "recruit", "target": "n_01"})])
    surroundings = {
        "entities": [{"id": "n_01", "type": "npc", "relations_player": 50}],
        "companions": ["n_01"],
    }
    with pytest.raises(JudgeSemanticError, match="already a companion"):
        check_semantics(output, surroundings)


def test_speak_part_not_companion():
    output = JudgeOutput(actions=[Verb(name="speak",
                                       modifiers={"intent": "part", "target": "n_01"})])
    surroundings = {"companions": []}
    with pytest.raises(JudgeSemanticError, match="not a companion"):
        check_semantics(output, surroundings)


def test_speak_part_companion_passes():
    output = JudgeOutput(actions=[Verb(name="speak",
                                       modifiers={"intent": "part", "target": "n_01"})])
    surroundings = {"companions": ["n_01"]}
    check_semantics(output, surroundings)


def test_speak_friendly_no_check():
    """non-recruit/part intents have no surroundings-based check."""
    output = JudgeOutput(actions=[Verb(name="speak",
                                       modifiers={"intent": "friendly", "target": "n_01"})])
    check_semantics(output, {"entities": []})


def test_transfer_buy_npc_in_merchants():
    output = JudgeOutput(actions=[Verb(name="transfer", modifiers={
        "from_id": "n_01", "to_id": "player_01",
        "mode": "trade", "item_id": "potion_01",
    })])
    surroundings = {
        "merchants": [{"id": "n_01", "stock": [{"id": "potion_01"}]}],
    }
    check_semantics(output, surroundings)


def test_transfer_buy_item_not_in_stock():
    output = JudgeOutput(actions=[Verb(name="transfer", modifiers={
        "from_id": "n_01", "to_id": "player_01",
        "mode": "trade", "item_id": "ghost_item",
    })])
    surroundings = {
        "merchants": [{"id": "n_01", "stock": [{"id": "potion_01"}]}],
    }
    with pytest.raises(JudgeSemanticError, match="not in"):
        check_semantics(output, surroundings)


def test_use_item_in_inventory():
    output = JudgeOutput(actions=[Verb(name="use", modifiers={"item_id": "herb_01"})])
    surroundings = {"inventory": [{"id": "herb_01", "kind": "consumable"}]}
    check_semantics(output, surroundings)


def test_use_weapon_rejected():
    output = JudgeOutput(actions=[Verb(name="use", modifiers={"item_id": "sword_01"})])
    surroundings = {"inventory": [{"id": "sword_01", "kind": "weapon"}]}
    with pytest.raises(JudgeSemanticError, match="weapon"):
        check_semantics(output, surroundings)


def test_rest_no_check_skipped():
    output = JudgeOutput(actions=[Verb(name="rest")])
    check_semantics(output, {"entities": []})


def test_wait_no_check():
    output = JudgeOutput(actions=[Verb(name="wait")])
    check_semantics(output, {"entities": []})


def test_perceive_no_check():
    output = JudgeOutput(actions=[Verb(name="perceive")])
    check_semantics(output, {"entities": []})
