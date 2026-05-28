import pytest

from src.llm.calls.classify.runner import classify
from src.llm.calls.classify.schema import ClassifyInput


class _NoCallLLM:
    async def chat(self, *args, **kwargs):  # pragma: no cover - failure path
        raise AssertionError("shortcut should avoid the LLM")


class _StaticLLM:
    def __init__(self, answer: str) -> None:
        self.answer = answer
        self.calls = []

    async def chat(self, messages, **kwargs):
        self.calls.append({"messages": messages, **kwargs})
        return {"answer": self.answer, "think": ""}


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
    ("player_input", "target"),
    [
        ("훈련용 허수아비를 공격한다", "training_dummy"),
        ("중장 훈련 골렘을 공격한다", "heavy_training_golem"),
    ],
)
async def test_korean_attack_to_visible_character_shortcuts_without_llm(
    player_input,
    target,
):
    output = await classify(
        _NoCallLLM(),
        ClassifyInput(player_input=player_input, context=_context()),
        locale="ko",
    )

    assert output.actions is not None
    assert output.actions[0].verb == "attack"
    assert output.actions[0].what == [target]


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


async def test_korean_visible_quest_accept_shortcuts_without_llm():
    context = _context()
    context["identity"]["available_quests"] = [
        {
            "id": "quest_01",
            "name": "통행 의뢰",
            "status": "pending",
            "giver": "training_dummy",
            "giver_name": "훈련용 허수아비",
        }
    ]

    output = await classify(
        _NoCallLLM(),
        ClassifyInput(
            player_input="훈련용 허수아비의 의뢰를 받는다",
            context=context,
        ),
        locale="ko",
    )

    assert output.actions is not None
    action = output.actions[0]
    assert action.verb == "transfer"
    assert action.what == "quest_01"
    assert action.from_ == "training_dummy"
    assert action.to == "player_01"
    assert action.how == "accept"


async def test_korean_departure_accepts_single_visible_pending_quest_without_llm():
    context = _context()
    context["identity"]["visible_targets"] = [
        {"id": "npc_eli", "name": "엘리", "type": "npc"}
    ]
    context["identity"]["available_quests"] = [
        {
            "id": "q_fog_depart",
            "name": "첫 출항",
            "status": "pending",
            "giver": "npc_eli",
            "giver_name": "엘리",
        }
    ]

    output = await classify(
        _NoCallLLM(),
        ClassifyInput(
            player_input="엘리와 함께 배에 올라 붉은섬으로 떠납니다",
            context=context,
        ),
        locale="ko",
    )

    assert output.actions is not None
    action = output.actions[0]
    assert action.verb == "transfer"
    assert action.what == "q_fog_depart"
    assert action.from_ == "npc_eli"
    assert action.to == "player_01"
    assert action.how == "accept"


async def test_korean_active_departure_quest_shortcuts_to_location_move_without_llm():
    context = _context()
    context["identity"]["active_quest"] = {
        "id": "q_fog_depart",
        "name": "첫 출항",
        "location_targets": ["loc_red_square"],
    }
    context["identity"]["exits"] = [
        {"id": "loc_fog_harbor", "name": "안개 항구"},
        {"id": "loc_red_square", "name": "붉은 광장"},
    ]

    output = await classify(
        _NoCallLLM(),
        ClassifyInput(
            player_input="엘리와 함께 배에 올라 붉은섬으로 떠납니다",
            context=context,
        ),
        locale="ko",
    )

    assert output.actions is not None
    action = output.actions[0]
    assert action.verb == "move"
    assert action.to == "loc_red_square"


async def test_korean_active_departure_move_word_shortcuts_to_location_move_without_llm():
    context = _context()
    context["identity"]["active_quest"] = {
        "id": "q_fog_depart",
        "name": "첫 출항",
        "location_targets": ["loc_red_square"],
    }
    context["identity"]["exits"] = [
        {"id": "loc_fog_harbor", "name": "안개 항구"},
        {"id": "loc_red_square", "name": "붉은섬 광장"},
    ]

    output = await classify(
        _NoCallLLM(),
        ClassifyInput(
            player_input="엘리와 함께 붉은섬으로 이동한다",
            context=context,
        ),
        locale="ko",
    )

    assert output.actions is not None
    action = output.actions[0]
    assert action.verb == "move"
    assert action.to == "loc_red_square"


async def test_generated_open_move_shortcuts_without_llm():
    output = await classify(
        _NoCallLLM(),
        ClassifyInput(
            player_input="표지판이 가리키는 북쪽 길목으로 이동합니다.",
            context=_context(),
        ),
        locale="ko",
    )

    assert output.actions is not None
    action = output.actions[0]
    assert action.verb == "move"
    assert action.to is None
    assert action.note == "generated_open_move"


async def test_generated_exit_move_uses_visible_location_without_llm():
    context = _context()
    context["identity"]["exits"] = [
        {"id": "loc_road", "name": "북쪽 길목"},
    ]

    output = await classify(
        _NoCallLLM(),
        ClassifyInput(
            player_input="북쪽 길목으로 이동합니다",
            context=context,
        ),
        locale="ko",
    )

    assert output.actions is not None
    action = output.actions[0]
    assert action.verb == "move"
    assert action.to == "loc_road"
    assert action.note is None


