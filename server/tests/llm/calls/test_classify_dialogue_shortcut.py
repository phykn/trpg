import pytest

from src.llm.calls.classify.runner import classify
from src.llm.calls.classify.schema import ClassifyInput


def _classify_test_context(surroundings: dict) -> dict:
    entities = surroundings.get("entities", [])
    return {
        "mode": "combat" if surroundings.get("in_combat") else "exploration",
        "identity": {
            "location": surroundings.get("location") or {},
            "visible_targets": [
                entity for entity in entities if entity.get("type") in {"npc", "enemy"}
            ],
            "exits": [
                {"id": entity["id"], "name": entity["name"]}
                for entity in entities
                if entity.get("type") == "connection"
            ],
            "inventory": surroundings.get("inventory", []),
            "equipment": surroundings.get("equipment", {}),
            "skills": surroundings.get("skills", []),
            "active_quest": None,
        },
        "affordances": {},
        "references": {
            "last_npc": surroundings.get("recent_npc"),
            "recent_dialogue": [],
        },
        "budget": {},
    }


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
            context=_classify_test_context(
                {
                    "in_combat": False,
                    "entities": [
                        {"id": "player_01", "name": "주인공", "type": "player"},
                        {"id": "guide_01", "name": "테스트 가이드", "type": "npc"},
                    ],
                }
            ),
        ),
        locale="ko",
    )

    assert result.actions is not None
    assert result.actions[0].verb == "speak"
    assert result.actions[0].to == "guide_01"
    assert result.actions[0].how == "friendly"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "player_input",
    [
        "서울이 추우면 뭔 줄 알아? 다섯 글자야",
        "정답은 서울시립대야 재미있지?",
        "농담 하나 할게",
    ],
)
async def test_joke_or_riddle_continues_recent_npc_dialogue(player_input):
    result = await classify(
        _NoLLM(),  # type: ignore[arg-type]
        ClassifyInput(
            player_input=player_input,
            context=_classify_test_context(
                {
                    "in_combat": False,
                    "entities": [
                        {"id": "player_01", "name": "주인공", "type": "player"},
                        {"id": "guide_01", "name": "테스트 가이드", "type": "npc"},
                    ],
                    "recent_npc": {"id": "guide_01", "name": "테스트 가이드"},
                }
            ),
        ),
        locale="ko",
    )

    assert result.actions is not None
    assert result.actions[0].verb == "speak"
    assert result.actions[0].to == "guide_01"
    assert result.actions[0].how == "friendly"
