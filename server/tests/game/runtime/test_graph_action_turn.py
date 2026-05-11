import asyncio
import time

import pytest

from src.db.graph_local_fs import LocalFsGraphRepo
from src.game.domain.action import Action
from src.game.domain.combat import GraphCombatState
from src.game.domain.graph import Graph, GraphEdge, GraphNode
from src.game.domain.memory import GMLogEntry
from src.game.domain.progress import GameProgress
from src.game.runtime.turn import GraphActionTurnError, run_graph_action_turn


def _character(
    character_id: str,
    *,
    hp: int = 30,
    max_hp: int = 30,
    mp: int = 10,
    max_mp: int = 10,
) -> GraphNode:
    return GraphNode(
        id=character_id,
        type="character",
        properties={
            "name": character_id,
            "hp": hp,
            "max_hp": max_hp,
            "mp": mp,
            "max_mp": max_mp,
            "alive": hp > 0,
            "stats": {"body": 3, "agility": 2, "mind": 2, "presence": 2},
            "status": [],
            "visited_location_ids": [],
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
            "forest": GraphNode(
                id="forest",
                type="location",
                properties={"name": "광장"},
            ),
            "player_01": _character("player_01"),
            "goblin_01": _character("goblin_01", hp=24, max_hp=24),
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
            "connects_to:town:forest": GraphEdge(
                id="connects_to:town:forest",
                type="connects_to",
                from_node_id="town",
                to_node_id="forest",
            ),
        },
    )


async def _repo(tmp_path) -> LocalFsGraphRepo:
    repo = LocalFsGraphRepo(str(tmp_path))
    await repo.save_graph("game-1", _graph())
    await repo.save_progress(GameProgress(game_id="game-1", player_id="player_01"))
    return repo


class _DeltaTrackingRepo(LocalFsGraphRepo):
    def __init__(self, saves_dir: str) -> None:
        super().__init__(saves_dir)
        self.delta_calls: list[dict] = []

    async def save_graph_changes(
        self,
        game_id,
        graph,
        *,
        changed_node_ids,
        changed_edge_ids,
        removed_edge_ids,
    ):
        self.delta_calls.append(
            {
                "game_id": game_id,
                "changed_node_ids": changed_node_ids,
                "changed_edge_ids": changed_edge_ids,
                "removed_edge_ids": removed_edge_ids,
            }
        )
        await super().save_graph_changes(
            game_id,
            graph,
            changed_node_ids=changed_node_ids,
            changed_edge_ids=changed_edge_ids,
            removed_edge_ids=removed_edge_ids,
        )


async def _tracking_repo(tmp_path) -> _DeltaTrackingRepo:
    repo = _DeltaTrackingRepo(str(tmp_path))
    await repo.save_graph("game-1", _graph())
    await repo.save_progress(GameProgress(game_id="game-1", player_id="player_01"))
    return repo


class _NarrationLLM:
    def __init__(self) -> None:
        self.calls = []

    async def chat(self, messages, **kwargs):
        self.calls.append({"messages": messages, **kwargs})
        return {"answer": "칼끝이 번뜩이고, 적이 비틀거리며 길 위에 쓰러집니다."}


class _SlowNarrationLLM:
    async def chat(self, *args, **kwargs):
        await asyncio.sleep(0.2)
        return {"answer": "너무 늦게 도착한 나레이션입니다."}


class _RepeatNarrationLLM:
    def __init__(self, text: str) -> None:
        self.text = text

    async def chat(self, messages, **kwargs):
        return {"answer": self.text}


async def test_run_graph_action_turn_saves_move_and_returns_front_state(tmp_path):
    repo = await _repo(tmp_path)

    result = await run_graph_action_turn(
        repo, "game-1", Action(verb="move", to="forest")
    )
    saved_graph = await repo.load_graph("game-1")
    saved_progress = await repo.load_progress("game-1")
    saved_logs = await repo.load_log_entries("game-1")

    assert "located_at:player_01:forest" in saved_graph.edges
    assert "located_at:player_01:town" not in saved_graph.edges
    assert saved_progress.turn_count == 1
    assert saved_progress.next_log_id == 3
    assert len(saved_logs) == 2
    assert saved_logs[0].kind == "act"
    assert saved_logs[0].text == "당신은 광장으로 이동합니다."
    assert saved_logs[1].kind == "act"
    assert saved_logs[1].text == "새 의뢰가 도착합니다: 마을의 부탁."
    assert result.front_state.log == saved_logs
    assert result.front_state.place.id == "forest"
    assert result.runtime.progress.turn_count == 1


