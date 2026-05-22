import json

import pytest

from src.db.graph.local_fs import LocalFsGraphRepo
from src.game.domain.action import Action
from src.game.domain.graph import Graph, GraphEdge, GraphNode
from src.game.domain.progress import GameProgress
from src.game.rules import RULES
from src.game.runtime.flow.confirmation import run_graph_action_request
from src.game.runtime.flow.confirmation import (
    run_graph_action_request_stream,
    run_graph_confirm,
    run_graph_confirm_stream,
)
from src.game.runtime.flow.roll import (
    GraphRollExpected,
    _ResolvedGraphRoll,
    build_pending_roll,
    _strip_repeated_preroll_text,
    run_graph_preroll_stream,
    run_graph_roll,
    run_graph_roll_stream,
    start_graph_roll,
)


@pytest.fixture(autouse=True)
def _fixed_roll_dc(monkeypatch):
    monkeypatch.setenv("GRAPH_DEFAULT_ROLL_DC", "13")


class _RollStreamLLM:
    def __init__(
        self,
        narration: str = "판정의 여파가 짧게 남습니다.",
        *,
        suggestions: list[object] | None = None,
    ) -> None:
        self.narration = narration
        self.suggestions = suggestions or []
        self.calls: list[dict] = []

    async def chat_stream(
        self,
        messages,
        think=False,
        agent=None,
        temperature=None,
        use_fallback=False,
    ):
        del think, temperature, use_fallback
        self.calls.append({"agent": agent, "messages": messages})
        yield {"answer": self.narration}
        yield {
            "answer": (
                "\n---TRPG_META---\n"
                + json.dumps(
                    {"turn_summary": "", "importance": 1, "suggestions": self.suggestions},
                    ensure_ascii=False,
                )
            )
        }

    async def chat(
        self,
        messages,
        think=False,
        agent=None,
        temperature=None,
        use_fallback=False,
    ):
        del think, temperature, use_fallback
        self.calls.append({"agent": agent, "messages": messages})
        return {
            "answer": (
                f"{self.narration}\n---TRPG_META---\n"
                + json.dumps(
                    {"turn_summary": "", "importance": 1, "suggestions": self.suggestions},
                    ensure_ascii=False,
                )
            )
        }


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
            "level": 1,
            "xp_pool": 0,
            "stats": {"body": 10, "agility": 10, "mind": 10, "presence": 10},
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
                properties={"name": "Forest"},
            ),
            "player_01": _character("player_01"),
        },
        edges={
            "located_at:player_01:town": GraphEdge(
                id="located_at:player_01:town",
                type="located_at",
                from_node_id="player_01",
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


async def _add_guard_with_affinity(
    repo: LocalFsGraphRepo,
    affinity: int,
) -> None:
    graph = await repo.load_graph("game-1")
    graph.nodes["guard_01"] = _character("guard_01")
    graph.edges["located_at:guard_01:town"] = GraphEdge(
        id="located_at:guard_01:town",
        type="located_at",
        from_node_id="guard_01",
        to_node_id="town",
    )
    graph.edges["relation:guard_01:player_01"] = GraphEdge(
        id="relation:guard_01:player_01",
        type="relation",
        from_node_id="guard_01",
        to_node_id="player_01",
        properties={"affinity": affinity},
    )
    await repo.save_graph("game-1", graph)


async def _add_guard_coin(
    repo: LocalFsGraphRepo,
    *,
    affinity: int = 0,
) -> None:
    graph = await repo.load_graph("game-1")
    graph.nodes["guard_01"] = _character("guard_01")
    graph.nodes["coin_01"] = GraphNode(
        id="coin_01",
        type="item",
        properties={"name": "coin_01"},
    )
    graph.edges["located_at:guard_01:town"] = GraphEdge(
        id="located_at:guard_01:town",
        type="located_at",
        from_node_id="guard_01",
        to_node_id="town",
    )
    graph.edges["carries:guard_01:coin_01"] = GraphEdge(
        id="carries:guard_01:coin_01",
        type="carries",
        from_node_id="guard_01",
        to_node_id="coin_01",
    )
    graph.edges["relation:guard_01:player_01"] = GraphEdge(
        id="relation:guard_01:player_01",
        type="relation",
        from_node_id="guard_01",
        to_node_id="player_01",
        properties={"affinity": affinity},
    )
    await repo.save_graph("game-1", graph)


async def test_start_graph_roll_stores_pending_roll_without_gm_narration(tmp_path):
    repo = await _repo(tmp_path)

    result = await start_graph_roll(
        repo,
        "game-1",
        Action(verb="perceive", what="town"),
    )
    progress = await repo.load_progress("game-1")
    logs = await repo.load_log_entries("game-1")

    assert result.status == "roll_required"
    assert progress.pending_roll["kind"] == "perceive"
    assert progress.pending_roll["title"] == "지력 판정이 필요합니다"
    assert progress.pending_roll["body"] == (
        "당신은 눈앞의 흔적과 기척을 더 깊이 읽으려 합니다. "
        "성공하면 숨은 단서나 위험을 알아차립니다."
    )
    assert progress.pending_roll["required_roll"] == 13
    assert logs == []


async def test_graph_action_request_hasty_move_creates_pending_roll(tmp_path):
    repo = await _repo(tmp_path)

    result = await run_graph_action_request(
        repo,
        "game-1",
        Action(verb="move", to="forest", how="hasty"),
    )
    progress = await repo.load_progress("game-1")
    graph = await repo.load_graph("game-1")

    assert result.status == "roll_required"
    assert progress.pending_roll["kind"] == "move"
    assert progress.pending_roll["stat"] == "agility"
    assert graph.edges["located_at:player_01:town"].to_node_id == "town"


async def test_graph_action_request_difficult_move_creates_pending_roll(tmp_path):
    repo = await _repo(tmp_path)
    graph = await repo.load_graph("game-1")
    graph.edges["connects_to:town:forest"].properties["difficulty"] = "easy"
    await repo.save_graph("game-1", graph)

    result = await run_graph_action_request(
        repo,
        "game-1",
        Action(verb="move", to="forest"),
    )
    progress = await repo.load_progress("game-1")

    assert result.status == "roll_required"
    assert progress.pending_roll["kind"] == "move"


async def test_graph_action_request_stream_roll_streams_preroll_before_roll(tmp_path):
    repo = await _repo(tmp_path)
    graph = await repo.load_graph("game-1")
    graph.edges["connects_to:town:forest"].properties["difficulty"] = "easy"
    await repo.save_graph("game-1", graph)
    llm = _RollStreamLLM("숲길 입구의 흙이 발끝에서 살짝 밀립니다.")

    events = [
        event
        async for event in run_graph_action_request_stream(
            repo,
            "game-1",
            Action(verb="move", to="forest"),
            llm=llm,
        )
    ]
    progress = await repo.load_progress("game-1")
    logs = await repo.load_log_entries("game-1")

    assert events[0]["type"] == "result"
    assert events[-1]["type"] == "final"
    deltas = [event for event in events[1:-1] if event["type"] == "narration_delta"]
    assert len(deltas) >= 1
    assert events[0]["result"].status == "roll_required"
    assert events[-1]["result"].front_state.pending_roll.body == progress.pending_roll["body"]
    assert "".join(event["text"] for event in deltas) == llm.narration
    assert progress.pending_roll["body"] == llm.narration
    assert [entry.kind for entry in logs] == ["gm"]
    assert logs[0].text == llm.narration
    assert llm.calls[0]["agent"] == "graph_narrate"


async def test_preroll_stream_preserves_check_reason_after_body_narration(tmp_path):
    repo = await _repo(tmp_path)
    await _add_guard_with_affinity(repo, 0)
    llm = _RollStreamLLM("경비병은 답하기 전에 주변의 시선을 먼저 살핍니다.")
    reason = "경비병을 설득하려면 믿을 만한 말을 해야 합니다."

    events = [
        event
        async for event in run_graph_preroll_stream(
            llm,
            repo,
            "game-1",
            Action(verb="speak", to="guard_01", how="friendly"),
            reason=reason,
        )
    ]
    progress = await repo.load_progress("game-1")

    assert events[0]["result"].pending_roll["check_reason"] != llm.narration
    assert progress.pending_roll["body"] == llm.narration
    assert progress.pending_roll["check_reason"] == reason


def test_build_pending_roll_stores_original_action_payload():
    pending = build_pending_roll(
        _character("player_01").properties,
        Action(verb="perceive", what="town"),
    )

    assert pending["payload"] == {
        "kind": "graph_action",
        "action": {
            "verb": "perceive",
            "what": "town",
            "from": None,
            "to": None,
            "with": None,
            "how": None,
            "note": None,
        },
    }


def test_build_pending_roll_uses_normal_tier_base_dc_when_not_overridden(monkeypatch):
    monkeypatch.delenv("GRAPH_DEFAULT_ROLL_DC", raising=False)
    monkeypatch.setattr("src.game.runtime.flow.roll.pick_dc", lambda tier: 9)

    pending = build_pending_roll(
        _character("player_01").properties,
        Action(verb="perceive", what="town"),
    )

    assert pending["base_dc"] == 9
    assert pending["required_roll"] == 9


@pytest.mark.parametrize(
    ("action", "expected_stat"),
    [
        (Action(verb="speak", to="guard_01", how="friendly"), "presence"),
        (Action(verb="perceive", what="town"), "mind"),
        (Action(verb="move", to="forest"), "agility"),
        (Action(verb="use", what="healing_herb"), "mind"),
        (
            Action(
                verb="transfer",
                what="coin_01",
                from_="guard_01",
                to="player_01",
                how="steal",
            ),
            "agility",
        ),
        (
            Action(
                verb="transfer",
                what="coin_01",
                from_="player_01",
                to="guard_01",
                how="free",
            ),
            "presence",
        ),
    ],
)
def test_build_pending_roll_uses_action_specific_stat(action, expected_stat):
    pending = build_pending_roll(_character("player_01").properties, action)

    assert pending["stat"] == expected_stat


async def test_start_graph_roll_lowers_npc_check_dc_for_positive_affinity(tmp_path):
    repo = await _repo(tmp_path)
    await _add_guard_with_affinity(repo, 20)

    result = await start_graph_roll(
        repo,
        "game-1",
        Action(verb="speak", to="guard_01", how="friendly"),
    )

    assert result.pending_roll["required_roll"] == 11


async def test_start_graph_roll_raises_npc_check_dc_for_negative_affinity(tmp_path):
    repo = await _repo(tmp_path)
    await _add_guard_with_affinity(repo, -10)

    result = await start_graph_roll(
        repo,
        "game-1",
        Action(verb="speak", to="guard_01", how="friendly"),
    )

    assert result.pending_roll["required_roll"] == 14


async def test_run_graph_roll_failure_lowers_npc_affinity_and_next_dc_gets_harder(
    tmp_path,
):
    repo = await _repo(tmp_path)
    await _add_guard_with_affinity(repo, -9)
    pending = (
        await start_graph_roll(
            repo,
            "game-1",
            Action(verb="speak", to="guard_01", how="friendly"),
        )
    ).pending_roll

    result = await run_graph_roll(repo, "game-1", pending["id"], dice=12)
    graph = await repo.load_graph("game-1")
    next_pending = (
        await start_graph_roll(
            repo,
            "game-1",
            Action(verb="speak", to="guard_01", how="friendly"),
        )
    ).pending_roll

    assert result.outcome == "failure"
    assert graph.edges["relation:guard_01:player_01"].properties["affinity"] == (
        -9 + RULES.social.affinity_failure
    )
    assert next_pending["required_roll"] == 14


async def test_run_graph_roll_friendly_success_raises_npc_affinity(tmp_path):
    repo = await _repo(tmp_path)
    await _add_guard_with_affinity(repo, 0)
    pending = (
        await start_graph_roll(
            repo,
            "game-1",
            Action(verb="speak", to="guard_01", how="friendly"),
        )
    ).pending_roll

    result = await run_graph_roll(repo, "game-1", pending["id"], dice=13)
    graph = await repo.load_graph("game-1")

    assert result.outcome == "success"
    assert graph.edges["relation:guard_01:player_01"].properties["affinity"] == (
        RULES.social.affinity_success
    )


async def test_run_graph_roll_success_completes_social_check_quest(tmp_path):
    repo = await _repo(tmp_path)
    await _add_guard_with_affinity(repo, 0)
    graph = await repo.load_graph("game-1")
    graph.nodes["quest_social"] = GraphNode(
        id="quest_social",
        type="quest",
        properties={
            "name": "섬의 규칙을 듣습니다",
            "description": "흰섬은 두 번째 이름을 주지 않습니다.",
            "status": "active",
            "required": True,
            "triggers": [
                {
                    "id": "talk_guard",
                    "type": "social_check",
                    "target": "guard_01",
                }
            ],
            "triggers_met": [False],
            "rewards": {"gold": 2, "exp": 4},
        },
    )
    graph.nodes["quest_next"] = GraphNode(
        id="quest_next",
        type="quest",
        properties={
            "status": "locked",
            "required": True,
            "prerequisites": ["quest_social"],
        },
    )
    await repo.save_graph("game-1", graph)
    progress = await repo.load_progress("game-1")
    await repo.save_progress(
        progress.model_copy(update={"active_quest_id": "quest_social"})
    )
    pending = (
        await start_graph_roll(
            repo,
            "game-1",
            Action(verb="speak", to="guard_01", how="friendly"),
        )
    ).pending_roll

    result = await run_graph_roll(repo, "game-1", pending["id"], dice=13)
    logs = await repo.load_log_entries("game-1")
    saved_graph = await repo.load_graph("game-1")
    saved_progress = await repo.load_progress("game-1")
    player = saved_graph.nodes["player_01"].properties

    assert result.outcome == "success"
    assert saved_graph.nodes["quest_social"].properties["status"] == "completed"
    assert saved_graph.nodes["quest_social"].properties["triggers_met"] == [True]
    assert saved_graph.nodes["quest_next"].properties["status"] == "pending"
    assert player["gold"] == 2
    assert player["xp_pool"] == 5
    assert saved_progress.active_quest_id is None
    assert result.front_state.quest is None
    assert logs[-1].kind == "gm"
    assert logs[-1].text == "흰섬은 두 번째 이름을 주지 않습니다."


async def test_run_graph_roll_appends_completed_social_quest_text_when_llm_omits_it(
    tmp_path,
):
    repo = await _repo(tmp_path)
    await _add_guard_with_affinity(repo, 0)
    graph = await repo.load_graph("game-1")
    graph.nodes["quest_social"] = GraphNode(
        id="quest_social",
        type="quest",
        properties={
            "description": "흰섬은 두 번째 이름을 주지 않습니다.",
            "status": "active",
            "required": True,
            "triggers": [
                {
                    "id": "talk_guard",
                    "type": "social_check",
                    "target": "guard_01",
                }
            ],
            "triggers_met": [False],
        },
    )
    await repo.save_graph("game-1", graph)
    pending = (
        await start_graph_roll(
            repo,
            "game-1",
            Action(verb="speak", to="guard_01", how="friendly"),
        )
    ).pending_roll
    llm = _RollStreamLLM("그녀는 당신의 질문을 듣고 짧게 고개를 끄덕입니다.")

    await run_graph_roll(repo, "game-1", pending["id"], dice=13, llm=llm)  # type: ignore[arg-type]
    logs = await repo.load_log_entries("game-1")

    assert logs[-1].kind == "gm"
    assert logs[-1].text == (
        "그녀는 당신의 질문을 듣고 짧게 고개를 끄덕입니다.\n\n"
        "흰섬은 두 번째 이름을 주지 않습니다."
    )


async def test_run_graph_roll_removes_roll_meta_phrase_from_narration(tmp_path):
    repo = await _repo(tmp_path)
    await _add_guard_with_affinity(repo, 0)
    pending = (
        await start_graph_roll(
            repo,
            "game-1",
            Action(verb="speak", to="guard_01", how="friendly"),
        )
    ).pending_roll
    llm = _RollStreamLLM(
        "경비병은 고개를 듭니다. 매력 판정의 성공으로, 긴장이 풀립니다."
    )

    await run_graph_roll(repo, "game-1", pending["id"], dice=13, llm=llm)  # type: ignore[arg-type]
    logs = await repo.load_log_entries("game-1")

    assert logs[-1].kind == "gm"
    assert logs[-1].text == "경비병은 고개를 듭니다. 긴장이 풀립니다."


async def test_run_graph_roll_success_grants_roll_xp_once_per_award_key(tmp_path):
    repo = await _repo(tmp_path)
    pending = (
        await start_graph_roll(repo, "game-1", Action(verb="perceive", what="town"))
    ).pending_roll

    await run_graph_roll(repo, "game-1", pending["id"], dice=13)
    graph = await repo.load_graph("game-1")
    next_pending = (
        await start_graph_roll(repo, "game-1", Action(verb="perceive", what="town"))
    ).pending_roll
    await run_graph_roll(repo, "game-1", next_pending["id"], dice=13)
    graph_after_repeat = await repo.load_graph("game-1")

    assert graph.nodes["player_01"].properties["xp_pool"] == 1
    assert graph_after_repeat.nodes["player_01"].properties["xp_pool"] == 1
    assert graph_after_repeat.nodes["player_01"].properties["xp_award_keys"] == [
        "roll:perceive:town"
    ]


async def test_run_graph_roll_critical_success_grants_more_roll_xp(tmp_path):
    repo = await _repo(tmp_path)
    pending = (
        await start_graph_roll(repo, "game-1", Action(verb="perceive", what="town"))
    ).pending_roll

    await run_graph_roll(repo, "game-1", pending["id"], dice=20)
    graph = await repo.load_graph("game-1")

    assert graph.nodes["player_01"].properties["xp_pool"] == 2


async def test_run_graph_roll_failure_grants_no_roll_xp(tmp_path):
    repo = await _repo(tmp_path)
    pending = (
        await start_graph_roll(repo, "game-1", Action(verb="perceive", what="town"))
    ).pending_roll

    await run_graph_roll(repo, "game-1", pending["id"], dice=12)
    graph = await repo.load_graph("game-1")

    assert graph.nodes["player_01"].properties["xp_pool"] == 0
    assert "xp_award_keys" not in graph.nodes["player_01"].properties


async def test_graph_action_request_perceive_creates_pending_roll(tmp_path):
    repo = await _repo(tmp_path)

    result = await run_graph_action_request(
        repo,
        "game-1",
        Action(verb="perceive", what="town"),
    )
    progress = await repo.load_progress("game-1")

    assert result.status == "roll_required"
    assert progress.pending_roll["kind"] == "perceive"
    assert result.front_state.pending_roll is not None


async def test_steal_requires_confirmation_then_roll_and_failure_does_not_transfer(
    tmp_path,
):
    repo = await _repo(tmp_path)
    await _add_guard_coin(repo)

    confirmation = await run_graph_action_request(
        repo,
        "game-1",
        Action(
            verb="transfer",
            what="coin_01",
            from_="guard_01",
            to="player_01",
            how="steal",
        ),
    )
    confirmation_id = confirmation.pending_confirmation["id"]
    roll = await run_graph_confirm(repo, "game-1", confirmation_id, "confirm")
    result = await run_graph_roll(repo, "game-1", roll.pending_roll["id"], dice=12)
    graph = await repo.load_graph("game-1")

    assert confirmation.status == "confirmation_required"
    assert confirmation.pending_confirmation["kind"] == "steal"
    assert roll.status == "roll_required"
    assert roll.pending_roll["stat"] == "agility"
    assert result.outcome == "failure"
    assert "carries:guard_01:coin_01" in graph.edges
    assert "carries:player_01:coin_01" not in graph.edges
    assert graph.edges["relation:guard_01:player_01"].properties["affinity"] == (
        RULES.social.affinity_failure
    )


async def test_graph_confirm_stream_roll_streams_preroll_before_roll(tmp_path):
    repo = await _repo(tmp_path)
    await _add_guard_coin(repo)
    confirmation = await run_graph_action_request(
        repo,
        "game-1",
        Action(
            verb="transfer",
            what="coin_01",
            from_="guard_01",
            to="player_01",
            how="steal",
        ),
    )
    llm = _RollStreamLLM("경비병의 손이 주머니 근처에서 멈춥니다.")

    events = [
        event
        async for event in run_graph_confirm_stream(
            repo,
            "game-1",
            confirmation.pending_confirmation["id"],
            "confirm",
            llm=llm,
        )
    ]
    progress = await repo.load_progress("game-1")
    logs = await repo.load_log_entries("game-1")

    assert events[0]["type"] == "result"
    assert events[-1]["type"] == "final"
    deltas = [event for event in events[1:-1] if event["type"] == "narration_delta"]
    assert len(deltas) >= 1
    assert events[0]["result"].status == "roll_required"
    assert events[-1]["result"].front_state.pending_roll.body == progress.pending_roll["body"]
    assert "".join(event["text"] for event in deltas) == llm.narration
    assert progress.pending_confirmation is None
    assert progress.pending_roll["body"] == llm.narration
    assert [entry.kind for entry in logs] == ["gm"]
    assert logs[0].text == llm.narration
    assert llm.calls[0]["agent"] == "graph_narrate"


async def test_run_graph_roll_resolves_pending_roll_and_appends_roll_log(tmp_path):
    repo = await _repo(tmp_path)
    pending = (
        await start_graph_roll(repo, "game-1", Action(verb="move", to="forest"))
    ).pending_roll

    result = await run_graph_roll(repo, "game-1", pending["id"], dice=13)
    progress = await repo.load_progress("game-1")
    logs = await repo.load_log_entries("game-1")

    assert result.status == "executed"
    assert progress.pending_roll is None
    assert progress.turn_count == 2
    assert logs[0].kind == "roll"
    assert [entry.id for entry in logs] == list(range(1, len(logs) + 1))
    assert progress.next_log_id == logs[-1].id + 1
    assert logs[0].check == "민첩"
    assert logs[0].roll == 13
    assert logs[0].result == "success"
    assert result.outcome == "success"
    assert result.front_state.pending_roll is None


async def test_run_graph_roll_continues_stored_action(tmp_path):
    repo = await _repo(tmp_path)
    action = Action(verb="move", to="forest")
    pending = build_pending_roll(_character("player_01").properties, action)
    progress = await repo.load_progress("game-1")
    await repo.save_progress(progress.model_copy(update={"pending_roll": pending}))

    result = await run_graph_roll(repo, "game-1", pending["id"], dice=13)
    progress = await repo.load_progress("game-1")
    graph = await repo.load_graph("game-1")

    assert result.status == "executed"
    assert progress.pending_roll is None
    assert result.dispatch is not None
    assert result.dispatch.kind == "move"
    assert result.front_state.place.id == "forest"
    assert "located_at:player_01:forest" in graph.edges


async def test_run_graph_roll_resolves_narrative_perceive_without_dispatch(tmp_path):
    repo = await _repo(tmp_path)
    pending = (
        await start_graph_roll(repo, "game-1", Action(verb="perceive", what="town"))
    ).pending_roll

    result = await run_graph_roll(repo, "game-1", pending["id"], dice=13)
    progress = await repo.load_progress("game-1")
    logs = await repo.load_log_entries("game-1")

    assert result.status == "executed"
    assert result.outcome == "success"
    assert result.dispatch is None
    assert progress.pending_roll is None
    assert logs[0].kind == "roll"
    assert logs[0].result == "success"
    assert logs[1].kind == "gm"
    assert logs[1].outcome == "success"
    assert logs[1].text == "당신은 살핀 끝에 의미 있는 단서나 위험의 낌새를 잡아냅니다."


async def test_run_graph_roll_resolves_failed_narrative_perceive_without_dispatch(
    tmp_path,
):
    repo = await _repo(tmp_path)
    llm = _RollStreamLLM("흔적은 보이지만, 서로 이어지는 방향을 끝내 잡아내지 못합니다.")
    pending = (
        await start_graph_roll(repo, "game-1", Action(verb="perceive", what="town"))
    ).pending_roll

    result = await run_graph_roll(repo, "game-1", pending["id"], dice=12, llm=llm)  # type: ignore[arg-type]
    logs = await repo.load_log_entries("game-1")

    assert result.status == "executed"
    assert result.outcome == "failure"
    assert result.dispatch is None
    assert logs[0].kind == "roll"
    assert logs[0].result == "fail"
    assert logs[1].kind == "gm"
    assert logs[1].outcome == "failure"
    assert logs[1].text == "흔적은 보이지만, 서로 이어지는 방향을 끝내 잡아내지 못합니다."
    assert len(llm.calls) == 1
    assert llm.calls[0]["agent"] == "graph_narrate"


async def test_run_graph_roll_filters_narrative_suggestions(tmp_path):
    repo = await _repo(tmp_path)
    llm = _RollStreamLLM(
        "숲 쪽 길이 다시 눈에 들어옵니다.",
        suggestions=[
            {"label": "숲", "input_text": "Forest로 이동합니다", "intent": "move"},
            {"label": "발자국", "input_text": "발자국을 자세히 살핍니다"},
        ],
    )
    pending = (
        await start_graph_roll(repo, "game-1", Action(verb="perceive", what="town"))
    ).pending_roll

    result = await run_graph_roll(repo, "game-1", pending["id"], dice=12, llm=llm)  # type: ignore[arg-type]

    assert [suggestion.input_text for suggestion in result.suggestions] == [
        "Forest로 이동합니다"
    ]


async def test_run_graph_roll_strips_repeated_preroll_sentences(tmp_path):
    repo = await _repo(tmp_path)
    reason = (
        "흰 머리 여인의 주변을 천천히 둘러봅니다. "
        "그녀가 입은 물고기 비늘이 붙은 앞치마와 흰 머리카락의 움직임을 놓치지 않으려 합니다."
    )
    llm = _RollStreamLLM(
        reason
        + " 옷감 아래로 오래 물에 닿은 흔적이 접힌 선마다 남아 있습니다."
    )
    pending = (
        await start_graph_roll(
            repo,
            "game-1",
            Action(verb="perceive", what="town"),
            reason=reason,
        )
    ).pending_roll

    result = await run_graph_roll(repo, "game-1", pending["id"], dice=12, llm=llm)  # type: ignore[arg-type]
    logs = await repo.load_log_entries("game-1")

    assert result.status == "executed"
    assert logs[1].text == "옷감 아래로 오래 물에 닿은 흔적이 접힌 선마다 남아 있습니다."


def test_strip_repeated_preroll_text_keeps_non_repeated_narration():
    resolved = _ResolvedGraphRoll(
        runtime=None,  # type: ignore[arg-type]
        action=Action(verb="perceive", what="town"),
        pending={"body": "문틀을 살피려 합니다."},
        roll_entry=None,  # type: ignore[arg-type]
        grade="success",
        outcome="success",
        completed_quest_ids=[],
    )

    assert (
        _strip_repeated_preroll_text(resolved, "문 아래 긁힌 선이 한쪽으로만 이어집니다.")
        == "문 아래 긁힌 선이 한쪽으로만 이어집니다."
    )


async def test_run_graph_roll_stream_uses_llm_for_failed_narrative_perceive(
    tmp_path,
):
    repo = await _repo(tmp_path)
    llm = _RollStreamLLM("바닥의 흠집은 보이지만, 방향을 가늠할 만큼 이어지지 않습니다.")
    pending = (
        await start_graph_roll(repo, "game-1", Action(verb="perceive", what="town"))
    ).pending_roll

    events = [
        event
        async for event in run_graph_roll_stream(
            llm,
            repo,
            "game-1",
            pending["id"],
            dice=1,
        )
    ]
    logs = await repo.load_log_entries("game-1")

    assert events[0]["type"] == "result"
    assert events[-1]["type"] == "final"
    assert events[0]["result"].outcome == "failure"
    assert "".join(event["text"] for event in events[1:-1]) == (
        "바닥의 흠집은 보이지만, 방향을 가늠할 만큼 이어지지 않습니다."
    )
    assert [entry.kind for entry in logs] == ["roll", "gm"]
    assert logs[-1].outcome == "failure"
    assert logs[-1].text == "바닥의 흠집은 보이지만, 방향을 가늠할 만큼 이어지지 않습니다."
    assert len(llm.calls) == 1
    assert llm.calls[0]["agent"] == "graph_narrate"


async def test_run_graph_roll_logs_one_short_roll_as_fail(tmp_path):
    repo = await _repo(tmp_path)
    pending = (
        await start_graph_roll(repo, "game-1", Action(verb="move", to="forest"))
    ).pending_roll

    result = await run_graph_roll(repo, "game-1", pending["id"], dice=12)
    logs = await repo.load_log_entries("game-1")
    graph = await repo.load_graph("game-1")

    assert logs[0].kind == "roll"
    assert logs[0].margin == -1
    assert logs[0].result == "fail"
    assert result.outcome == "failure"
    assert "located_at:player_01:town" in graph.edges
    assert "located_at:player_01:forest" not in graph.edges
    assert result.dispatch is None


async def test_run_graph_roll_stream_narrates_failed_roll_without_dispatch(tmp_path):
    repo = await _repo(tmp_path)
    llm = _RollStreamLLM("발밑의 길이 선뜻 열리지 않습니다.")
    pending = (
        await start_graph_roll(repo, "game-1", Action(verb="move", to="forest"))
    ).pending_roll

    events = [
        event
        async for event in run_graph_roll_stream(
            llm,
            repo,
            "game-1",
            pending["id"],
            dice=12,
        )
    ]
    graph = await repo.load_graph("game-1")
    logs = await repo.load_log_entries("game-1")

    assert events[0]["type"] == "result"
    assert events[-1]["type"] == "final"
    assert all(event["type"] == "narration_delta" for event in events[1:-1])
    assert events[0]["result"].outcome == "failure"
    assert events[-1]["result"].outcome == "failure"
    assert "".join(event["text"] for event in events[1:-1]) == (
        "발밑의 길이 선뜻 열리지 않습니다."
    )
    assert "located_at:player_01:town" in graph.edges
    assert "located_at:player_01:forest" not in graph.edges
    assert [entry.kind for entry in logs] == ["roll", "gm"]
    assert logs[-1].text == "발밑의 길이 선뜻 열리지 않습니다."
    assert llm.calls[0]["agent"] == "graph_narrate"


async def test_run_graph_roll_stream_executes_success_action_before_result(tmp_path):
    repo = await _repo(tmp_path)
    llm = _RollStreamLLM("숲길이 눈앞으로 가까워집니다.")
    pending = (
        await start_graph_roll(repo, "game-1", Action(verb="move", to="forest"))
    ).pending_roll

    events = [
        event
        async for event in run_graph_roll_stream(
            llm,
            repo,
            "game-1",
            pending["id"],
            dice=13,
        )
    ]
    logs = await repo.load_log_entries("game-1")

    assert events[0]["type"] == "result"
    assert events[-1]["type"] == "final"
    assert all(event["type"] == "narration_delta" for event in events[1:-1])
    assert events[0]["result"].outcome == "success"
    assert events[0]["result"].front_state.place.id == "forest"
    assert events[-1]["result"].outcome == "success"
    assert [entry.kind for entry in logs] == ["roll", "act", "gm"]


async def test_run_graph_roll_requires_matching_pending_id(tmp_path):
    repo = await _repo(tmp_path)

    with pytest.raises(GraphRollExpected):
        await run_graph_roll(repo, "game-1", "missing", dice=13)


async def test_run_graph_roll_requires_stored_action_payload(tmp_path):
    repo = await _repo(tmp_path)
    progress = await repo.load_progress("game-1")
    await repo.save_progress(
        progress.model_copy(
            update={
                "pending_roll": {
                    "id": "roll_1",
                    "kind": "perceive",
                    "title": "지력 판정이 필요합니다",
                    "body": "주변을 자세히 살핍니다.",
                    "stat": "mind",
                    "stat_label": "지력",
                    "required_roll": 13,
                }
            }
        )
    )

    with pytest.raises(GraphRollExpected, match="pending graph action missing"):
        await run_graph_roll(repo, "game-1", "roll_1", dice=13)
