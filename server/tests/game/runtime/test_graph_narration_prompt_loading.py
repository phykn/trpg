import pytest

from src.db.graph_local_fs import LocalFsGraphRepo
from src.game.domain.action import Action
from src.game.domain.combat import GraphCombatState
from src.game.domain.graph import Graph, GraphEdge, GraphNode
from src.game.domain.progress import GameProgress
from src.game.runtime.flow.input import run_graph_input_turn
from src.game.runtime.flow.intro import run_graph_initial_narration
from src.game.runtime.state import GameRuntimeState
from src.game.runtime.flow.turn import run_graph_action_turn
from src.llm.calls.runner import get_prompt


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
        self.calls.append(
            {"agent": agent, "messages": messages, "temperature": temperature}
        )
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
    assert get_prompt("combat_narrate", "ko")


def test_graph_narration_prompts_encode_style_without_source_title():
    intro_prompt = get_prompt("graph_intro", "ko")
    narrate_prompt = get_prompt("graph_narrate", "ko")
    combined = f"{intro_prompt}\n{narrate_prompt}"

    assert "문체 목표" in intro_prompt
    assert "문체 목표" in narrate_prompt
    assert "감각" in combined
    assert "선택" in combined
    assert "냉소" in combined
    assert "선택하지 않은 행동" in intro_prompt
    assert "나쁜 예" in combined
    assert "좋은 예" in combined
    assert "한자" in combined
    assert "문장 수와 길이를 강제하지 않습니다" in intro_prompt
    assert "문장 수와 길이를 강제하지 않습니다" in narrate_prompt
    assert "문장 수와 길이를 강제하지 않습니다" in intro_prompt
    assert "문장 수와 길이를 강제하지 않습니다" in narrate_prompt
    assert "「」" in narrate_prompt
    assert "「허가는 받았습니다」" in narrate_prompt
    assert "직접 발화" in narrate_prompt
    assert "NPC 직접 발화" in narrate_prompt
    assert "짧은 반응으로만" not in narrate_prompt
    assert "짧은 말" not in narrate_prompt
    assert "당신의 새 대사" not in narrate_prompt
    assert "payload.combat_view" in narrate_prompt
    assert "tone.lethality" in narrate_prompt
    assert "훈련 충격" in narrate_prompt
    assert "닫는 기호는 반드시" in narrate_prompt
    assert "1~2문장" not in combined
    assert "2~3문장" not in combined
    assert "한 문장" not in intro_prompt
    assert "Baldur" not in combined
    assert "발더" not in combined
    assert "발게" not in combined


def test_graph_narration_runtime_preserves_llm_text():
    from src.game.runtime.flow.intro import _clean_intro_text

    long_text = "  긴 문장입니다.\n\n" + ("가" * 450)

    assert _clean_intro_text(long_text) == long_text


@pytest.mark.asyncio
async def test_graph_intro_uses_packaged_prompt(monkeypatch, tmp_path):
    import src.game.runtime.flow.intro as intro_module

    monkeypatch.setattr(
        intro_module, "get_prompt", lambda agent, locale: f"{agent}:{locale}"
    )
    repo = await _repo(tmp_path)
    runtime = GameRuntimeState(
        graph=await repo.load_graph("game-1"),
        progress=await repo.load_progress("game-1"),
    )
    llm = _PromptCaptureLLM()

    await run_graph_initial_narration(llm, repo, runtime)  # type: ignore[arg-type]

    assert llm.calls[-1]["messages"][0]["content"] == "graph_intro:ko"


@pytest.mark.asyncio
async def test_graph_intro_sends_rich_first_scene_payload(tmp_path):
    import json
    import src.game.runtime.flow.intro as intro_module

    repo = await _repo(tmp_path)
    runtime = GameRuntimeState(
        graph=await repo.load_graph("game-1"),
        progress=await repo.load_progress("game-1"),
    )
    llm = _PromptCaptureLLM()

    await intro_module.run_graph_initial_narration(llm, repo, runtime)  # type: ignore[arg-type]

    payload = json.loads(llm.calls[-1]["messages"][1]["content"])
    assert "player" in payload
    assert "place" in payload
    assert "visible_targets" in payload
    assert "exits" in payload
    assert "inventory" in payload


@pytest.mark.asyncio
async def test_graph_turn_narration_uses_packaged_prompt(monkeypatch, tmp_path):
    import src.game.runtime.narration.action as action_narration

    monkeypatch.setattr(
        action_narration, "get_prompt", lambda agent, locale: f"{agent}:{locale}"
    )
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

    call = [call for call in llm.calls if call["agent"] == "combat_narrate"][0]

    assert call["messages"][0]["content"] == "combat_narrate:ko"
    assert call["temperature"] == 1.0


@pytest.mark.asyncio
async def test_graph_input_narration_uses_packaged_prompt(monkeypatch, tmp_path):
    import src.game.runtime.narration.input as input_narration

    monkeypatch.setattr(
        input_narration, "get_prompt", lambda agent, locale: f"{agent}:{locale}"
    )
    repo = await _repo(tmp_path)
    llm = _PromptCaptureLLM()

    await run_graph_input_turn(llm, repo, "game-1", "고블린에게 말을 건다")  # type: ignore[arg-type]

    narrate_call = [call for call in llm.calls if call["agent"] == "graph_narrate"][0]
    assert narrate_call["messages"][0]["content"] == "graph_narrate:ko"
    assert narrate_call["temperature"] == 1.0
