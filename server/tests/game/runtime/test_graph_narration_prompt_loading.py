import pytest

from src.db.graph_local_fs import LocalFsGraphRepo
from src.game.domain.action import Action
from src.game.domain.combat import GraphCombatState
from src.game.domain.graph import Graph, GraphEdge, GraphNode
from src.game.domain.progress import GameProgress
from src.game.runtime.input import run_graph_input_turn
from src.game.runtime.intro import run_graph_initial_narration
from src.game.runtime.state import GameRuntimeState
from src.game.runtime.turn import run_graph_action_turn
from src.llm.calls._runner import get_prompt


class _PromptCaptureLLM:
    def __init__(self, payload=None) -> None:
        self.payload = payload or {
            "actions": [{"verb": "speak", "what": "goblin_01", "how": "friendly"}]
        }
        self.calls: list[dict] = []

    async def chat(
        self,
        messages,
        think=False,
        agent=None,
        temperature=None,
        use_fallback=False,
    ):
        self.calls.append({"agent": agent, "messages": messages})
        if agent == "classify":
            import json

            return {"answer": json.dumps(self.payload), "think": ""}
        return {"answer": "짧은 나레이션입니다.", "think": ""}


def _character(node_id: str, *, hp: int = 30) -> GraphNode:
    return GraphNode(
        id=node_id,
        type="character",
        properties={
            "name": node_id,
            "hp": hp,
            "max_hp": 30,
            "mp": 10,
            "max_mp": 10,
            "stats": {"body": 10, "agility": 10, "mind": 10, "presence": 10},
            "status": [],
        },
    )


def _graph() -> Graph:
    return Graph(
        nodes={
            "town": GraphNode(
                id="town",
                type="location",
                properties={"name": "Town", "description": "A quiet place."},
            ),
            "player_01": _character("player_01"),
            "goblin_01": _character("goblin_01", hp=8),
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


def test_graph_narration_prompt_files_are_packaged():
    assert get_prompt("graph_intro", "ko")
    assert get_prompt("graph_narrate", "ko")


@pytest.mark.asyncio
async def test_graph_intro_uses_packaged_prompt(monkeypatch, tmp_path):
    import src.game.runtime.intro as intro_module

    monkeypatch.setattr(intro_module, "get_prompt", lambda agent, locale: f"{agent}:{locale}")
    repo = await _repo(tmp_path)
    runtime = GameRuntimeState(
        graph=await repo.load_graph("game-1"),
        progress=await repo.load_progress("game-1"),
    )
    llm = _PromptCaptureLLM()

    await run_graph_initial_narration(llm, repo, runtime)  # type: ignore[arg-type]

    assert llm.calls[-1]["messages"][0]["content"] == "graph_intro:ko"


@pytest.mark.asyncio
async def test_graph_turn_narration_uses_packaged_prompt(monkeypatch, tmp_path):
    import src.game.runtime.turn as turn_module

    monkeypatch.setattr(turn_module, "get_prompt", lambda agent, locale: f"{agent}:{locale}")
    repo = await _repo(tmp_path)
    progress = await repo.load_progress("game-1")
    await repo.save_progress(
        progress.model_copy(
            update={
                "graph_combat_state": GraphCombatState(
                    location_id="town",
                    player_id="player_01",
                    enemy_ids=["goblin_01"],
                    participant_ids=["player_01", "goblin_01"],
                    sides={"player_01": "player", "goblin_01": "enemy"},
                    round=3,
                )
            }
        )
    )
    llm = _PromptCaptureLLM()

    await run_graph_action_turn(
        repo,
        "game-1",
        Action(verb="attack", what="goblin_01"),
        llm=llm,  # type: ignore[arg-type]
    )

    assert llm.calls[-1]["messages"][0]["content"] == "graph_narrate:ko"


@pytest.mark.asyncio
async def test_graph_input_narration_uses_packaged_prompt(monkeypatch, tmp_path):
    import src.game.runtime.input as input_module

    monkeypatch.setattr(input_module, "get_prompt", lambda agent, locale: f"{agent}:{locale}")
    repo = await _repo(tmp_path)
    llm = _PromptCaptureLLM()

    await run_graph_input_turn(llm, repo, "game-1", "고블린에게 말을 건다")  # type: ignore[arg-type]

    narrate_call = [call for call in llm.calls if call["agent"] == "graph_narrate"][0]
    assert narrate_call["messages"][0]["content"] == "graph_narrate:ko"
