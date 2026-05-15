import pytest

from src.db.graph_local_fs import LocalFsGraphRepo
from src.game.domain.action import Action
from src.game.domain.graph import Graph, GraphEdge, GraphNode
from src.game.domain.progress import GameProgress
from src.game.runtime.flow.confirmation import (
    GraphConfirmationActive,
    run_graph_action_request,
    run_graph_confirm,
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
            "player_01": _character("player_01"),
            "goblin_01": _character("goblin_01", hp=24, max_hp=24),
            "goblin_named": GraphNode(
                id="goblin_named",
                type="character",
                properties={
                    **_character("goblin_named", hp=24, max_hp=24).properties,
                    "name": "고블린 약탈자",
                },
            ),
            "quest_01": GraphNode(
                id="quest_01",
                type="quest",
                properties={"title": "첫 의뢰", "status": "pending"},
            ),
            "training_strike": GraphNode(
                id="training_strike",
                type="skill",
                properties={
                    "name": "훈련 일격",
                    "kind": "attack",
                    "mp_cost": 2,
                    "power": 40,
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
            "located_at:goblin_named:town": GraphEdge(
                id="located_at:goblin_named:town",
                type="located_at",
                from_node_id="goblin_named",
                to_node_id="town",
            ),
            "knows_skill:player_01:training_strike": GraphEdge(
                id="knows_skill:player_01:training_strike",
                type="knows_skill",
                from_node_id="player_01",
                to_node_id="training_strike",
            ),
        },
    )


async def _repo(tmp_path) -> LocalFsGraphRepo:
    repo = LocalFsGraphRepo(str(tmp_path))
    await repo.save_graph("game-1", _graph())
    await repo.save_progress(GameProgress(game_id="game-1", player_id="player_01"))
    return repo


async def test_attack_start_stores_confirmation_without_starting_combat(tmp_path):
    repo = await _repo(tmp_path)

    result = await run_graph_action_request(
        repo,
        "game-1",
        Action(verb="attack", what="goblin_01"),
    )
    saved_progress = await repo.load_progress("game-1")

    assert result.status == "confirmation_required"
    assert saved_progress.pending_confirmation["kind"] == "attack_start"
    assert saved_progress.pending_confirmation["payload"]["kind"] == "graph_action"
    assert saved_progress.graph_combat_state is None
    assert saved_progress.turn_count == 0


async def test_attack_start_confirmation_uses_korean_object_particle(tmp_path):
    repo = await _repo(tmp_path)

    result = await run_graph_action_request(
        repo,
        "game-1",
        Action(verb="attack", what="goblin_named"),
    )

    assert result.front_state.pending_confirmation is not None
    assert (
        result.front_state.pending_confirmation.body
        == "고블린 약탈자를 공격해 전투를 시작합니다."
    )


async def test_attack_start_uses_live_target_from_multiple_candidates(tmp_path):
    repo = await _repo(tmp_path)
    graph = await repo.load_graph("game-1")
    graph.nodes["goblin_01"].properties["hp"] = 0
    graph.nodes["goblin_01"].properties["alive"] = False
    graph.nodes["goblin_01"].properties["status"] = ["dead"]
    graph.nodes["goblin_named"].properties["name"] = "고블린"
    await repo.save_graph("game-1", graph)

    await run_graph_action_request(
        repo,
        "game-1",
        Action(verb="attack", what=["goblin_01", "goblin_named"]),
    )
    pending = (await repo.load_progress("game-1")).pending_confirmation

    assert pending["target_label"] == "고블린"
    assert pending["payload"]["action"]["what"] == ["goblin_named"]


async def test_action_request_is_blocked_while_confirmation_is_pending(tmp_path):
    repo = await _repo(tmp_path)
    await run_graph_action_request(
        repo,
        "game-1",
        Action(verb="attack", what="goblin_01"),
    )

    with pytest.raises(GraphConfirmationActive):
        await run_graph_action_request(
            repo,
            "game-1",
            Action(verb="pass"),
        )


async def test_confirm_cancel_clears_pending_without_mutating_graph(tmp_path):
    repo = await _repo(tmp_path)
    await run_graph_action_request(
        repo,
        "game-1",
        Action(verb="attack", what="goblin_01"),
    )
    pending = (await repo.load_progress("game-1")).pending_confirmation

    result = await run_graph_confirm(repo, "game-1", pending["id"], "cancel")
    saved_graph = await repo.load_graph("game-1")
    saved_progress = await repo.load_progress("game-1")

    assert result.status == "cancelled"
    assert saved_graph == _graph()
    assert saved_progress.pending_confirmation is None
    assert saved_progress.graph_combat_state is None
    assert saved_progress.turn_count == 0


async def test_confirm_attack_executes_stored_action(tmp_path):
    repo = await _repo(tmp_path)
    await run_graph_action_request(
        repo,
        "game-1",
        Action(verb="attack", what="goblin_01"),
    )
    pending = (await repo.load_progress("game-1")).pending_confirmation

    result = await run_graph_confirm(repo, "game-1", pending["id"], "confirm")
    saved_progress = await repo.load_progress("game-1")
    saved_logs = await repo.load_log_entries("game-1")

    assert result.status == "executed"
    assert saved_progress.pending_confirmation is None
    assert saved_progress.graph_combat_state is not None
    assert saved_progress.turn_count == 1
    assert len(saved_logs) == 1
    assert saved_logs[0].kind == "act"
    assert "전투를 시작합니다" in saved_logs[0].text
    assert result.front_state.log == saved_logs


async def test_confirm_attack_log_uses_korean_object_particle(tmp_path):
    repo = await _repo(tmp_path)
    await run_graph_action_request(
        repo,
        "game-1",
        Action(verb="attack", what="goblin_named"),
    )
    pending = (await repo.load_progress("game-1")).pending_confirmation

    await run_graph_confirm(repo, "game-1", pending["id"], "confirm")
    saved_logs = await repo.load_log_entries("game-1")

    assert saved_logs[0].text == "당신은 고블린 약탈자를 공격해 전투를 시작합니다."


async def test_confirm_skill_attack_starts_combat_without_spending_mp(tmp_path, monkeypatch):
    monkeypatch.setattr("src.game.engines.graph.combat.randint", lambda _a, _b: 20)
    repo = await _repo(tmp_path)
    await run_graph_action_request(
        repo,
        "game-1",
        Action(verb="attack", what="goblin_01", with_="training_strike"),
    )
    pending = (await repo.load_progress("game-1")).pending_confirmation

    result = await run_graph_confirm(repo, "game-1", pending["id"], "confirm")
    saved_progress = await repo.load_progress("game-1")
    saved_graph = await repo.load_graph("game-1")
    saved_logs = await repo.load_log_entries("game-1")

    assert result.status == "executed"
    assert saved_progress.graph_combat_state is not None
    assert saved_progress.graph_combat_state.enemy_hearts == 3
    assert saved_progress.graph_combat_state.last_roll is None
    assert saved_graph.nodes["player_01"].properties["mp"] == 10
    assert saved_graph.nodes["goblin_01"].properties["status"] == []
    assert "훈련 일격" not in saved_logs[0].text
    assert "MP 2" not in saved_logs[0].text
    assert "전투를 시작합니다" in saved_logs[0].text


async def test_confirm_quest_accept_executes_stored_action(tmp_path):
    repo = await _repo(tmp_path)

    result = await run_graph_action_request(
        repo,
        "game-1",
        Action(verb="transfer", what="quest_01", how="accept"),
    )
    pending = (await repo.load_progress("game-1")).pending_confirmation
    graph_before_confirm = await repo.load_graph("game-1")

    assert result.status == "confirmation_required"
    assert pending["kind"] == "quest_accept"
    assert graph_before_confirm.nodes["quest_01"].properties["status"] == "pending"

    await run_graph_confirm(repo, "game-1", pending["id"], "confirm")
    saved_graph = await repo.load_graph("game-1")
    saved_progress = await repo.load_progress("game-1")

    assert saved_graph.nodes["quest_01"].properties["status"] == "active"
    assert saved_progress.pending_confirmation is None
    assert saved_progress.turn_count == 1