async def test_run_graph_action_turn_persists_only_touched_graph_ids(tmp_path):
    repo = await _tracking_repo(tmp_path)

    await run_graph_action_turn(repo, "game-1", Action(verb="move", to="forest"))

    assert len(repo.delta_calls) == 1
    call = repo.delta_calls[0]
    assert "player_01" in call["changed_node_ids"]
    assert "auto_quest_001" in call["changed_node_ids"]
    assert "located_at:player_01:forest" in call["changed_edge_ids"]
    assert "gives_quest:auto_giver_001:auto_quest_001" in call["changed_edge_ids"]
    assert call["removed_edge_ids"] == ["located_at:player_01:town"]


async def test_run_graph_action_turn_skips_llm_narration_for_plain_move(tmp_path):
    repo = await _repo(tmp_path)
    llm = _NarrationLLM()

    result = await run_graph_action_turn(
        repo,
        "game-1",
        Action(verb="move", to="forest"),
        llm=llm,  # type: ignore[arg-type]
    )
    saved_logs = await repo.load_log_entries("game-1")

    assert len(llm.calls) == 0
    assert [entry.kind for entry in saved_logs] == ["act", "act"]
    assert result.front_state.log == saved_logs


async def test_run_graph_action_turn_generates_offer_when_no_work_exists(tmp_path):
    repo = await _repo(tmp_path)

    result = await run_graph_action_turn(
        repo, "game-1", Action(verb="move", to="forest")
    )
    saved_graph = await repo.load_graph("game-1")
    saved_progress = await repo.load_progress("game-1")
    saved_logs = await repo.load_log_entries("game-1")

    assert "auto_quest_001" in saved_graph.nodes
    assert "title" not in saved_graph.nodes["auto_quest_001"].properties
    assert "name" not in saved_graph.nodes["auto_giver_001"].properties
    assert (
        saved_progress.runtime_content.quests["auto_quest_001"]["title"]
        == "마을의 부탁"
    )
    assert (
        saved_progress.runtime_content.characters["auto_giver_001"]["name"]
        == "마을 주민"
    )
    assert saved_graph.nodes["auto_quest_001"].properties["status"] == "pending"
    assert result.front_state.quest is None
    assert len(result.front_state.quest_offers) == 1
    assert result.front_state.quest_offers[0].id == "auto_quest_001"
    assert result.front_state.quest_offers[0].actions == ["accept"]
    assert [entry.kind for entry in saved_logs] == ["act", "act"]
    assert saved_logs[1].text == "새 의뢰가 도착합니다: 마을의 부탁."
    assert result.front_state.log == saved_logs


async def test_run_graph_action_turn_saves_attack_progress_and_front_combat(tmp_path):
    repo = await _repo(tmp_path)

    result = await run_graph_action_turn(
        repo,
        "game-1",
        Action(verb="attack", what="goblin_01"),
    )
    saved_progress = await repo.load_progress("game-1")

    assert saved_progress.graph_combat_state is not None
    assert saved_progress.graph_combat_state.round == 2
    assert result.front_state.combat is not None
    assert result.front_state.combat.round == 2


async def test_run_graph_action_turn_adds_short_gm_narration_for_combat_victory(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr("src.game.engines.graph_combat.randint", lambda _a, _b: 20)
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
                    enemy_hearts=1,
                    round=3,
                )
            }
        )
    )
    graph = await repo.load_graph("game-1")
    graph.nodes["goblin_01"].properties["hp"] = 8
    await repo.save_graph("game-1", graph)

    result = await run_graph_action_turn(
        repo,
        "game-1",
        Action(verb="attack", what="goblin_01"),
        llm=_NarrationLLM(),  # type: ignore[arg-type]
    )
    saved_logs = await repo.load_log_entries("game-1")

    assert [entry.kind for entry in saved_logs] == ["act", "act", "gm"]
    assert saved_logs[-1].text == "칼끝이 번뜩이고, 적이 비틀거리며 길 위에 쓰러집니다."
    assert result.front_state.log == saved_logs
    assert result.runtime.progress.next_log_id == saved_logs[-1].id + 1


