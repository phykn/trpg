import json

import pytest

from src.db.graph_local_fs import LocalFsGraphRepo
from src.game.domain.graph import Graph, GraphEdge, GraphNode
from src.game.domain.progress import GameProgress
from src.game.runtime.input import GraphInputError, run_graph_input_turn


class _FakeLLM:
    def __init__(self, payload: dict) -> None:
        self.payload = payload

    async def chat(
        self,
        messages,
        think=False,
        agent=None,
        temperature=None,
        use_fallback=False,
    ):
        return {"answer": json.dumps(self.payload, ensure_ascii=False), "think": ""}


def _character(character_id: str) -> GraphNode:
    return GraphNode(
        id=character_id,
        type="character",
        properties={
            "name": character_id,
            "hp": 30,
            "max_hp": 30,
            "mp": 10,
            "max_mp": 10,
            "alive": True,
            "stats": {"body": 3, "agility": 2, "mind": 2, "presence": 2},
        },
    )


def _graph() -> Graph:
    return Graph(
        nodes={
            "town": GraphNode(
                id="town",
                type="location",
                properties={"name": "Town"},
            ),
            "player_01": _character("player_01"),
            "goblin_01": _character("goblin_01"),
        },
        edges={
            "located_at:player_01:town": GraphEdge(
                id="located_at:player_01:town",
                type="located_at",
                from_node_id="player_01",
                to_node_id="town",
            ),
            "located_at:goblin_01:town": GraphEdge(
                id="located_at:goblin_01:town",
                type="located_at",
                from_node_id="goblin_01",
                to_node_id="town",
            ),
        },
    )


async def _repo(tmp_path) -> LocalFsGraphRepo:
    repo = LocalFsGraphRepo(str(tmp_path))
    await repo.save_graph("game-1", _graph())
    await repo.save_progress(GameProgress(game_id="game-1", player_id="player_01"))
    return repo


async def test_graph_input_classifies_one_action_and_creates_confirmation(tmp_path):
    repo = await _repo(tmp_path)
    llm = _FakeLLM({"actions": [{"verb": "attack", "what": "goblin_01"}]})

    result = await run_graph_input_turn(llm, repo, "game-1", "고블린을 공격한다")
    progress = await repo.load_progress("game-1")

    assert result.status == "confirmation_required"
    assert progress.pending_confirmation["kind"] == "attack_start"
    assert progress.graph_combat_state is None


async def test_graph_input_rejects_multi_action_output(tmp_path):
    repo = await _repo(tmp_path)
    llm = _FakeLLM(
        {
            "actions": [
                {"verb": "attack", "what": "goblin_01"},
                {"verb": "pass"},
            ]
        }
    )

    with pytest.raises(GraphInputError, match="exactly one"):
        await run_graph_input_turn(llm, repo, "game-1", "공격하고 기다린다")
