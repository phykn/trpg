import json

from src.llm.calls.classify.action_builder import build_action_output
from src.llm.calls.classify.schema import validate_action_output_json


def _surroundings() -> dict:
    return {
        "entities": [
            {"id": "player_01", "name": "당신", "type": "player"},
            {"id": "guard_01", "name": "경비병", "type": "npc"},
            {"id": "merchant_01", "name": "상인", "type": "npc"},
            {"id": "goblin_01", "name": "고블린", "type": "enemy"},
            {"id": "north_gate", "name": "북문", "type": "connection"},
        ],
        "location": {"id": "loc_01", "name": "광장"},
        "inventory": [{"id": "dagger_01", "name": "단검"}],
        "equipment": {"weapon": {"id": "sword_01", "name": "검"}},
        "skills": [{"id": "slash_01", "name": "베기"}],
        "location_items": [{"id": "coin_01", "name": "동전"}],
        "merchants": [
            {
                "id": "merchant_01",
                "name": "상인",
                "stock": [{"id": "potion_01", "name": "회복약"}],
            }
        ],
        "corpses": [
            {
                "id": "corpse_01",
                "name": "쓰러진 고블린",
                "inventory": [{"id": "fang_01", "name": "송곳니"}],
            }
        ],
        "quests": [{"id": "quest_01", "name": "경비 의뢰"}],
    }


def test_build_action_output_converts_buy_intent_to_transfer_action():
    output = build_action_output(
        {
            "intents": [
                {
                    "intent": "buy",
                    "merchant_id": "merchant_01",
                    "item_id": "potion_01",
                }
            ]
        },
        _surroundings(),
    )

    assert output.actions is not None
    assert output.actions[0].model_dump(
        mode="json", by_alias=True, exclude_none=True
    ) == {
        "verb": "transfer",
        "what": "potion_01",
        "from": "merchant_01",
        "to": "player_01",
        "how": "trade",
    }


def test_build_action_output_converts_move_intent_to_move_action():
    output = build_action_output(
        {"intents": [{"intent": "move", "destination_id": "north_gate"}]},
        _surroundings(),
    )

    assert output.actions is not None
    assert output.actions[0].verb == "move"
    assert output.actions[0].to == "north_gate"


def test_build_action_output_converts_non_combat_skill_use_intent():
    output = build_action_output(
        {
            "intents": [
                {
                    "intent": "use",
                    "skill_id": "minor_heal_01",
                    "target": "player_01",
                }
            ]
        },
        _surroundings(),
    )

    assert output.actions is not None
    assert output.actions[0].model_dump(
        mode="json", by_alias=True, exclude_none=True
    ) == {
        "verb": "use",
        "to": "player_01",
        "with": "minor_heal_01",
    }


def test_build_action_output_carries_check_hint_separately_from_action():
    output = build_action_output(
        {
            "intents": [
                {
                    "intent": "move",
                    "destination_id": "north_gate",
                    "check_required": True,
                    "check_reason": "무너진 길을 조심히 건너야 합니다.",
                }
            ]
        },
        _surroundings(),
    )

    assert output.actions is not None
    assert output.actions[0].verb == "move"
    assert output.action_checks[0].required is True
    assert output.action_checks[0].reason == "무너진 길을 조심히 건너야 합니다."


def test_build_action_output_converts_uncertain_inspect_to_perceive_with_check_reason():
    output = build_action_output(
        {
            "intents": [
                {
                    "intent": "inspect",
                    "target": "guard_01",
                    "check_required": True,
                    "check_reason": "경비병의 말투에서 숨긴 뜻을 읽어야 합니다.",
                }
            ]
        },
        _surroundings(),
    )

    assert output.actions is not None
    assert output.actions[0].model_dump(
        mode="json", by_alias=True, exclude_none=True
    ) == {
        "verb": "perceive",
        "what": "guard_01",
    }
    assert output.action_checks[0].required is True
    assert output.action_checks[0].reason == "경비병의 말투에서 숨긴 뜻을 읽어야 합니다."


def test_build_action_output_converts_public_info_request_to_query_without_check():
    output = build_action_output(
        {
            "intents": [
                {
                    "intent": "query",
                    "topic": "exits",
                    "check_required": False,
                }
            ]
        },
        _surroundings(),
    )

    assert output.actions is not None
    assert output.actions[0].model_dump(
        mode="json", by_alias=True, exclude_none=True
    ) == {
        "verb": "query",
        "what": "exits",
    }
    assert output.action_checks[0].required is False


