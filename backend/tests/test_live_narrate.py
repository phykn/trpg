import os

import pytest

from src.agents.narrate import (
    NarrateInput,
    NarrativeDelta,
    NarrativeFinal,
    stream_narrate,
)
from src.llm.client import LLMClient

pytestmark = pytest.mark.live


@pytest.fixture
def client():
    base_url = os.environ.get("BASE_URL", "http://localhost:8000/v1")
    return LLMClient(base_url=base_url, model="local")


async def _collect(stream):
    body = ""
    final: NarrativeFinal | None = None
    async for item in stream:
        if isinstance(item, NarrativeDelta):
            body += item.text
        else:
            final = item
    assert final is not None
    return body, final


async def test_narrate_roll_success(client):
    input_ = NarrateInput(
        world="중세 판타지",
        session={"chapter": None, "world_time": "0812-04-28T14:00:00"},
        history="",
        target_view={
            "type": "npc",
            "name": "경비병",
            "tone_hint": "격식체",
            "disposition": {"lawful": 70, "moral": 50, "aggressive": 40},
            "affinity": 0,
        },
        surroundings={
            "location": {"id": "plaza_01", "name": "광장"},
            "entities": [
                {"id": "player_01", "name": "너", "type": "player"},
                {"id": "guard_01", "name": "경비병", "type": "npc"},
            ],
        },
        judge_result={
            "action": "roll",
            "tier": "보통",
            "stat": "CHA",
            "targets": ["guard_01"],
        },
        grade="success",
        player_input="경비병에게 동전을 쥐여주며 통과시켜달라고 한다",
    )
    body, final = await _collect(stream_narrate(client, input_))
    assert len(body) > 20
    assert final.output.turn_summary


async def test_narrate_reject_engine_forces_clean_output(client):
    """note: this checks the *agent prompt* discipline (state_changes empty for reject).
    pipeline/narrate.py adds a stronger engine-level enforcement on top."""
    input_ = NarrateInput(
        world="중세 판타지",
        session={"chapter": None, "world_time": "0812-04-28T14:00:00"},
        history="",
        target_view=None,
        surroundings={
            "location": {"id": "plaza", "name": "광장"},
            "entities": [{"id": "player_01", "name": "너", "type": "player"}],
        },
        judge_result={"action": "reject"},
        grade=None,
        player_input="너 누구야? 진짜 화나네",
    )
    body, final = await _collect(stream_narrate(client, input_))
    assert len(body) > 0
    # Body content varies too much to assert on (the model often phrases the
    # rejection in-world: "an unknown force", "dizziness" etc). Only check
    # that state_changes is empty.
    assert final.output.state_changes == []
    assert final.output.memorable is False
