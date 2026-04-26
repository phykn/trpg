"""§2.3 4단계 — 실제 LLM 으로 스킬 후보 산출 검증."""
import os

import pytest

from src.domain.entities import Character, Stats
from src.domain.memory import DialoguePair, Memory, TurnLogEntry
from src.llm.client import LLMClient
from src.flow import skill_recommend as recommend_mod
from src.domain.state import GameState

pytestmark = pytest.mark.live


@pytest.fixture
def client():
    base_url = os.environ.get("BASE_URL", "http://localhost:8000/v1")
    return LLMClient(base_url=base_url, model="local")


async def test_live_recommend_returns_three_thematic_candidates(client):
    state = GameState(
        game_id="t",
        profile="default",
        player_id="player_01",
        world_time="0812-04-28T14:00:00",
    )
    state.characters["player_01"] = Character(
        id="player_01",
        name="주",
        race_id="human",
        is_player=True,
        stats=Stats(),
        level=2,
        memories=[
            Memory(content="고블린 정찰병에게 조용히 다가가 등에 칼을 박았다.", importance=3, turn=1),
            Memory(content="대장간에서 단검을 갈아 날을 세웠다.", importance=2, turn=2),
            Memory(content="술집에서 주인을 설득해 정보를 얻어냈다.", importance=2, turn=3),
        ],
    )
    state.turn_log = [
        TurnLogEntry(turn=1, target="goblin_01", summary="잠입 후 일격으로 정찰병 처치"),
        TurnLogEntry(turn=2, target=None, summary="단검 정비"),
        TurnLogEntry(turn=3, target="barkeep_01", summary="술집 주인을 설득해 정보 획득"),
    ]
    state.recent_dialogue = [
        DialoguePair(turn=1, player="조용히 다가가서 등에 칼을 박는다", narrator="..."),
        DialoguePair(turn=3, player="주인에게 마을의 소문을 묻는다", narrator="..."),
    ]

    skills = await recommend_mod.recommend_skill_candidates(client, state)
    assert len(skills) == 3
    # 모든 후보가 level=2 로 박혀야
    assert all(s.level == 2 for s in skills)
    # type/target/primary_stat 가 enum 안 있는지 (스키마 수준에서 이미 검증됨)
    assert all(s.type in {"attack", "heal", "buff", "debuff"} for s in skills)
    assert all(s.target in {"self", "single", "area"} for s in skills)
    # 이름·설명 비어있지 않음
    assert all(s.name and s.description and s.special_effect for s in skills)
