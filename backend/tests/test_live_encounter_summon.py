"""LLM live — encounter_summon agent 가 페어 트레이드를 따르는 적을 산출하는지."""
import os

import pytest

from src.llm_client.agents.encounter_summon import (
    EncounterSummonInput,
    encounter_summon,
)
from src.llm_client.client import LLMClient

pytestmark = pytest.mark.live


@pytest.fixture
def client():
    base_url = os.environ.get("BASE_URL", "http://localhost:8000/v1")
    return LLMClient(base_url=base_url, model="local")


async def test_summon_forest_wolf(client):
    input_ = EncounterSummonInput(
        world="중세 판타지. 깊은 숲은 어두워 늑대가 자주 출몰하고, 굶주린 야수가 길손을 노린다.",
        location={
            "id": "forest_01",
            "name": "외진 숲길",
            "description": "달빛이 가까스로 새는 빽빽한 숲속 길.",
            "tags": ["야외", "어두움"],
            "weather": ["바람", "찬 공기"],
            "sleep_risk": "risky",
        },
        player_level=2,
        available_races=[
            {"id": "wolf", "name": "늑대", "description": "회색 털, 무리 사냥꾼"},
            {"id": "human", "name": "인간", "description": "보통 사람"},
        ],
    )
    out = await encounter_summon(client, input_)
    # 페어 트레이드는 schema validator 가 강제 — 산출 자체가 invariant.
    s = out.stats
    assert s.STR + s.CHA == 20
    assert s.DEX + s.WIS == 20
    assert s.CON + s.INT == 20
    # race_id 는 가용 풀 안.
    assert out.race_id in ("wolf", "human")
    # 한국어 출력.
    assert any("가" <= ch <= "힣" for ch in out.name)
