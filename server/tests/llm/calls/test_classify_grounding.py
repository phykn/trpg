import pytest

from src.game.domain.verb import Verb
from src.llm.calls.classify.grounding import (
    JudgeGroundingError,
    validate_grounded_output,
)
from src.llm.calls.classify.schema import JudgeOutput


def _surroundings() -> dict:
    return {
        "in_combat": False,
        "entities": [
            {"id": "player_01", "name": "주인공", "type": "player"},
            {
                "id": "goblin_01",
                "name": "고블린",
                "type": "npc",
                "carryables": [{"id": "coin_01", "name": "동전"}],
            },
            {"id": "town_gate", "name": "성문", "type": "connection"},
            {"id": "loose_key", "name": "열쇠", "type": "item"},
        ],
        "inventory": [
            {"id": "potion_01", "name": "치유 물약", "kind": "consumable"},
            {"id": "bomb_01", "name": "폭탄", "kind": "consumable"},
        ],
        "equipment": {
            "weapon": {"id": "sword_01", "name": "검"},
            "armor": None,
            "accessory": None,
        },
        "skills": [{"id": "heal_01", "name": "치유", "type": "heal"}],
        "merchants": [
            {
                "id": "goblin_01",
                "name": "고블린",
                "stock": [{"id": "bread_01", "name": "빵"}],
            }
        ],
        "corpses": [
            {
                "id": "corpse_01",
                "name": "시체",
                "inventory": [{"id": "ring_01", "name": "반지"}],
            }
        ],
    }


def test_valid_view_ids_pass():
    output = JudgeOutput(
        actions=[
            Verb(name="move", modifiers={"destination": "town_gate"}),
            Verb(name="use", modifiers={"item_id": "potion_01"}),
            Verb(name="attack", target_ids=["goblin_01"]),
            Verb(name="cast", modifiers={"skill_id": "heal_01"}),
        ]
    )

    assert validate_grounded_output(output, _surroundings()) is output


def test_unknown_move_destination_fails():
    output = JudgeOutput(
        actions=[Verb(name="move", modifiers={"destination": "missing_loc"})]
    )

    with pytest.raises(JudgeGroundingError, match="destination"):
        validate_grounded_output(output, _surroundings())


def test_unknown_use_item_fails():
    output = JudgeOutput(
        actions=[Verb(name="use", modifiers={"item_id": "missing_item"})]
    )

    with pytest.raises(JudgeGroundingError, match="item_id"):
        validate_grounded_output(output, _surroundings())


def test_attack_cannot_target_player_self():
    output = JudgeOutput(actions=[Verb(name="attack", target_ids=["player_01"])])

    with pytest.raises(JudgeGroundingError, match="target_ids"):
        validate_grounded_output(output, _surroundings())


def test_attack_accepts_visible_enemy_entity():
    surroundings = _surroundings()
    surroundings["entities"].append(
        {"id": "training_dummy", "name": "훈련용 허수아비", "type": "enemy"}
    )
    output = JudgeOutput(actions=[Verb(name="attack", target_ids=["training_dummy"])])

    assert validate_grounded_output(output, surroundings) is output


def test_speak_target_must_be_visible_npc():
    output = JudgeOutput(
        actions=[
            Verb(
                name="speak",
                modifiers={"intent": "friendly", "target": "missing_npc"},
            )
        ]
    )

    with pytest.raises(JudgeGroundingError, match="target"):
        validate_grounded_output(output, _surroundings())


def test_transfer_accepts_self_refs_and_exposed_item_ids():
    output = JudgeOutput(
        actions=[
            Verb(
                name="transfer",
                modifiers={
                    "from_id": "<self>.equipped.weapon",
                    "to_id": "<self>.inventory",
                    "mode": "gift",
                    "item_id": "sword_01",
                },
            ),
            Verb(
                name="transfer",
                modifiers={
                    "from_id": "goblin_01",
                    "to_id": "player_01",
                    "mode": "trade",
                    "item_id": "bread_01",
                },
            ),
        ]
    )

    assert validate_grounded_output(output, _surroundings()) is output
