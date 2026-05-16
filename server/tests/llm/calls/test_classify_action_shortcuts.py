import pytest

from src.llm.calls.classify.runner import classify
from src.llm.calls.classify.schema import ClassifyInput


class _NoCallLLM:
    async def chat(self, *args, **kwargs):  # pragma: no cover - failure path
        raise AssertionError("shortcut should avoid the LLM")


def _context(*, mode: str = "exploration") -> dict:
    return {
        "mode": mode,
        "identity": {
            "player": {"id": "player_01", "name": "당신"},
            "location": {"id": "test_hub", "name": "테스트 허브"},
            "visible_targets": [
                {
                    "id": "training_dummy",
                    "name": "훈련용 허수아비",
                    "type": "npc",
                },
                {
                    "id": "heavy_training_golem",
                    "name": "중장 훈련 골렘",
                    "type": "npc",
                },
            ],
            "exits": [],
            "inventory": [],
            "equipment": {},
            "skills": [
                {"id": "training_strike", "name": "훈련 일격"},
            ],
            "location_items": [
                {"id": "supply_token", "name": "보급 표식", "kind": "item"},
            ],
            "merchants": [],
            "corpses": [],
            "active_quest": None,
        },
        "affordances": {
            "can_attack": ["training_dummy", "heavy_training_golem"],
            "can_pick_up": ["supply_token"],
        },
        "references": {},
        "budget": {},
    }


@pytest.mark.parametrize(
    ("player_input", "target_id"),
    [
        ("훈련용 허수아비를 공격한다", "training_dummy"),
        ("중장 훈련 골렘을 공격한다", "heavy_training_golem"),
    ],
)
async def test_korean_attack_to_visible_character_shortcuts_without_llm(
    player_input,
    target_id,
):
    output = await classify(
        _NoCallLLM(),
        ClassifyInput(player_input=player_input, context=_context()),
        locale="ko",
    )

    assert output.actions is not None
    assert output.actions[0].verb == "attack"
    assert output.actions[0].what == [target_id]


async def test_korean_skill_attack_keeps_skill_and_target_without_llm():
    output = await classify(
        _NoCallLLM(),
        ClassifyInput(
            player_input="훈련 일격으로 훈련용 허수아비를 공격한다",
            context=_context(),
        ),
        locale="ko",
    )

    assert output.actions is not None
    action = output.actions[0]
    assert action.verb == "attack"
    assert action.what == ["training_dummy"]
    assert action.with_ == "training_strike"


async def test_korean_pickup_location_item_shortcuts_without_llm():
    output = await classify(
        _NoCallLLM(),
        ClassifyInput(player_input="보급 표식을 획득한다", context=_context()),
        locale="ko",
    )

    assert output.actions is not None
    action = output.actions[0]
    assert action.verb == "transfer"
    assert action.what == "supply_token"
    assert action.from_ == "test_hub"
    assert action.to == "player_01"
    assert action.how == "free"


async def test_korean_corpse_inspect_loots_single_carried_item_without_llm():
    context = _context()
    context["identity"]["corpses"] = [
        {
            "id": "corpse_01",
            "name": "쓰러진 허수아비",
            "inventory": [{"id": "reward_badge", "name": "검증 배지", "kind": "item"}],
        }
    ]

    output = await classify(
        _NoCallLLM(),
        ClassifyInput(player_input="쓰러진 허수아비를 조사한다", context=context),
        locale="ko",
    )

    assert output.actions is not None
    action = output.actions[0]
    assert action.verb == "transfer"
    assert action.what == "reward_badge"
    assert action.from_ == "corpse_01"
    assert action.to == "player_01"
    assert action.how == "free"


async def test_korean_flee_in_combat_shortcuts_without_llm():
    output = await classify(
        _NoCallLLM(),
        ClassifyInput(player_input="도망친다", context=_context(mode="combat")),
        locale="ko",
    )

    assert output.actions is not None
    action = output.actions[0]
    assert action.verb == "move"
    assert action.how == "hasty"
