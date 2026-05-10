from pathlib import Path

import pytest

from agency.qa.harness.agent import PlayerAgent


class FakeLLM:
    def __init__(self) -> None:
        self.messages: list[dict] = []

    async def chat(self, messages: list[dict], **kwargs) -> dict:
        self.messages = messages
        return {"answer": "성장한다"}


@pytest.mark.asyncio
async def test_player_agent_priority_guard_uses_graph_growth_terms(tmp_path: Path):
    prompt_path = tmp_path / "agent.md"
    prompt_path.write_text("persona", encoding="utf-8")
    llm = FakeLLM()
    agent = PlayerAgent("tester", prompt_path, llm)

    await agent.next_input("나: 레벨업 가능", "성장할 수 있습니다.", turn_no=1)

    user_msg = llm.messages[1]["content"]
    assert "몸을 단련한다" in user_msg
    assert "존재감을 키운다" in user_msg
    assert "skill_candidates" not in user_msg
    assert "STR" not in user_msg
    assert "CHA" not in user_msg
