import pytest

from src.game.domain.action import Action
from src.game.domain.graph import Graph, GraphEdge, GraphNode
from src.game.domain.progress import GameProgress
from src.game.runtime import GameRuntimeState
from src.game.runtime.action.dispatch import GraphActionDispatchResult
from src.game.runtime.narration.action import build_graph_action_narration


class _QuestAcceptLLM:
    async def chat(self, messages, think=False, agent=None, temperature=None):
        del messages, think, agent, temperature
        return {
            "answer": (
                "당신은 무대 뒤편의 빈 의자 앞에 섭니다.\n"
                "---TRPG_META---\n"
                '{"suggestions":[{"label":"의뢰 포기","input_text":"빈 의자에 앉기를 포기합니다","intent":"quest"}]}'
            )
        }


def _runtime() -> GameRuntimeState:
    return GameRuntimeState(
        graph=Graph(
            nodes={
                "stage": GraphNode(
                    id="stage",
                    type="location",
                    properties={"name": "무대 뒤"},
                ),
                "white_chair": GraphNode(
                    id="white_chair",
                    type="location",
                    properties={"name": "항구 끝 빈 의자"},
                ),
                "player_01": GraphNode(
                    id="player_01",
                    type="character",
                    properties={
                        "name": "주인공",
                        "hp": 10,
                        "max_hp": 10,
                        "mp": 5,
                        "max_mp": 5,
                        "alive": True,
                    },
                ),
                "quest_white_chair": GraphNode(
                    id="quest_white_chair",
                    type="quest",
                    properties={"title": "빈 의자에 앉기", "status": "active"},
                ),
            },
            edges={
                "located_at:player_01:stage": GraphEdge(
                    id="located_at:player_01:stage",
                    type="located_at",
                    from_node_id="player_01",
                    to_node_id="stage",
                ),
                "connects_to:stage:white_chair": GraphEdge(
                    id="connects_to:stage:white_chair",
                    type="connects_to",
                    from_node_id="stage",
                    to_node_id="white_chair",
                ),
            },
        ),
        progress=GameProgress(game_id="game-1", player_id="player_01"),
    )


@pytest.mark.asyncio
async def test_quest_accept_discards_extra_llm_narration_but_keeps_meta():
    before = _runtime()
    after = before.model_copy(
        update={
            "progress": before.progress.model_copy(
                update={"active_quest_id": "quest_white_chair"}
            )
        }
    )
    dispatch = GraphActionDispatchResult(
        runtime=after,
        kind="quest_accept",
        applied=1,
        changed_node_ids=["quest_white_chair"],
        changed_edge_ids=[],
        removed_edge_ids=[],
    )

    result = await build_graph_action_narration(
        _QuestAcceptLLM(),
        before=before,
        after=after,
        action=Action(verb="transfer", what="quest_white_chair", how="accept"),
        dispatch=dispatch,
        card_texts=["당신은 의뢰 「빈 의자에 앉기」를 시작합니다."],
        timeout_s=1,
    )

    assert result.narration == ""
    assert [suggestion.input_text for suggestion in result.suggestions] == [
        "빈 의자에 앉기를 포기합니다"
    ]