async def test_korean_active_quest_route_shortcuts_to_next_step_without_llm():
    context = _context()
    context["identity"]["active_quest"] = {
        "id": "q_final_stage",
        "name": "새 출발 축하식 사건",
        "location_targets": ["loc_backstage"],
        "location_routes": [
            {
                "target_id": "loc_backstage",
                "target_name": "무대 뒤",
                "next_exit_id": "loc_orange_square",
                "next_exit_name": "주황 광장",
            }
        ],
    }
    context["identity"]["exits"] = [
        {"id": "loc_silver_street", "name": "은빛 거리"},
        {"id": "loc_orange_square", "name": "주황 광장"},
    ]

    output = await classify(
        _NoCallLLM(),
        ClassifyInput(
            player_input="주황광장의 무대 뒤로 이동합니다",
            context=context,
        ),
        locale="ko",
    )

    assert output.actions is not None
    action = output.actions[0]
    assert action.verb == "move"
    assert action.to == "loc_orange_square"


async def test_korean_inspect_word_does_not_route_active_quest_move_shortcut():
    context = _context()
    context["identity"]["active_quest"] = {
        "id": "q_departure",
        "name": "출항 허가 사건",
        "location_targets": ["loc_permit_office"],
        "location_routes": [
            {
                "target_id": "loc_permit_office",
                "target_name": "출항 허가소",
                "next_exit_id": "loc_permit_office",
                "next_exit_name": "출항 허가소",
            }
        ],
    }
    context["identity"]["exits"] = [
        {"id": "loc_permit_office", "name": "출항 허가소"},
    ]

    llm = _StaticLLM('{"intents":[{"intent":"inspect"}]}')
    output = await classify(
        llm,
        ClassifyInput(
            player_input="연두 여관의 닫히지 않은 여행 가방을 살펴봅니다",
            context=context,
        ),
        locale="ko",
    )

    assert output.actions is not None
    assert output.actions[0].verb == "perceive"
    assert [call["agent"] for call in llm.calls] == ["classify"]


async def test_korean_departure_rule_question_uses_llm_instead_of_move_shortcut():
    context = _context()
    context["identity"]["visible_targets"] = [
        {"id": "npc_olden", "name": "올든", "type": "npc"}
    ]
    context["identity"]["active_quest"] = {
        "id": "q_fog_ready",
        "name": "안개 바다 준비",
        "location_targets": ["loc_fog_pier"],
    }
    context["identity"]["exits"] = [
        {"id": "loc_fog_pier", "name": "안개 항구 선착장"},
    ]

    llm = _StaticLLM(
        '{"intents":[{"intent":"talk","target":"npc_olden","manner":"friendly"}]}'
    )

    output = await classify(
        llm,
        ClassifyInput(
            player_input="올든에게 출항 규칙과 혼자 탄 배가 왜 사라지는지 확인합니다",
            context=context,
        ),
        locale="ko",
    )

    assert output.actions is not None
    action = output.actions[0]
    assert action.verb == "speak"
    assert action.to == "npc_olden"
    assert [call["agent"] for call in llm.calls] == ["classify"]


async def test_korean_missing_dialogue_target_refuses_without_llm():
    output = await classify(
        _NoCallLLM(),
        ClassifyInput(
            player_input="밀로에게 짐이 왜 젖었는지 묻습니다",
            context=_context(),
        ),
        locale="ko",
    )

    assert output.refuse is not None
    assert output.refuse.category == "invalid_transition"
    assert "보이지 않습니다" in output.refuse.message_hint


async def test_korean_quest_choice_label_shortcuts_to_decide_without_llm():
    context = _context()
    context["identity"]["active_quest"] = {
        "id": "quest_01",
        "name": "분노 환불 사건",
        "choices": [
            {"id": "record", "label": "책임을 기록으로 남깁니다"},
            {"id": "release", "label": "분노를 흘려보냅니다"},
        ],
    }

    output = await classify(
        _NoCallLLM(),
        ClassifyInput(player_input="분노를 흘려보냅니다", context=context),
        locale="ko",
    )

    assert output.actions is not None
    action = output.actions[0]
    assert action.verb == "decide"
    assert action.what == "quest_01"
    assert action.how == "release"


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


async def test_korean_ambiguous_corpse_loot_does_not_choose_without_llm():
    context = _context()
    context["identity"]["corpses"] = [
        {
            "id": "corpse_01",
            "name": "쓰러진 허수아비",
            "inventory": [{"id": "reward_badge", "name": "검증 배지", "kind": "item"}],
        },
        {
            "id": "corpse_02",
            "name": "쓰러진 골렘",
            "inventory": [{"id": "gear_01", "name": "기어", "kind": "item"}],
        },
    ]

    class _FallbackLLM:
        async def chat(self, *args, **kwargs):
            return {"answer": '{"intents":[{"intent":"pass","note":"대상을 더 특정해야 합니다."}]}'}

    output = await classify(
        _FallbackLLM(),
        ClassifyInput(player_input="시체를 조사한다", context=context),
        locale="ko",
    )

    assert output.actions is not None
    assert output.actions[0].verb == "pass"


async def test_korean_flee_in_combat_shortcuts_without_llm():
    output = await classify(
        _NoCallLLM(),
        ClassifyInput(player_input="도망친다", context=_context(mode="combat")),
        locale="ko",
    )

    assert output.actions is not None
    action = output.actions[0]
    assert action.verb == "move"
    assert action.how == "flee"
