import json

import pytest

from src.db.graph_local_fs import LocalFsGraphRepo
from src.game.domain.graph import Graph, GraphEdge, GraphNode
from src.game.domain.progress import GameProgress
from src.game.runtime.input import GraphInputError, run_graph_input_turn


class _FakeLLM:
    def __init__(
        self,
        payload: dict,
        *,
        narration: str = "상대는 당신의 말을 듣고 잠시 생각에 잠깁니다.",
    ) -> None:
        self.payload = payload
        self.narration = narration
        self.calls = []

    async def chat(
        self,
        messages,
        think=False,
        agent=None,
        temperature=None,
        use_fallback=False,
    ):
        self.calls.append({"messages": messages, "agent": agent})
        if agent == "graph_narrate":
            return {"answer": self.narration, "think": ""}
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


async def test_graph_input_speak_writes_gm_narration_instead_of_422(tmp_path):
    repo = await _repo(tmp_path)
    llm = _FakeLLM({"actions": [{"verb": "speak", "what": "goblin_01"}]})

    result = await run_graph_input_turn(llm, repo, "game-1", "고블린에게 말을 건다")
    logs = await repo.load_log_entries("game-1")
    progress = await repo.load_progress("game-1")

    assert result.status == "executed"
    assert [entry.kind for entry in logs] == ["gm"]
    assert logs[0].text == "상대는 당신의 말을 듣고 잠시 생각에 잠깁니다."
    assert progress.turn_count == 1


async def test_graph_input_targetless_speak_defaults_to_nearby_living_npc(tmp_path):
    repo = await _repo(tmp_path)
    llm = _FakeLLM({"actions": [{"verb": "speak"}]})

    await run_graph_input_turn(llm, repo, "game-1", "근처 사람에게 말을 건다")
    progress = await repo.load_progress("game-1")
    narrate_call = [call for call in llm.calls if call["agent"] == "graph_narrate"][0]
    user_prompt = narrate_call["messages"][1]["content"]

    assert progress.active_subject_id == "goblin_01"
    assert "대화 대상: goblin_01" in user_prompt
    assert "대상 상태: 현재 장소에 있음" in user_prompt
    assert "NPC의 짧은 반응이나 대사를 포함합니다" in narrate_call["messages"][0]["content"]


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