def test_validate_action_output_json_accepts_intent_json():
    raw = json.dumps(
        {
            "intents": [
                {
                    "intent": "attack",
                    "target": "goblin_01",
                    "skill_id": "slash_01",
                }
            ]
        }
    )

    out = validate_action_output_json(raw, surroundings=_surroundings())

    assert out.actions is not None
    assert out.actions[0].verb == "attack"
    assert out.actions[0].what == ["goblin_01"]
    assert out.actions[0].with_ == "slash_01"


def test_build_action_output_keeps_combat_tactic_separate_from_intent():
    output = build_action_output(
        {
            "intents": [
                {
                    "intent": "attack",
                    "target": "goblin_01",
                    "tactic": "reckless",
                }
            ]
        },
        {**_surroundings(), "in_combat": True},
    )

    assert output.actions is not None
    assert output.actions[0].verb == "attack"
    assert output.actions[0].how == "reckless"


def test_build_action_output_supports_existing_intent_catalog():
    cases = [
        (
            {"intent": "sell", "merchant_id": "merchant_01", "item_id": "dagger_01"},
            {
                "verb": "transfer",
                "what": "dagger_01",
                "from": "player_01",
                "to": "merchant_01",
                "how": "trade",
            },
        ),
        (
            {"intent": "equip", "item_id": "dagger_01", "slot": "weapon"},
            {"verb": "transfer", "what": "dagger_01", "to": "weapon", "how": "equip"},
        ),
        (
            {"intent": "unequip", "item_id": "sword_01"},
            {"verb": "transfer", "what": "sword_01", "how": "unequip"},
        ),
        (
            {"intent": "use", "item_id": "dagger_01", "target": "player_01"},
            {"verb": "use", "what": "dagger_01", "to": "player_01"},
        ),
        (
            {"intent": "cast", "skill_id": "slash_01", "target": "goblin_01"},
            {"verb": "attack", "what": ["goblin_01"], "with": "slash_01"},
        ),
        (
            {"intent": "cast", "skill_id": "heal_01", "target": "player_01"},
            {"verb": "use", "with": "heal_01", "to": "player_01"},
        ),
        (
            {"intent": "give", "item_id": "dagger_01", "target": "guard_01"},
            {
                "verb": "transfer",
                "what": "dagger_01",
                "from": "player_01",
                "to": "guard_01",
                "how": "free",
            },
        ),
        (
            {"intent": "steal", "item_id": "dagger_01", "target": "guard_01"},
            {
                "verb": "transfer",
                "what": "dagger_01",
                "from": "guard_01",
                "to": "player_01",
                "how": "steal",
            },
        ),
        (
            {"intent": "loot", "item_id": "fang_01", "source_id": "corpse_01"},
            {
                "verb": "transfer",
                "what": "fang_01",
                "from": "corpse_01",
                "to": "player_01",
                "how": "free",
            },
        ),
        (
            {"intent": "accept_quest", "quest_id": "quest_01", "target": "guard_01"},
            {
                "verb": "transfer",
                "what": "quest_01",
                "from": "guard_01",
                "to": "player_01",
                "how": "accept",
            },
        ),
        (
            {
                "intent": "abandon_quest",
                "quest_id": "quest_01",
                "target": "guard_01",
            },
            {
                "verb": "transfer",
                "what": "quest_01",
                "from": "player_01",
                "to": "guard_01",
                "how": "abandon",
            },
        ),
        (
            {"intent": "pickup", "item_id": "coin_01"},
            {
                "verb": "transfer",
                "what": "coin_01",
                "from": "loc_01",
                "to": "player_01",
                "how": "free",
            },
        ),
        (
            {"intent": "flee"},
            {"verb": "move", "how": "create_distance"},
            {"in_combat": True},
        ),
        ({"intent": "rest"}, {"verb": "rest"}),
    ]

    for case in cases:
        intent, expected = case[0], case[1]
        surroundings = {**_surroundings(), **(case[2] if len(case) > 2 else {})}
        output = build_action_output({"intents": [intent]}, surroundings)
        assert output.actions is not None
        assert (
            output.actions[0].model_dump(
                mode="json",
                by_alias=True,
                exclude_none=True,
            )
            == expected
        )
