import pytest

from src.game.domain.action import Action, ActionOutput
from src.llm.calls.classify.grounding import (
    ActionGroundingError,
    validate_grounded_output,
)


def _surroundings() -> dict:
    return {
        "in_combat": False,
        "entities": [
            {"id": "player_01", "name": "주인공", "type": "player"},
            {
                "id": "goblin_01",
                "name": "고블린",
                "type": "npc",
            },
            {"id": "town_gate", "name": "성문", "type": "connection"},
            {"id": "loose_key", "name": "열쇠", "type": "item"},
        ],
        "inventory": [
            {"id": "potion_01", "name": "치유 물약", "kind": "consumable"},
            {"id": "bomb_01", "name": "폭탄", "kind": "consumable"},
        ],
        "location": {"id": "town", "name": "마을"},
        "location_items": [
            {"id": "loose_key", "name": "열쇠", "kind": "key"},
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
        "quests": [
            {
                "id": "quest_01",
                "name": "통행 의뢰",
                "choices": [{"id": "record", "label": "기록으로 남깁니다"}],
            }
        ],
    }


def test_valid_view_ids_pass():
    output = ActionOutput(
        actions=[
            Action(verb="move", to="town_gate"),
            Action(verb="use", what="potion_01"),
            Action(verb="attack", what=["goblin_01"]),
            Action(verb="use", with_="heal_01", to="player_01"),
        ]
    )

    assert validate_grounded_output(output, _surroundings()) is output


def test_unknown_move_destination_fails():
    output = ActionOutput(actions=[Action(verb="move", to="missing_loc")])

    with pytest.raises(ActionGroundingError, match="to"):
        validate_grounded_output(output, _surroundings())


def test_unknown_use_item_fails():
    output = ActionOutput(actions=[Action(verb="use", what="missing_item")])

    with pytest.raises(ActionGroundingError, match="missing item"):
        validate_grounded_output(output, _surroundings())


def test_visible_but_uncarried_use_item_fails_with_repairable_reason():
    output = ActionOutput(actions=[Action(verb="use", what="loose_key")])

    with pytest.raises(ActionGroundingError, match="item is not carried"):
        validate_grounded_output(output, _surroundings())


def test_attack_cannot_target_player_self():
    output = ActionOutput(actions=[Action(verb="attack", what=["player_01"])])

    with pytest.raises(ActionGroundingError, match="what"):
        validate_grounded_output(output, _surroundings())


def test_attack_accepts_visible_enemy_entity():
    surroundings = _surroundings()
    surroundings["entities"].append(
        {"id": "training_dummy", "name": "훈련용 허수아비", "type": "enemy"}
    )
    output = ActionOutput(actions=[Action(verb="attack", what=["training_dummy"])])

    assert validate_grounded_output(output, surroundings) is output


def test_attack_rejects_protected_visible_target():
    surroundings = _surroundings()
    surroundings["entities"].append(
        {
            "id": "protected_guard",
            "name": "경비병",
            "type": "enemy",
            "protected": True,
        }
    )
    output = ActionOutput(actions=[Action(verb="attack", what=["protected_guard"])])

    with pytest.raises(ActionGroundingError, match="protected target cannot be attacked"):
        validate_grounded_output(output, surroundings)


def test_speak_target_must_be_visible_npc():
    output = ActionOutput(
        actions=[Action(verb="speak", to="missing_npc", how="friendly")]
    )

    with pytest.raises(ActionGroundingError, match="to"):
        validate_grounded_output(output, _surroundings())


def test_transfer_accepts_self_refs_and_exposed_item_ids():
    output = ActionOutput(
        actions=[
            Action(
                verb="transfer",
                from_="<self>.equipped.weapon",
                to="<self>.inventory",
                how="free",
                what="sword_01",
            ),
            Action(
                verb="transfer",
                from_="goblin_01",
                to="player_01",
                how="trade",
                what="bread_01",
            ),
        ]
    )

    assert validate_grounded_output(output, _surroundings()) is output


def test_transfer_equip_grounds_item_and_slot_without_actor_refs():
    output = ActionOutput(
        actions=[
            Action(verb="transfer", what="potion_01", how="equip", to="weapon"),
        ]
    )

    assert validate_grounded_output(output, _surroundings()) is output


def test_transfer_unequip_grounds_equipped_item_without_actor_refs():
    output = ActionOutput(
        actions=[
            Action(verb="transfer", what="sword_01", how="unequip"),
        ]
    )

    assert validate_grounded_output(output, _surroundings()) is output


def test_transfer_equip_rejects_non_slot_destination():
    output = ActionOutput.model_construct(
        actions=[
            Action.model_construct(
                verb="transfer", what="potion_01", how="equip", to="goblin_01"
            ),
        ],
        refuse=None,
    )

    with pytest.raises(ActionGroundingError, match="to"):
        validate_grounded_output(output, _surroundings())


def test_transfer_accepts_active_quest_ids():
    output = ActionOutput(
        actions=[
            Action(
                verb="transfer",
                from_="goblin_01",
                to="player_01",
                how="accept",
                what="quest_01",
            ),
        ]
    )

    assert validate_grounded_output(output, _surroundings()) is output


def test_decide_accepts_visible_quest_id_and_data_defined_choice_id():
    output = ActionOutput(
        actions=[
            Action(verb="decide", what="quest_01", how="record"),
        ]
    )

    assert validate_grounded_output(output, _surroundings()) is output


def test_decide_rejects_unknown_quest_id():
    output = ActionOutput(
        actions=[
            Action(verb="decide", what="missing_quest", how="record"),
        ]
    )

    with pytest.raises(ActionGroundingError, match="what"):
        validate_grounded_output(output, _surroundings())


def test_decide_rejects_unknown_choice_id():
    output = ActionOutput(
        actions=[
            Action(verb="decide", what="quest_01", how="missing_choice"),
        ]
    )

    with pytest.raises(ActionGroundingError, match="how"):
        validate_grounded_output(output, _surroundings())


def test_transfer_accepts_current_location_item_pickup():
    output = ActionOutput(
        actions=[
            Action(
                verb="transfer",
                from_="town",
                to="player_01",
                how="free",
                what="loose_key",
            ),
        ]
    )

    assert validate_grounded_output(output, _surroundings()) is output


def test_transfer_rejects_loot_item_from_wrong_corpse():
    surroundings = _surroundings()
    surroundings["corpses"].append(
        {
            "id": "corpse_02",
            "name": "다른 시체",
            "inventory": [{"id": "amulet_01", "name": "부적"}],
        }
    )
    output = ActionOutput(
        actions=[
            Action(
                verb="transfer",
                from_="corpse_02",
                to="player_01",
                how="free",
                what="ring_01",
            )
        ]
    )

    with pytest.raises(ActionGroundingError, match="corpse item mismatch"):
        validate_grounded_output(output, surroundings)
