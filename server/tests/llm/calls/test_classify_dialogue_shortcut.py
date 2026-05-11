import pytest

from src.llm.calls.classify.runner import classify
from src.llm.calls.classify.schema import ClassifyInput


class _NoLLM:
    def pick_fallback(self, agent):
        return None

    async def chat(self, messages, **kwargs):
        raise AssertionError("dialogue shortcut should not call the LLM")


@pytest.mark.asyncio
async def test_korean_question_to_visible_npc_shortcuts_to_speak():
    result = await classify(
        _NoLLM(),  # type: ignore[arg-type]
        ClassifyInput(
            player_input="테스트 가이드에게 허수아비 훈련 방법을 물어봅니다.",
            surroundings={
                "in_combat": False,
                "entities": [
                    {"id": "player_01", "name": "주인공", "type": "player"},
                    {"id": "guide_01", "name": "테스트 가이드", "type": "npc"},
                ],
            },
        ),
        locale="ko",
    )

    assert result.actions is not None
    assert result.actions[0].verb == "speak"
    assert result.actions[0].to == "guide_01"
    assert result.actions[0].how == "friendly"
