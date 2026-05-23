import json

import pytest

from src.db.graph.local_fs import LocalFsGraphRepo
from src.game.domain.action import Action
from src.game.domain.graph import Graph, GraphEdge, GraphNode
from src.game.domain.progress import GameProgress
from src.game.runtime.flow.confirmation import (
    GraphConfirmationActive,
    run_graph_action_request,
    run_graph_confirm,
)


class _NarrationLLM:
    def __init__(self, suggestions: list[object]) -> None:
        self.suggestions = suggestions

    async def chat(
        self,
        messages,
        think=False,
        agent=None,
        temperature=None,
        use_fallback=False,
    ):
        del messages, think, agent, temperature, use_fallback
        return {
            "answer": "\n".join(
                [
                    "의뢰 상태가 바뀝니다.",
                    "---TRPG_META---",
                    json.dumps(
                        {
                            "turn_summary": "",
                            "importance": 1,
                            "suggestions": self.suggestions,
                        },
                        ensure_ascii=False,
                    ),
                ]
            )
        }


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
    assert "싸움의 중심을 잡습니다" in saved_logs[0].text
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

    assert saved_logs[0].text == (
        "고블린 약탈자가 정면을 막아서고, 당신은 자세를 낮춰 싸움의 중심을 잡습니다."
    )


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
    assert "싸움의 중심을 잡습니다" in saved_logs[0].text


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


async def test_confirm_quest_accept_filters_impossible_quest_suggestions(tmp_path):
    repo = await _repo(tmp_path)
    confirmation = await run_graph_action_request(
        repo,
        "game-1",
        Action(verb="transfer", what="quest_01", how="accept"),
    )
    llm = _NarrationLLM(
        [
            {
                "label": "의뢰 수락",
                "input_text": "첫 의뢰를 수락합니다",
                "intent": "quest",
                "action": None,
            },
            {
                "label": "의뢰 포기",
                "input_text": "첫 의뢰를 포기합니다",
                "intent": "quest",
                "action": None,
            },
        ]
    )

    result = await run_graph_confirm(
        repo,
        "game-1",
        confirmation.pending_confirmation["id"],
        "confirm",
        llm=llm,
    )

    assert result.front_state.quest is not None
    assert result.front_state.quest.actions == ["abandon"]
    assert [suggestion.input_text for suggestion in result.suggestions] == [
        "첫 의뢰를 포기합니다"
    ]


async def test_one_way_unlocked_move_requires_confirmation(tmp_path):
    repo = await _repo(tmp_path)
    graph = await repo.load_graph("game-1")
    graph.nodes["town"].properties["name"] = "안개 부두"
    graph.nodes["red_square"] = GraphNode(
        id="red_square",
        type="location",
        properties={"name": "붉은 광장"},
    )
    graph.nodes["fog_depart"] = GraphNode(
        id="fog_depart",
        type="quest",
        properties={"title": "첫 출항", "status": "completed"},
    )
    graph.edges["connects_to:town:red_square"] = GraphEdge(
        id="connects_to:town:red_square",
        type="connects_to",
        from_node_id="town",
        to_node_id="red_square",
        properties={"requires_quest": "fog_depart"},
    )
    await repo.save_graph("game-1", graph)

    result = await run_graph_action_request(
        repo,
        "game-1",
        Action(verb="move", to="red_square"),
    )
    saved_graph = await repo.load_graph("game-1")
    pending = (await repo.load_progress("game-1")).pending_confirmation

    assert result.status == "confirmation_required"
    assert pending["kind"] == "important_move"
    assert result.front_state.pending_confirmation is not None
    assert result.front_state.pending_confirmation.title == "이동을 확정하시겠습니까?"
    assert (
        result.front_state.pending_confirmation.body
        == "붉은 광장으로 이동하면 안개 부두로 돌아올 수 없습니다."
    )
    assert result.front_state.pending_confirmation.confirm_label == "이동"
    assert "located_at:player_01:town" in saved_graph.edges
    assert "located_at:player_01:red_square" not in saved_graph.edges


async def test_bidirectional_unlocked_move_does_not_require_confirmation(tmp_path):
    repo = await _repo(tmp_path)
    graph = await repo.load_graph("game-1")
    graph.nodes["red_square"] = GraphNode(
        id="red_square",
        type="location",
        properties={"name": "붉은 광장"},
    )
    graph.nodes["fog_depart"] = GraphNode(
        id="fog_depart",
        type="quest",
        properties={"title": "첫 출항", "status": "completed"},
    )
    graph.edges["connects_to:town:red_square"] = GraphEdge(
        id="connects_to:town:red_square",
        type="connects_to",
        from_node_id="town",
        to_node_id="red_square",
        properties={"requires_quest": "fog_depart"},
    )
    graph.edges["connects_to:red_square:town"] = GraphEdge(
        id="connects_to:red_square:town",
        type="connects_to",
        from_node_id="red_square",
        to_node_id="town",
    )
    await repo.save_graph("game-1", graph)

    result = await run_graph_action_request(
        repo,
        "game-1",
        Action(verb="move", to="red_square"),
    )

    assert result.status == "executed"
    assert (await repo.load_progress("game-1")).pending_confirmation is None


async def test_confirm_quest_abandon_filters_impossible_quest_suggestions(tmp_path):
    repo = await _repo(tmp_path)
    graph = await repo.load_graph("game-1")
    graph.nodes["quest_01"].properties["status"] = "active"
    await repo.save_graph("game-1", graph)
    progress = await repo.load_progress("game-1")
    await repo.save_progress(progress.model_copy(update={"active_quest_id": "quest_01"}))
    confirmation = await run_graph_action_request(
        repo,
        "game-1",
        Action(verb="transfer", what="quest_01", how="abandon"),
    )
    llm = _NarrationLLM(
        [
            {
                "label": "의뢰 포기",
                "input_text": "첫 의뢰를 포기합니다",
                "intent": "quest",
                "action": None,
            },
            {
                "label": "주변 확인",
                "input_text": "주변을 확인합니다",
                "intent": "inspect",
                "action": None,
            },
        ]
    )

    result = await run_graph_confirm(
        repo,
        "game-1",
        confirmation.pending_confirmation["id"],
        "confirm",
        llm=llm,
    )

    assert result.front_state.quest is None
    assert result.front_state.quest_offers == []
    assert [suggestion.input_text for suggestion in result.suggestions] == [
        "주변을 확인합니다"
    ]
