import asyncio
import time

import pytest

from src.db.graph.local_fs import LocalFsGraphRepo
from src.game.domain.action import Action
from src.game.domain.combat import GraphCombatState
from src.game.domain.graph import Graph, GraphEdge, GraphNode
from src.game.domain.memory import GMLogEntry
from src.game.domain.progress import GameProgress
from src.game.runtime.load import load_runtime_state
from src.game.runtime.flow.turn import (
    run_graph_action_turn,
    run_graph_action_turn_from_runtime_stream,
)


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
            "gold": 20,
            "alive": hp > 0,
            "stats": {"body": 3, "agility": 2, "mind": 2, "presence": 2},
            "status": [],
            "active_buffs": [],
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
            "loose_herb": GraphNode(
                id="loose_herb",
                type="item",
                properties={"name": "loose_herb"},
            ),
            "gift_apple": GraphNode(
                id="gift_apple",
                type="item",
                properties={"name": "gift_apple"},
            ),
            "player_gift": GraphNode(
                id="player_gift",
                type="item",
                properties={"name": "player_gift"},
            ),
            "shop_potion": GraphNode(
                id="shop_potion",
                type="item",
                properties={"name": "shop_potion", "price": 6},
            ),
            "old_coin": GraphNode(
                id="old_coin",
                type="item",
                properties={"name": "old_coin", "price": 6},
            ),
            "healing_herb": GraphNode(
                id="healing_herb",
                type="item",
                properties={
                    "name": "healing_herb",
                    "consumable": False,
                    "on_use": "test_trigger",
                },
            ),
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
            "located_at:loose_herb:town": GraphEdge(
                id="located_at:loose_herb:town",
                type="located_at",
                from_node_id="loose_herb",
                to_node_id="town",
            ),
            "carries:goblin_01:gift_apple": GraphEdge(
                id="carries:goblin_01:gift_apple",
                type="carries",
                from_node_id="goblin_01",
                to_node_id="gift_apple",
            ),
            "carries:goblin_01:shop_potion": GraphEdge(
                id="carries:goblin_01:shop_potion",
                type="carries",
                from_node_id="goblin_01",
                to_node_id="shop_potion",
            ),
            "carries:player_01:old_coin": GraphEdge(
                id="carries:player_01:old_coin",
                type="carries",
                from_node_id="player_01",
                to_node_id="old_coin",
            ),
            "carries:player_01:player_gift": GraphEdge(
                id="carries:player_01:player_gift",
                type="carries",
                from_node_id="player_01",
                to_node_id="player_gift",
            ),
            "carries:player_01:healing_herb": GraphEdge(
                id="carries:player_01:healing_herb",
                type="carries",
                from_node_id="player_01",
                to_node_id="healing_herb",
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
    def __init__(self, text: str | None = None) -> None:
        self.text = text or "칼끝이 번뜩이고, 적이 비틀거리며 길 위에 쓰러집니다."
        self.calls = []

    async def chat(self, messages, **kwargs):
        self.calls.append({"messages": messages, **kwargs})
        return {"answer": self.text}


class _SlowNarrationLLM:
    async def chat(self, *args, **kwargs):
        await asyncio.sleep(0.2)
        return {"answer": "너무 늦게 도착한 나레이션입니다."}


class _EmptyNarrationLLM:
    def __init__(self) -> None:
        self.calls = []

    async def chat(self, messages, **kwargs):
        self.calls.append({"messages": messages, **kwargs})
        return {"answer": ""}


class _RepeatNarrationLLM:
    def __init__(self, text: str) -> None:
        self.text = text
        self.calls = []

    async def chat(self, messages, **kwargs):
        self.calls.append({"messages": messages, **kwargs})
        return {"answer": self.text}


class _RepeatStreamNarrationLLM:
    def __init__(self, text: str) -> None:
        self.text = text
        self.calls = []

    async def chat_stream(self, messages, **kwargs):
        self.calls.append({"messages": messages, **kwargs})
        midpoint = max(1, len(self.text) // 2)
        for chunk in (self.text[:midpoint], self.text[midpoint:]):
            yield {"answer": chunk, "think": None}


class _PersistCheckingStreamLLM:
    def __init__(self, repo: LocalFsGraphRepo) -> None:
        self.repo = repo
        self.logs_before_narration: list[str] | None = None

    async def chat_stream(self, messages, **kwargs):
        logs = await self.repo.load_log_entries("game-1")
        self.logs_before_narration = [entry.kind for entry in logs]
        yield {"answer": "전투가 시작됩니다.", "think": None}


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
    assert saved_progress.next_log_id == 2
    assert len(saved_logs) == 1
    assert saved_logs[0].kind == "act"
    assert saved_logs[0].text == "당신은 광장으로 이동합니다."
    assert result.front_state.log == saved_logs
    assert result.front_state.place.id == "forest"
    assert result.runtime.progress.turn_count == 1
    assert result.front_state.quest_offers == []


async def test_run_graph_action_turn_persists_only_touched_graph_ids(tmp_path):
    repo = await _tracking_repo(tmp_path)

    await run_graph_action_turn(repo, "game-1", Action(verb="move", to="forest"))

    assert len(repo.delta_calls) == 1
    call = repo.delta_calls[0]
    assert "player_01" in call["changed_node_ids"]
    assert "located_at:player_01:forest" in call["changed_edge_ids"]
    assert call["removed_edge_ids"] == ["located_at:player_01:town"]


async def test_run_graph_action_turn_adds_gm_narration_for_first_visit_move(tmp_path):
    repo = await _repo(tmp_path)
    llm = _NarrationLLM()

    result = await run_graph_action_turn(
        repo,
        "game-1",
        Action(verb="move", to="forest"),
        llm=llm,  # type: ignore[arg-type]
    )
    saved_logs = await repo.load_log_entries("game-1")

    assert [call["agent"] for call in llm.calls] == ["graph_narrate"]
    assert [entry.kind for entry in saved_logs] == ["act", "gm"]
    assert saved_logs[-1].text == "칼끝이 번뜩이고, 적이 비틀거리며 길 위에 쓰러집니다."
    assert saved_logs[-1].outcome == "neutral"
    assert result.front_state.log == saved_logs


async def test_run_graph_action_turn_skips_llm_narration_for_equip(tmp_path):
    repo = await _repo(tmp_path)
    llm = _NarrationLLM()

    result = await run_graph_action_turn(
        repo,
        "game-1",
        Action(verb="transfer", what="old_coin", how="equip", to="accessory"),
        llm=llm,  # type: ignore[arg-type]
    )
    saved_logs = await repo.load_log_entries("game-1")

    assert llm.calls == []
    assert [entry.kind for entry in saved_logs] == ["act"]
    assert result.front_state.log == saved_logs


async def test_run_graph_action_turn_skips_llm_narration_for_revisited_move(tmp_path):
    repo = await _repo(tmp_path)
    graph = await repo.load_graph("game-1")
    graph.nodes["player_01"].properties["visited_location_ids"] = ["town", "forest"]
    graph.nodes["active_quest"] = GraphNode(
        id="active_quest",
        type="quest",
        properties={"status": "active"},
    )
    await repo.save_graph("game-1", graph)
    llm = _NarrationLLM()

    result = await run_graph_action_turn(
        repo,
        "game-1",
        Action(verb="move", to="forest"),
        llm=llm,  # type: ignore[arg-type]
    )
    saved_logs = await repo.load_log_entries("game-1")

    assert len(llm.calls) == 0
    assert [entry.kind for entry in saved_logs] == ["act"]
    assert result.front_state.log == saved_logs


@pytest.mark.parametrize(
    ("action", "kind"),
    [
        (Action(verb="transfer", what="loose_herb", from_="town"), "transfer"),
        (
            Action(
                verb="transfer",
                what="player_gift",
                from_="player_01",
                to="goblin_01",
            ),
            "transfer",
        ),
        (
            Action(
                verb="transfer",
                what="gift_apple",
                from_="goblin_01",
                to="player_01",
            ),
            "transfer",
        ),
        (
            Action(
                verb="transfer",
                what="shop_potion",
                from_="goblin_01",
                to="player_01",
                how="trade",
            ),
            "trade_buy",
        ),
        (
            Action(
                verb="transfer",
                what="old_coin",
                from_="player_01",
                to="goblin_01",
                how="trade",
            ),
            "trade_sell",
        ),
        (Action(verb="use", what="healing_herb"), "use"),
        (Action(verb="rest"), "rest"),
    ],
)
async def test_run_graph_action_turn_narrates_item_and_rest_actions(
    tmp_path,
    action,
    kind,
):
    repo = await _repo(tmp_path)
    llm = _NarrationLLM()

    result = await run_graph_action_turn(
        repo,
        "game-1",
        action,
        llm=llm,  # type: ignore[arg-type]
    )
    saved_logs = await repo.load_log_entries("game-1")

    assert result.dispatch.kind == kind
    assert llm.calls[-1]["agent"] == "graph_narrate"
    assert saved_logs[-1].kind == "gm"


async def test_run_graph_action_turn_labels_targetless_location_transfer_as_pickup(
    tmp_path,
):
    repo = await _repo(tmp_path)
    llm = _NarrationLLM()

    await run_graph_action_turn(
        repo,
        "game-1",
        Action(verb="transfer", what="loose_herb"),
        llm=llm,  # type: ignore[arg-type]
    )
    saved_logs = await repo.load_log_entries("game-1")

    assert saved_logs[-2].text == "당신은 loose_herb를 챙깁니다."


async def test_run_graph_action_turn_narrates_rest_encounter(tmp_path):
    repo = await _repo(tmp_path)
    graph = await repo.load_graph("game-1")
    graph.nodes["town"].properties["sleep_risk"] = "dangerous"
    graph.nodes["town"].properties["sleep_encounters"] = ["goblin_01"]
    await repo.save_graph("game-1", graph)
    llm = _NarrationLLM()

    result = await run_graph_action_turn(
        repo,
        "game-1",
        Action(verb="rest"),
        llm=llm,  # type: ignore[arg-type]
    )
    saved_logs = await repo.load_log_entries("game-1")

    assert result.dispatch.kind == "rest_encounter"
    assert llm.calls[-1]["agent"] == "graph_narrate"
    assert saved_logs[-1].kind == "gm"


async def test_run_graph_action_turn_does_not_generate_quest_offer_on_revisited_move(
    tmp_path,
):
    repo = await _repo(tmp_path)
    graph = await repo.load_graph("game-1")
    graph.nodes["player_01"].properties["visited_location_ids"] = ["town", "forest"]
    await repo.save_graph("game-1", graph)
    llm = _NarrationLLM()

    result = await run_graph_action_turn(
        repo,
        "game-1",
        Action(verb="move", to="forest"),
        llm=llm,  # type: ignore[arg-type]
    )
    saved_logs = await repo.load_log_entries("game-1")

    assert [entry.kind for entry in saved_logs] == ["act"]
    assert llm.calls == []
    assert result.front_state.quest_offers == []


async def test_run_graph_action_turn_completes_location_enter_quest_and_rewards(
    tmp_path,
):
    repo = await _repo(tmp_path)
    graph = await repo.load_graph("game-1")
    graph.nodes["quest_forest"] = GraphNode(
        id="quest_forest",
        type="quest",
        properties={
            "status": "active",
            "triggers": [
                {
                    "id": "reach_forest",
                    "type": "location_enter",
                    "target": "forest",
                }
            ],
            "triggers_met": [False],
            "rewards": {"gold": 3, "exp": 2},
        },
    )
    await repo.save_graph("game-1", graph)
    progress = await repo.load_progress("game-1")
    await repo.save_progress(
        progress.model_copy(update={"active_quest_id": "quest_forest"})
    )

    result = await run_graph_action_turn(
        repo,
        "game-1",
        Action(verb="move", to="forest"),
    )
    saved_graph = await repo.load_graph("game-1")
    saved_progress = await repo.load_progress("game-1")
    player = saved_graph.nodes["player_01"].properties

    assert saved_graph.nodes["quest_forest"].properties["status"] == "completed"
    assert saved_graph.nodes["quest_forest"].properties["triggers_met"] == [True]
    assert player["gold"] == 23
    assert player["xp_pool"] == 2
    assert saved_progress.active_quest_id is None
    assert result.front_state.quest is None


async def test_run_graph_action_turn_uses_pass_style_fallback_for_empty_narration(
    tmp_path,
):
    repo = await _repo(tmp_path)

    await run_graph_action_turn(
        repo,
        "game-1",
        Action(verb="use", what="healing_herb"),
        llm=_EmptyNarrationLLM(),  # type: ignore[arg-type]
    )
    saved_logs = await repo.load_log_entries("game-1")

    assert saved_logs[-1].kind == "gm"
    assert saved_logs[-1].text == "당신의 행동은 조용히 이어집니다."


async def test_run_graph_action_turn_stream_emits_result_before_narration(tmp_path):
    repo = await _repo(tmp_path)
    runtime = await load_runtime_state(repo, "game-1")
    llm = _PersistCheckingStreamLLM(repo)

    events = [
        event
        async for event in run_graph_action_turn_from_runtime_stream(
            repo,
            "game-1",
            runtime,
            Action(verb="attack", what="goblin_01"),
            llm=llm,  # type: ignore[arg-type]
        )
    ]
    saved_logs = await repo.load_log_entries("game-1")

    assert [event["type"] for event in events] == [
        "result",
        "narration_delta",
        "final",
    ]
    assert llm.logs_before_narration == ["act"]
    assert [entry.kind for entry in events[0]["result"].front_state.log] == ["act"]
    assert [entry.kind for entry in saved_logs] == ["act", "gm"]
    assert saved_logs[-1].text == "전투가 시작됩니다."
    assert [entry.kind for entry in events[-1]["result"].front_state.log] == [
        "act",
        "gm",
    ]


async def test_run_graph_action_turn_does_not_generate_offer_when_no_work_exists(
    tmp_path,
):
    repo = await _repo(tmp_path)

    result = await run_graph_action_turn(
        repo, "game-1", Action(verb="move", to="forest")
    )
    saved_graph = await repo.load_graph("game-1")
    saved_logs = await repo.load_log_entries("game-1")

    assert not any(node_id.startswith("auto_") for node_id in saved_graph.nodes)
    assert result.front_state.quest is None
    assert result.front_state.quest_offers == []
    assert [entry.kind for entry in saved_logs] == ["act"]
    assert result.front_state.log == saved_logs


async def test_run_graph_action_turn_saves_attack_progress_and_front_combat(tmp_path):
    repo = await _repo(tmp_path)

    result = await run_graph_action_turn(
        repo,
        "game-1",
        Action(verb="attack", what="goblin_01"),
    )
    saved_progress = await repo.load_progress("game-1")
    saved_logs = await repo.load_log_entries("game-1")

    assert saved_progress.graph_combat_state is not None
    assert saved_progress.graph_combat_state.round == 1
    assert saved_progress.graph_combat_state.last_roll is None
    assert saved_logs[0].text == (
        "goblin_01가 정면을 막아서고, 당신은 발을 낮게 깔아 싸움의 중심을 잡습니다."
    )
    assert result.front_state.combat is not None
    assert result.front_state.combat.round == 1
    assert result.front_state.combat.last_roll is None


async def test_run_graph_action_turn_adds_short_gm_narration_for_combat_victory(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr("src.game.engines.graph.combat.randint", lambda _a, _b: 20)
    repo = await _repo(tmp_path)
    progress = await repo.load_progress("game-1")
    await repo.save_progress(
        progress.model_copy(
            update={
                "graph_combat_state": GraphCombatState(
                    location_id="town",
                    player_id="player_01",
                    active_enemy_id="goblin_01",
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

    assert [entry.kind for entry in saved_logs] == ["act", "gm"]
    assert saved_logs[-1].text == "칼끝이 번뜩이고, 적이 비틀거리며 길 위에 쓰러집니다."
    assert saved_logs[-1].outcome == "success"
    assert result.front_state.log == saved_logs
    assert result.runtime.progress.next_log_id == saved_logs[-1].id + 1


async def test_run_graph_action_turn_escapes_combat_on_success(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr("src.game.engines.graph.combat.randint", lambda _a, _b: 20)
    repo = await _repo(tmp_path)
    llm = _NarrationLLM()
    progress = await repo.load_progress("game-1")
    await repo.save_progress(
        progress.model_copy(
            update={
                "graph_combat_state": GraphCombatState(
                    location_id="town",
                    player_id="player_01",
                    active_enemy_id="goblin_01",
                    enemy_ids=["goblin_01"],
                    participant_ids=["player_01", "goblin_01"],
                    sides={"player_01": "player", "goblin_01": "enemy"},
                    round=2,
                )
            }
        )
    )

    result = await run_graph_action_turn(
        repo,
        "game-1",
        Action(verb="move", how="flee"),
        llm=llm,  # type: ignore[arg-type]
    )
    saved_logs = await repo.load_log_entries("game-1")

    assert result.runtime.progress.graph_combat_state is None
    assert saved_logs[-1].text == "칼끝이 번뜩이고, 적이 비틀거리며 길 위에 쓰러집니다."
    assert saved_logs[-1].outcome == "neutral"
    assert [entry.kind for entry in saved_logs] == ["act", "gm"]
    assert len(llm.calls) == 1
    assert llm.calls[0]["agent"] == "combat_narrate"


async def test_run_graph_action_turn_preserves_repeated_llm_narration(tmp_path):
    repo = await _repo(tmp_path)
    repeated = "테스트 가이드는 대답하지 않고 당신을 다시 봅니다."
    await repo.append_log_entries(
        "game-1",
        [GMLogEntry(id=1, kind="gm", text=repeated)],
    )
    progress = await repo.load_progress("game-1")
    await repo.save_progress(progress.model_copy(update={"next_log_id": 2}))
    llm = _RepeatNarrationLLM(repeated)

    await run_graph_action_turn(
        repo,
        "game-1",
        Action(verb="attack", what="goblin_01"),
        llm=llm,  # type: ignore[arg-type]
    )
    saved_logs = await repo.load_log_entries("game-1")

    assert [entry.kind for entry in saved_logs] == ["gm", "act", "gm"]
    assert saved_logs[-1].text == (
        "대치가 이어지고, 서로의 다음 움직임이 아직 정해지지 않습니다."
    )
    assert saved_logs[-1].outcome == "neutral"
    import json

    payload = json.loads(llm.calls[0]["messages"][1]["content"])
    assert payload["reference_context"]["recent_narration"] == [
        {"text": repeated},
    ]


async def test_run_graph_action_turn_uses_llm_for_combat_failure_narration(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr("src.game.engines.graph.combat.randint", lambda _a, _b: 1)
    repo = await _repo(tmp_path)
    progress = await repo.load_progress("game-1")
    await repo.save_progress(
        progress.model_copy(
            update={
                "graph_combat_state": GraphCombatState(
                    location_id="town",
                    player_id="player_01",
                    active_enemy_id="goblin_01",
                    enemy_ids=["goblin_01"],
                    participant_ids=["player_01", "goblin_01"],
                    sides={"player_01": "player", "goblin_01": "enemy"},
                    round=2,
                )
            }
        )
    )
    llm = _NarrationLLM("상대가 먼저 각도를 지우고, 당신의 공격선은 짧게 빗나갑니다.")

    await run_graph_action_turn(
        repo,
        "game-1",
        Action(verb="attack", what="goblin_01", how="attack"),
        llm=llm,  # type: ignore[arg-type]
    )
    saved_logs = await repo.load_log_entries("game-1")

    assert saved_logs[-1].text == "상대가 먼저 각도를 지우고, 당신의 공격선은 짧게 빗나갑니다."
    assert saved_logs[-1].outcome == "failure"
    assert len(llm.calls) == 1
    assert llm.calls[0]["agent"] == "combat_narrate"


async def test_run_graph_action_turn_stream_persists_streamed_repeated_narration(
    tmp_path,
):
    repo = await _repo(tmp_path)
    repeated = "테스트 가이드는 대답하지 않고 당신을 다시 봅니다."
    await repo.append_log_entries(
        "game-1",
        [GMLogEntry(id=1, kind="gm", text=repeated)],
    )
    progress = await repo.load_progress("game-1")
    await repo.save_progress(progress.model_copy(update={"next_log_id": 2}))
    runtime = await load_runtime_state(repo, "game-1")

    events = [
        event
        async for event in run_graph_action_turn_from_runtime_stream(
            repo,
            "game-1",
            runtime,
            Action(verb="attack", what="goblin_01"),
            llm=_RepeatStreamNarrationLLM(repeated),  # type: ignore[arg-type]
        )
    ]
    saved_logs = await repo.load_log_entries("game-1")
    streamed = "".join(
        event["text"] for event in events if event["type"] == "narration_delta"
    )

    assert streamed == repeated
    assert saved_logs[-1].kind == "gm"
    assert saved_logs[-1].text == repeated
    assert events[-1]["result"].front_state.log[-1].text == repeated


async def test_run_graph_action_turn_stream_uses_llm_for_combat_failure_narration(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr("src.game.engines.graph.combat.randint", lambda _a, _b: 1)
    repo = await _repo(tmp_path)
    progress = await repo.load_progress("game-1")
    await repo.save_progress(
        progress.model_copy(
            update={
                "graph_combat_state": GraphCombatState(
                    location_id="town",
                    player_id="player_01",
                    active_enemy_id="goblin_01",
                    enemy_ids=["goblin_01"],
                    participant_ids=["player_01", "goblin_01"],
                    sides={"player_01": "player", "goblin_01": "enemy"},
                    round=2,
                )
            }
        )
    )
    runtime = await load_runtime_state(repo, "game-1")

    llm = _RepeatStreamNarrationLLM(
        "발을 빼려는 순간 상대가 간격을 좁히고, 당신은 다시 선 안에 붙잡힙니다."
    )
    events = [
        event
        async for event in run_graph_action_turn_from_runtime_stream(
            repo,
            "game-1",
            runtime,
            Action(verb="move", how="flee"),
            llm=llm,  # type: ignore[arg-type]
        )
    ]
    saved_logs = await repo.load_log_entries("game-1")
    streamed = "".join(
        event["text"] for event in events if event["type"] == "narration_delta"
    )

    assert streamed == "발을 빼려는 순간 상대가 간격을 좁히고, 당신은 다시 선 안에 붙잡힙니다."
    assert saved_logs[-1].text == streamed
    assert saved_logs[-1].outcome == "failure"
    assert len(llm.calls) == 1


async def test_run_graph_action_turn_sends_combat_trace_to_narration(tmp_path):
    repo = await _repo(tmp_path)
    llm = _NarrationLLM()

    await run_graph_action_turn(
        repo,
        "game-1",
        Action(verb="attack", what="goblin_01"),
        llm=llm,  # type: ignore[arg-type]
    )

    call = [call for call in llm.calls if call["agent"] == "combat_narrate"][0]
    import json

    payload = json.loads(call["messages"][1]["content"])
    encoded = json.dumps(payload, ensure_ascii=False)

    assert payload["engine_event"]["action"]["verb"] == "attack"
    assert payload["combat_view"]["events"]
    assert payload["scene_state"]["scene_anchor"]["visible_names"]
    assert "combat_started" not in encoded
    assert "player_attack_success" not in encoded


async def test_run_graph_action_turn_times_out_slow_narration_and_keeps_action(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv("GRAPH_ACTION_NARRATION_TIMEOUT_S", "0.01")
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
    assert [entry.kind for entry in saved_logs] == ["act", "gm"]
    assert saved_logs[-1].text == "당신의 행동은 조용히 이어집니다."
    assert result.front_state.combat is not None
