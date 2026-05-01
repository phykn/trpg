import os

import pytest

from src.agents.dc_judge import judge
from src.agents.dc_judge.schema import (
    CombatAction,
    JudgeInput,
    PassAction,
    RejectAction,
    RollAction,
)
from src.llm.client import LLMClient

pytestmark = pytest.mark.live


@pytest.fixture
def client():
    base_url = os.environ.get("BASE_URL", "http://localhost:8000/v1")
    return LLMClient.from_single(base_url=base_url, model="local")


@pytest.fixture
def surroundings():
    return {
        "location": {"id": "tavern", "name": "술집"},
        "entities": [
            {"id": "player_01", "name": "너", "type": "player"},
            {"id": "guard_01", "name": "경비병", "type": "npc"},
            {"id": "guard_02", "name": "경비병", "type": "npc"},
            {"id": "goblin_01", "name": "고블린", "type": "npc"},
            {"id": "chest_01", "name": "상자", "type": "item", "difficulty": "어려움"},
        ],
    }


@pytest.mark.parametrize(
    "text,expected",
    [
        ("자리에 앉는다", PassAction),
        ("아 씨발 짜증나", RejectAction),
        ("경비병 설득해서 통과시켜달라고 해", RollAction),
        ("고블린에게 활을 쏜다", CombatAction),
        ("뭔가 해봐", PassAction),
        ("드래곤에게 저주를 건다", RollAction),
    ],
)
async def test_judge_classifies(client, surroundings, text, expected):
    result = await judge(
        client, JudgeInput(player_input=text, surroundings=surroundings)
    )
    assert isinstance(result, expected)


async def test_judge_roll_emits_korean_tier_and_targets(client, surroundings):
    result = await judge(
        client,
        JudgeInput(
            player_input="경비병 설득해서 통과시켜달라고 해",
            surroundings=surroundings,
        ),
    )
    assert isinstance(result, RollAction)
    assert result.tier in (
        "매우 쉬움",
        "쉬움",
        "보통",
        "어려움",
        "매우 어려움",
        "전설",
        "신화",
    )
    assert result.targets == ["guard_01"]
    assert result.reason and len(result.reason) >= 4