async def test_run_graph_action_turn_logs_fled_combat_as_fled_not_victory(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr("src.game.engines.graph_combat.randint", lambda _a, _b: 20)
    repo = await _repo(tmp_path)
    llm = _NarrationLLM()
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
                    round=2,
                )
            }
        )
    )

    await run_graph_action_turn(
        repo,
        "game-1",
        Action(verb="move", how="flee"),
        llm=llm,  # type: ignore[arg-type]
    )
    saved_logs = await repo.load_log_entries("game-1")

    assert saved_logs[0].text == "당신은 전투에서 물러납니다."
    assert len(llm.calls) == 0


async def test_run_graph_action_turn_preserves_repeated_llm_narration(tmp_path):
    repo = await _repo(tmp_path)
    repeated = "테스트 가이드는 대답하지 않고 당신을 다시 봅니다."
    await repo.append_log_entries(
        "game-1",
        [GMLogEntry(id=1, kind="gm", text=repeated)],
    )
    progress = await repo.load_progress("game-1")
    await repo.save_progress(progress.model_copy(update={"next_log_id": 2}))

    await run_graph_action_turn(
        repo,
        "game-1",
        Action(verb="attack", what="goblin_01"),
        llm=_RepeatNarrationLLM(repeated),  # type: ignore[arg-type]
    )
    saved_logs = await repo.load_log_entries("game-1")

    assert [entry.kind for entry in saved_logs] == ["gm", "act", "gm"]
    assert saved_logs[-1].text == repeated


async def test_run_graph_action_turn_sends_combat_trace_to_narration(tmp_path):
    repo = await _repo(tmp_path)
    llm = _NarrationLLM()

    await run_graph_action_turn(
        repo,
        "game-1",
        Action(verb="attack", what="goblin_01"),
        llm=llm,  # type: ignore[arg-type]
    )

    call = [call for call in llm.calls if call["agent"] == "graph_narrate"][0]
    import json

    payload = json.loads(call["messages"][1]["content"])
    encoded = json.dumps(payload, ensure_ascii=False)

    assert payload["current_event"]["action"]["verb"] == "attack"
    assert payload["combat_view"]["events"]
    assert payload["scene_anchor"]["visible_names"]
    assert "combat_started" not in encoded
    assert "player_attacked" not in encoded


async def test_run_graph_action_turn_times_out_slow_narration_and_keeps_action(
    tmp_path,
    monkeypatch,
):
    import src.game.runtime.turn as turn_module

    monkeypatch.setattr(
        turn_module,
        "_GRAPH_ACTION_NARRATION_TIMEOUT_SECONDS",
        0.01,
        raising=False,
    )
    repo = await _repo(tmp_path)

    started = time.perf_counter()
    result = await run_graph_action_turn(
        repo,
        "game-1",
        Action(verb="attack", what="goblin_01"),
        llm=_SlowNarrationLLM(),  # type: ignore[arg-type]
    )
    elapsed = time.perf_counter() - started
    saved_logs = await repo.load_log_entries("game-1")

    assert elapsed < 0.15
    assert [entry.kind for entry in saved_logs] == ["act"]
    assert result.front_state.combat is not None


async def test_run_graph_action_turn_rejects_query_without_saving(tmp_path):
    repo = await _repo(tmp_path)

    with pytest.raises(GraphActionTurnError, match="read-only"):
        await run_graph_action_turn(repo, "game-1", Action(verb="query", what="status"))

    saved_graph = await repo.load_graph("game-1")
    saved_progress = await repo.load_progress("game-1")
    assert saved_graph == _graph()
    assert saved_progress.turn_count == 0
