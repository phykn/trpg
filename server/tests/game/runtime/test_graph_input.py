import json
import asyncio

import httpx
import pytest
from openai import RateLimitError

from src.db.graph.local_fs import LocalFsGraphRepo
from src.game.domain.action import Action
from src.game.domain.combat import GraphCombatState
from src.game.domain.graph import Graph, GraphEdge, GraphNode
from src.game.domain.memory import ExchangePair, GMLogEntry, TurnLogEntry
from src.game.domain.progress import GameProgress
from src.game.runtime.flow.confirmation import GraphConfirmationActive
from src.game.runtime.flow.input import (
    run_graph_input_turn,
    run_graph_input_turn_stream,
)
from src.game.runtime.flow.roll import build_pending_roll, run_graph_preroll_stream


@pytest.fixture(autouse=True)
def _fixed_roll_dc(monkeypatch):
    monkeypatch.setenv("GRAPH_DEFAULT_ROLL_DC", "13")


class _FakeLLM:
    def __init__(
        self,
        payload: dict,
        *,
        narration: str = "상대는 당신의 말을 듣고 잠시 생각에 잠깁니다.",
        turn_summary: str = "",
        importance: int = 1,
        suggestions: list[object] | None = None,
        ui_cues: list[object] | None = None,
    ) -> None:
        self.payload = payload
        self.narration = narration
        self.turn_summary = turn_summary
        self.importance = importance
        self.suggestions = suggestions or []
        self.ui_cues = ui_cues or []
        self.calls = []

    async def chat(
        self,
        messages,
        think=False,
        agent=None,
        temperature=None,
        use_fallback=False,
    ):
        self.calls.append(
            {"messages": messages, "agent": agent, "temperature": temperature}
        )
        if agent in {"graph_narrate", "combat_narrate"}:
            return {"answer": self._narration_answer(), "think": ""}
        return {"answer": json.dumps(self.payload, ensure_ascii=False), "think": ""}

    async def chat_stream(
        self,
        messages,
        think=False,
        agent=None,
        temperature=None,
        use_fallback=False,
    ):
        self.calls.append(
            {"messages": messages, "agent": agent, "temperature": temperature}
        )
        if agent in {"graph_narrate", "combat_narrate"}:
            answer = self._narration_answer()
            midpoint = max(1, len(answer) // 2)
            for chunk in (answer[:midpoint], answer[midpoint:]):
                yield {"answer": chunk, "think": None}
            return
        yield {
            "answer": json.dumps(self.payload, ensure_ascii=False),
            "think": None,
        }

    def _narration_answer(self) -> str:
        if (
            not self.turn_summary
            and not self.suggestions
            and not self.ui_cues
            and self.importance == 1
        ):
            return self.narration
        return "\n".join(
            [
                self.narration,
                "---TRPG_META---",
                json.dumps(
                    {
                        "turn_summary": self.turn_summary,
                        "importance": self.importance,
                        "suggestions": self.suggestions,
                        "ui_cues": self.ui_cues,
                    },
                    ensure_ascii=False,
                ),
            ]
        )


class _SlowGraphNarrateLLM(_FakeLLM):
    async def chat(
        self,
        messages,
        think=False,
        agent=None,
        temperature=None,
        use_fallback=False,
    ):
        if agent == "graph_narrate":
            await asyncio.sleep(0.2)
            return {"answer": "너무 늦게 도착한 나레이션입니다.", "think": ""}
        return await super().chat(
            messages,
            think=think,
            agent=agent,
            temperature=temperature,
            use_fallback=use_fallback,
        )


def _rate_limit_error(message: str = "quota exceeded") -> RateLimitError:
    response = httpx.Response(
        status_code=429, request=httpx.Request("POST", "http://x")
    )
    return RateLimitError(message, response=response, body=None)


class _RateLimitedGraphNarrateLLM(_FakeLLM):
    async def chat(
        self,
        messages,
        think=False,
        agent=None,
        temperature=None,
        use_fallback=False,
    ):
        if agent == "graph_narrate":
            raise _rate_limit_error()
        return await super().chat(
            messages,
            think=think,
            agent=agent,
            temperature=temperature,
            use_fallback=use_fallback,
        )


class _TrackingGraphRepo(LocalFsGraphRepo):
    def __init__(self, saves_dir: str) -> None:
        super().__init__(saves_dir)
        self.graph_change_saves = []

    async def save_graph_changes(
        self,
        game_id: str,
        graph: Graph,
        *,
        changed_node_ids: list[str],
        changed_edge_ids: list[str],
        removed_edge_ids: list[str],
    ) -> None:
        self.graph_change_saves.append(
            {
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
                properties={"name": "광장"},
            ),
            "player_01": _character("player_01"),
            "goblin_01": _character("goblin_01"),
            "supply_token": GraphNode(
                id="supply_token",
                type="item",
                properties={"name": "보급 표식"},
            ),
            "healing_herb": GraphNode(
                id="healing_herb",
                type="item",
                properties={
                    "name": "회복 약초",
                    "consumable": True,
                    "effect": "heal",
                    "amount": 5,
                },
            ),
            "mana_vial": GraphNode(
                id="mana_vial",
                type="item",
                properties={
                    "name": "마나 시약",
                    "consumable": True,
                    "effect": "mp_restore",
                    "amount": 5,
                },
            ),
            "heal": GraphNode(
                id="heal",
                type="effect",
                properties={"kind": "heal"},
            ),
            "mp_restore": GraphNode(
                id="mp_restore",
                type="effect",
                properties={"kind": "mp_restore"},
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
            "connects_to:town:forest": GraphEdge(
                id="connects_to:town:forest",
                type="connects_to",
                from_node_id="town",
                to_node_id="forest",
            ),
            "located_at:supply_token:town": GraphEdge(
                id="located_at:supply_token:town",
                type="located_at",
                from_node_id="supply_token",
                to_node_id="town",
            ),
            "carries:player_01:healing_herb": GraphEdge(
                id="carries:player_01:healing_herb",
                type="carries",
                from_node_id="player_01",
                to_node_id="healing_herb",
            ),
            "carries:player_01:mana_vial": GraphEdge(
                id="carries:player_01:mana_vial",
                type="carries",
                from_node_id="player_01",
                to_node_id="mana_vial",
            ),
        },
    )


async def _repo(tmp_path) -> LocalFsGraphRepo:
    repo = LocalFsGraphRepo(str(tmp_path))
    await repo.save_graph("game-1", _graph())
    await repo.save_progress(GameProgress(game_id="game-1", player_id="player_01"))
    return repo


async def _repo_with_trade_fixture(tmp_path) -> LocalFsGraphRepo:
    repo = await _repo(tmp_path)
    graph = await repo.load_graph("game-1")
    graph.nodes["player_01"].properties["gold"] = 2
    graph.nodes["goblin_01"].properties["gold"] = 1
    graph.nodes["potion"] = GraphNode(
        id="potion",
        type="item",
        properties={"name": "회복 물약", "price": 6},
    )
    graph.nodes["gem"] = GraphNode(
        id="gem",
        type="item",
        properties={"name": "보석", "price": 20},
    )
    graph.nodes["dagger"] = GraphNode(
        id="dagger",
        type="item",
        properties={"name": "단검", "price": 4},
    )
    graph.edges["carries:goblin_01:potion"] = GraphEdge(
        id="carries:goblin_01:potion",
        type="carries",
        from_node_id="goblin_01",
        to_node_id="potion",
    )
    graph.edges["carries:player_01:gem"] = GraphEdge(
        id="carries:player_01:gem",
        type="carries",
        from_node_id="player_01",
        to_node_id="gem",
    )
    graph.edges["equips:player_01:dagger"] = GraphEdge(
        id="equips:player_01:dagger",
        type="equips",
        from_node_id="player_01",
        to_node_id="dagger",
        properties={"slot": "weapon"},
    )
    await repo.save_graph("game-1", graph)
    return repo


async def test_graph_input_pending_confirmation_blocks_before_classify_or_log(tmp_path):
    repo = await _repo(tmp_path)
    progress = await repo.load_progress("game-1")
    await repo.save_progress(
        progress.model_copy(
            update={
                "pending_confirmation": {
                    "id": "confirm_1",
                    "kind": "attack_start",
                    "title": "전투를 시작하시겠습니까?",
                    "body": "goblin_01을 공격해 전투를 시작합니다.",
                    "confirm_label": "공격합니다",
                    "cancel_label": "취소",
                    "target_label": "goblin_01",
                    "payload": {
                        "kind": "graph_action",
                        "action": Action(
                            verb="attack",
                            what="goblin_01",
                        ).model_dump(mode="json", by_alias=True),
                    },
                }
            }
        )
    )
    llm = _FakeLLM({"actions": [{"verb": "attack", "what": "goblin_01"}]})

    with pytest.raises(GraphConfirmationActive, match="pending_confirmation"):
        await run_graph_input_turn(llm, repo, "game-1", "고블린을 공격한다")

    assert llm.calls == []
    assert await repo.load_log_entries("game-1") == []


async def test_graph_input_pending_roll_blocks_before_classify_or_log(tmp_path):
    repo = await _repo(tmp_path)
    progress = await repo.load_progress("game-1")
    pending_roll = build_pending_roll(
        _character("player_01").properties,
        Action(verb="perceive", what="town"),
    )
    await repo.save_progress(progress.model_copy(update={"pending_roll": pending_roll}))
    llm = _FakeLLM({"actions": [{"verb": "attack", "what": "goblin_01"}]})

    with pytest.raises(GraphConfirmationActive, match="pending_roll"):
        await run_graph_input_turn(llm, repo, "game-1", "고블린을 공격한다")

    assert llm.calls == []
    assert await repo.load_log_entries("game-1") == []


async def test_graph_input_classifies_one_action_and_creates_confirmation(tmp_path):
    repo = await _repo(tmp_path)
    llm = _FakeLLM({"actions": [{"verb": "attack", "what": "goblin_01"}]})

    result = await run_graph_input_turn(llm, repo, "game-1", "고블린을 공격한다")
    progress = await repo.load_progress("game-1")
    logs = await repo.load_log_entries("game-1")

    assert result.status == "confirmation_required"
    assert progress.pending_confirmation["kind"] == "attack_start"
    assert progress.graph_combat_state is None
    assert [entry.kind for entry in logs] == ["player"]
    assert logs[0].text == "고블린을 공격한다"


async def test_graph_input_protected_target_attack_is_clear_rejection(tmp_path):
    repo = await _repo(tmp_path)
    graph = await repo.load_graph("game-1")
    graph.nodes["goblin_01"].properties["protected"] = True
    await repo.save_graph("game-1", graph)
    llm = _FakeLLM(
        {"actions": [{"verb": "pass"}]},
        narration="",
    )

    result = await run_graph_input_turn(llm, repo, "game-1", "goblin_01을 공격한다")
    logs = await repo.load_log_entries("game-1")

    assert result.status == "rejected"
    assert (
        logs[-1].text
        == "보호받는 대상이라 지금은 공격할 수 없습니다. "
        "대화하거나 주변을 살피면 다른 방법을 찾을 수 있습니다."
    )
    assert "공격" in logs[-1].text
    assert [entry.kind for entry in logs] == ["player", "gm"]
    assert logs[0].text == "goblin_01을 공격한다"
    narrate_call = [call for call in llm.calls if call["agent"] == "graph_narrate"][0]
    payload = json.loads(narrate_call["messages"][1]["content"])
    assert payload["engine_event"]["outcome"] == "action_rejected"
    assert payload["user_request"]["player_input"] == "goblin_01을 공격한다"
    assert payload["engine_event"]["target"]["id"] == "goblin_01"
    assert payload["scene_state"]["target_view"]["id"] == "goblin_01"


async def test_graph_input_speak_writes_gm_narration_instead_of_422(tmp_path):
    repo = await _repo(tmp_path)
    llm = _FakeLLM(
        {"actions": [{"verb": "speak", "what": "goblin_01", "how": "friendly"}]}
    )

    result = await run_graph_input_turn(llm, repo, "game-1", "고블린에게 말을 건다")
    logs = await repo.load_log_entries("game-1")
    progress = await repo.load_progress("game-1")

    assert result.status == "executed"
    assert [entry.kind for entry in logs] == ["player", "gm"]
    assert logs[0].text == "고블린에게 말을 건다"
    assert logs[1].text == "상대는 당신의 말을 듣고 잠시 생각에 잠깁니다."
    assert progress.turn_count == 1
    narrate_call = [call for call in llm.calls if call["agent"] == "graph_narrate"][0]
    assert narrate_call["temperature"] is None


async def test_graph_input_speak_does_not_store_invented_player_question(tmp_path):
    repo = await _repo(tmp_path)
    graph = await repo.load_graph("game-1")
    graph.nodes["goblin_01"].properties["name"] = "고블린"
    await repo.save_graph("game-1", graph)
    llm = _FakeLLM(
        {"actions": [{"verb": "speak", "what": "goblin_01", "how": "friendly"}]},
        narration=(
            "고블린에게 「무슨 일이신가요?」라고 묻습니다.\n"
            "고블린은 눈을 가늘게 뜨고 당신의 말을 기다립니다."
        ),
    )

    result = await run_graph_input_turn(llm, repo, "game-1", "고블린에게 말을 건다")
    logs = await repo.load_log_entries("game-1")

    assert result.status == "executed"
    assert logs[1].text.startswith("고블린에게 말을 겁니다.")
    assert "무슨 일이신가요" not in logs[1].text


async def test_graph_input_persists_narration_ui_cues(tmp_path):
    repo = await _repo(tmp_path)
    llm = _FakeLLM(
        {"actions": [{"verb": "speak", "what": "goblin_01", "how": "friendly"}]},
        narration="고블린이 문틈 너머의 그림자를 가리킵니다.",
        ui_cues=[
            {
                "kind": "opportunity",
                "label": "기회",
                "text": "문틈을 살필 수 있음",
            }
        ],
    )

    result = await run_graph_input_turn(llm, repo, "game-1", "고블린에게 말을 건다")
    logs = await repo.load_log_entries("game-1")

    assert result.status == "executed"
    assert [entry.kind for entry in logs] == ["player", "gm"]
    assert isinstance(logs[1], GMLogEntry)
    assert logs[1].cues[0].text == "문틈을 살필 수 있음"


async def test_graph_input_speak_check_hint_creates_pending_roll(tmp_path):
    repo = await _repo(tmp_path)
    reason = "경비병을 설득하려면 믿을 만한 말을 해야 합니다."
    llm = _FakeLLM(
        {
            "actions": [
                {"verb": "speak", "what": "goblin_01", "how": "friendly"},
            ],
            "action_checks": [{"required": True, "reason": reason}],
        }
    )

    result = await run_graph_input_turn(llm, repo, "game-1", "고블린을 설득한다")
    logs = await repo.load_log_entries("game-1")
    progress = await repo.load_progress("game-1")

    assert result.status == "roll_required"
    assert progress.pending_roll["kind"] == "speak"
    assert progress.pending_roll["stat"] == "presence"
    assert progress.pending_roll["body"] == reason
    assert progress.pending_roll["check_reason"] == reason
    assert [entry.kind for entry in logs] == ["player"]
    assert [call["agent"] for call in llm.calls] == ["classify"]


async def test_graph_input_preroll_speak_does_not_store_invented_player_question(
    tmp_path,
):
    repo = await _repo(tmp_path)
    graph = await repo.load_graph("game-1")
    graph.nodes["goblin_01"].properties["name"] = "고블린"
    await repo.save_graph("game-1", graph)
    llm = _FakeLLM(
        {"actions": [{"verb": "pass"}]},
        narration=(
            "고블린에게 「무슨 일이신가요?」라고 묻습니다.\n"
            "고블린은 눈을 가늘게 뜨고 당신의 말을 기다립니다."
        ),
    )

    events = [
        event
        async for event in run_graph_preroll_stream(
            llm,
            repo,
            "game-1",
            Action(verb="speak", what="goblin_01", how="friendly"),
            reason="고블린을 설득하려면 먼저 말을 꺼내야 합니다.",
            player_input="고블린에게 말을 건다",
        )
    ]
    logs = await repo.load_log_entries("game-1")
    final = events[-1]["result"]
    deltas = [event["text"] for event in events if event["type"] == "narration_delta"]

    assert final.status == "roll_required"
    assert deltas == [
        "고블린에게 말을 겁니다.\n고블린은 눈을 가늘게 뜨고 당신의 말을 기다립니다."
    ]
    assert logs[0].text.startswith("고블린에게 말을 겁니다.")
    assert "무슨 일이신가요" not in logs[0].text
    assert final.pending_roll["body"].startswith("고블린에게 말을 겁니다.")


async def test_graph_input_speak_for_active_social_check_quest_creates_pending_roll(tmp_path):
    repo = await _repo(tmp_path)
    graph = await repo.load_graph("game-1")
    graph.nodes["quest_social"] = GraphNode(
        id="quest_social",
        type="quest",
        properties={
            "title": "섬의 규칙을 듣습니다",
            "status": "active",
            "triggers": [
                {
                    "id": "ask_goblin",
                    "type": "social_check",
                    "target": "goblin_01",
                }
            ],
            "triggers_met": [False],
        },
    )
    await repo.save_graph("game-1", graph)
    progress = await repo.load_progress("game-1")
    await repo.save_progress(
        progress.model_copy(update={"active_quest_id": "quest_social"})
    )
    llm = _FakeLLM(
        {"actions": [{"verb": "speak", "what": "goblin_01", "how": "friendly"}]}
    )

    result = await run_graph_input_turn(llm, repo, "game-1", "고블린에게 규칙을 묻는다")
    saved = await repo.load_progress("game-1")

    assert result.status == "roll_required"
    assert saved.pending_roll["kind"] == "speak"
    assert saved.pending_roll["stat"] == "presence"


async def test_graph_input_visible_pending_quest_accept_requires_confirmation(tmp_path):
    repo = await _repo(tmp_path)
    graph = await repo.load_graph("game-1")
    graph.nodes["goblin_01"].properties["name"] = "고블린"
    graph.nodes["quest_social"] = GraphNode(
        id="quest_social",
        type="quest",
        properties={
            "title": "섬의 규칙을 듣습니다",
            "status": "pending",
            "giver": "goblin_01",
        },
    )
    await repo.save_graph("game-1", graph)
    llm = _FakeLLM({"actions": [{"verb": "pass"}]})

    result = await run_graph_input_turn(llm, repo, "game-1", "고블린의 의뢰를 받는다")
    saved = await repo.load_progress("game-1")

    assert result.status == "confirmation_required"
    assert saved.pending_confirmation["kind"] == "quest_accept"
    assert saved.pending_confirmation["payload"]["action"]["what"] == "quest_social"
    assert [call["agent"] for call in llm.calls] == []


async def test_graph_input_generic_approach_does_not_complete_social_check_quest(
    tmp_path,
):
    repo = await _repo(tmp_path)
    graph = await repo.load_graph("game-1")
    graph.nodes["quest_social"] = GraphNode(
        id="quest_social",
        type="quest",
        properties={
            "title": "섬의 규칙을 듣습니다",
            "status": "active",
            "triggers": [
                {
                    "id": "ask_goblin",
                    "type": "social_check",
                    "target": "goblin_01",
                    "name": "고블린에게 섬의 규칙을 묻습니다",
                }
            ],
            "triggers_met": [False],
        },
    )
    await repo.save_graph("game-1", graph)
    progress = await repo.load_progress("game-1")
    await repo.save_progress(
        progress.model_copy(update={"active_quest_id": "quest_social"})
    )
    llm = _FakeLLM(
        {"actions": [{"verb": "speak", "what": "goblin_01", "how": "friendly"}]}
    )

    result = await run_graph_input_turn(llm, repo, "game-1", "고블린에게 접근합니다")
    saved = await repo.load_progress("game-1")
    saved_graph = await repo.load_graph("game-1")

    assert result.status == "executed"
    assert saved.pending_roll is None
    assert saved.active_quest_id == "quest_social"
    assert saved_graph.nodes["quest_social"].properties["status"] == "active"
    assert saved_graph.nodes["quest_social"].properties["triggers_met"] == [False]


async def test_graph_input_speak_for_visible_active_social_check_infers_target(tmp_path):
    repo = await _repo(tmp_path)
    graph = await repo.load_graph("game-1")
    graph.nodes["quest_social"] = GraphNode(
        id="quest_social",
        type="quest",
        properties={
            "title": "섬의 규칙을 듣습니다",
            "status": "active",
            "triggers": [
                {
                    "id": "ask_goblin",
                    "type": "social_check",
                    "target": "goblin_01",
                }
            ],
            "triggers_met": [False],
        },
    )
    await repo.save_graph("game-1", graph)
    progress = await repo.load_progress("game-1")
    await repo.save_progress(
        progress.model_copy(update={"active_quest_id": "quest_social"})
    )
    llm = _FakeLLM({"actions": [{"verb": "speak", "how": "friendly"}]})

    result = await run_graph_input_turn(llm, repo, "game-1", "규칙을 묻는다")
    saved = await repo.load_progress("game-1")

    assert result.status == "roll_required"
    assert saved.pending_roll["kind"] == "speak"


async def test_graph_input_social_transfer_check_hint_creates_presence_roll(tmp_path):
    repo = await _repo(tmp_path)
    reason = "상대가 선물을 받아들일지 확인해야 합니다."
    llm = _FakeLLM(
        {
            "actions": [
                {
                    "verb": "transfer",
                    "what": "healing_herb",
                    "from": "player_01",
                    "to": "goblin_01",
                    "how": "free",
                },
            ],
            "action_checks": [{"required": True, "reason": reason}],
        }
    )

    result = await run_graph_input_turn(llm, repo, "game-1", "고블린에게 약초를 건넨다")
    progress = await repo.load_progress("game-1")
    graph = await repo.load_graph("game-1")

    assert result.status == "roll_required"
    assert progress.pending_roll["kind"] == "transfer"
    assert progress.pending_roll["stat"] == "presence"
    assert progress.pending_roll["body"] == reason
    assert "carries:player_01:healing_herb" in graph.edges
    assert "carries:goblin_01:healing_herb" not in graph.edges


async def test_graph_input_in_combat_speak_runs_social_exchange(tmp_path, monkeypatch):
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
                    player_hearts=3,
                    enemy_hearts=3,
                )
            }
        )
    )
    llm = _FakeLLM(
        {"actions": [{"verb": "speak", "to": "goblin_01", "how": "hostile"}]},
        narration="당신의 말이 전투의 흐름을 흔듭니다.",
    )

    result = await run_graph_input_turn(llm, repo, "game-1", "고블린을 도발한다")
    saved = await repo.load_progress("game-1")

    assert result.status == "executed"
    assert saved.graph_combat_state is not None
    assert saved.graph_combat_state.last_action == "talk"
    assert saved.graph_combat_state.enemy_hearts == 3
    assert saved.graph_combat_state.enemy_pressure == 1
    assert "combat_narrate" in [call["agent"] for call in llm.calls]


async def test_graph_input_uses_llm_default_graph_narrate_temperature(tmp_path):
    repo = await _repo(tmp_path)
    llm = _FakeLLM(
        {"actions": [{"verb": "speak", "what": "goblin_01", "how": "friendly"}]}
    )

    await run_graph_input_turn(llm, repo, "game-1", "고블린에게 말을 건다")
    narrate_call = [call for call in llm.calls if call["agent"] == "graph_narrate"][0]

    assert narrate_call["temperature"] is None


async def test_graph_input_reflects_speak_turn_into_memory_exchanges_and_suggestions(
    tmp_path,
):
    repo = await _repo(tmp_path)
    llm = _FakeLLM(
        {"actions": [{"verb": "speak", "what": "goblin_01", "how": "friendly"}]},
        narration="고블린은 북문에 낯선 발자국이 있다고 말합니다.",
        turn_summary="고블린에게서 북문의 낯선 발자국 정보를 들었습니다.",
        importance=3,
        suggestions=[
            {"label": "광장", "input_text": "광장으로 이동합니다", "intent": "move"},
            {"label": "goblin_01", "input_text": "goblin_01에게 말을 겁니다", "intent": "talk"},
            {"label": "발자국", "input_text": "발자국을 자세히 살펴봅니다"},
        ],
    )

    result = await run_graph_input_turn(llm, repo, "game-1", "고블린에게 북문을 묻는다")
    history = await repo.load_history_entries("game-1")
    exchanges = await repo.load_exchange_entries("game-1")

    assert [suggestion.model_dump() for suggestion in result.suggestions] == [
        {
            "label": "광장",
            "input_text": "광장으로 이동합니다",
            "intent": "move",
            "action": None,
        },
        {
            "label": "goblin_01",
            "input_text": "goblin_01에게 말을 겁니다",
            "intent": "talk",
            "action": None,
        },
    ]
    assert history == [
        TurnLogEntry(
            turn=1,
            target="goblin_01",
            summary="고블린에게서 북문의 낯선 발자국 정보를 들었습니다.",
            importance=3,
        )
    ]
    assert exchanges == [
        ExchangePair(
            turn=1,
            player="고블린에게 북문을 묻는다",
            narrator="고블린은 북문에 낯선 발자국이 있다고 말합니다.",
            target="goblin_01",
        )
    ]
    assert [call["agent"] for call in llm.calls].count("graph_narrate") == 1
    assert "graph_reflect" not in [call["agent"] for call in llm.calls]


async def test_graph_input_passes_focused_context_to_classify(
    tmp_path,
):
    repo = await _repo(tmp_path)
    await repo.append_history_entries(
        "game-1",
        [
            TurnLogEntry(turn=1, summary="중요하지 않은 소문입니다.", importance=1),
            TurnLogEntry(
                turn=2,
                target="goblin_01",
                summary="고블린은 북문에 낯선 발자국이 있다고 말했습니다.",
                importance=3,
            ),
        ],
    )
    await repo.append_exchange_entries(
        "game-1",
        [
            ExchangePair(
                turn=2,
                player="북문에 대해 묻는다",
                narrator="고블린은 발자국을 보았다고 말합니다.",
            )
        ],
    )
    llm = _FakeLLM({"actions": [{"verb": "pass"}]}, narration="당신은 잠시 생각합니다.")

    await run_graph_input_turn(llm, repo, "game-1", "그걸 따라간다")
    classify_call = [call for call in llm.calls if call["agent"] == "classify"][0]
    payload = json.loads(classify_call["messages"][1]["content"])

    assert list(payload) == ["context", "player_input"]
    assert payload["player_input"] == "그걸 따라간다"
    assert "player_input" not in payload["context"]
    assert "history" not in payload
    assert "recent_exchanges" not in payload
    assert "recent_exchanges" not in payload
    assert payload["context"]["references"]["recent_exchanges"] == [
        {
            "turn": 2,
            "player": "북문에 대해 묻는다",
            "summary": "고블린은 발자국을 보았다고 말합니다.",
        }
    ]


async def test_graph_input_uses_llm_default_classify_temperature(tmp_path):
    repo = await _repo(tmp_path)
    llm = _FakeLLM({"actions": [{"verb": "pass"}]}, narration="당신은 잠시 생각합니다.")

    await run_graph_input_turn(llm, repo, "game-1", "잠시 기다린다")

    classify_call = [call for call in llm.calls if call["agent"] == "classify"][0]
    assert classify_call["temperature"] is None


async def test_graph_input_passes_env_classify_recent_context_limits(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("LLM_CLASSIFY_LIMIT_RECENT_SCENE", "1")
    monkeypatch.setenv("LLM_CLASSIFY_LIMIT_RECENT_EXCHANGES", "1")
    repo = await _repo(tmp_path)
    await repo.append_history_entries(
        "game-1",
        [
            TurnLogEntry(turn=1, summary="오래된 장면입니다."),
            TurnLogEntry(turn=2, summary="최근 장면입니다."),
        ],
    )
    await repo.append_exchange_entries(
        "game-1",
        [
            ExchangePair(turn=1, player="오래된 질문", narrator="오래된 답변"),
            ExchangePair(turn=2, player="최근 질문", narrator="최근 답변"),
        ],
    )
    llm = _FakeLLM({"actions": [{"verb": "pass"}]}, narration="당신은 잠시 생각합니다.")

    await run_graph_input_turn(llm, repo, "game-1", "잠시 기다린다")

    classify_call = [call for call in llm.calls if call["agent"] == "classify"][0]
    payload = json.loads(classify_call["messages"][1]["content"])
    context = payload["context"]
    assert context["references"]["recent_scene"] == [
        {"turn": 2, "summary": "최근 장면입니다."}
    ]
    assert context["references"]["recent_exchanges"] == [
        {"turn": 2, "player": "최근 질문", "summary": "최근 답변"}
    ]


async def test_graph_input_classify_context_omits_global_importance_history(
    tmp_path,
):
    repo = await _repo(tmp_path)
    entries = [
        TurnLogEntry(turn=1, summary="낮은 중요도 오래된 기억입니다.", importance=1),
        TurnLogEntry(turn=2, summary="낮은 중요도 최근 기억입니다.", importance=1),
        *[
            TurnLogEntry(
                turn=turn,
                summary=f"중요한 기억 {turn}",
                importance=2,
            )
            for turn in range(3, 22)
        ],
    ]
    await repo.append_history_entries("game-1", entries)
    llm = _FakeLLM({"actions": [{"verb": "pass"}]}, narration="당신은 잠시 생각합니다.")

    await run_graph_input_turn(llm, repo, "game-1", "기억을 떠올린다")
    classify_call = [call for call in llm.calls if call["agent"] == "classify"][0]
    payload = json.loads(classify_call["messages"][1]["content"])
    encoded = json.dumps(payload, ensure_ascii=False)

    assert "history" not in payload
    assert "낮은 중요도 오래된 기억" not in encoded
    assert payload["context"]["references"]["recent_scene"] == [
        {"turn": 19, "summary": "중요한 기억 19"},
        {"turn": 20, "summary": "중요한 기억 20"},
        {"turn": 21, "summary": "중요한 기억 21"},
    ]
    assert "budget" not in payload["context"]


async def test_graph_input_streams_result_before_speak_narration(tmp_path):
    repo = await _repo(tmp_path)
    llm = _FakeLLM(
        {"actions": [{"verb": "speak", "what": "goblin_01", "how": "friendly"}]},
        narration="상대는 당신의 말을 듣습니다.",
    )

    events = [
        event
        async for event in run_graph_input_turn_stream(
            llm,
            repo,
            "game-1",
            "고블린에게 말을 건다",
        )
    ]
    logs = await repo.load_log_entries("game-1")

    assert events[0]["type"] == "result"
    assert events[-1]["type"] == "final"
    assert all(event["type"] == "narration_delta" for event in events[1:-1])
    assert events[0]["result"].status == "executed"
    assert events[0]["result"].outcome == "neutral"
    assert (
        "".join(event["text"] for event in events[1:-1])
        == "상대는 당신의 말을 듣습니다."
    )
    assert events[-1]["result"].status == "executed"
    assert [entry.kind for entry in logs] == ["player", "gm"]
    assert logs[-1].text == "상대는 당신의 말을 듣습니다."


async def test_graph_input_streams_single_result_for_multiple_actions(tmp_path):
    repo = await _repo(tmp_path)
    llm = _FakeLLM(
        {
            "actions": [
                {"verb": "speak", "what": "goblin_01", "how": "friendly"},
                {"verb": "move", "to": "forest"},
            ]
        },
        narration="상대는 고개를 끄덕입니다.",
    )

    events = [
        event
        async for event in run_graph_input_turn_stream(
            llm,
            repo,
            "game-1",
            "multi action regression",
        )
    ]
    logs = await repo.load_log_entries("game-1")

    assert events[0]["type"] == "result"
    assert events[-1]["type"] == "final"
    assert [event["type"] for event in events].count("result") == 1
    assert all(event["type"] == "narration_delta" for event in events[1:-1])
    assert "".join(event["text"] for event in events[1:-1]) == (
        "상대는 고개를 끄덕입니다.상대는 고개를 끄덕입니다."
    )
    assert events[-1]["result"].front_state.place.id == "forest"
    assert [entry.kind for entry in logs] == ["player", "gm", "act", "gm"]


@pytest.mark.parametrize(
    ("item_id", "player_input", "raw_error"),
    [
        ("healing_herb", "회복 약초를 사용한다", "hp already full"),
        ("mana_vial", "마나 시약을 사용한다", "mp already full"),
    ],
)
async def test_graph_input_streams_item_use_rejection_as_gm_narration(
    tmp_path,
    item_id,
    player_input,
    raw_error,
):
    repo = await _repo(tmp_path)
    llm = _FakeLLM(
        {"actions": [{"verb": "use", "what": item_id}]},
        narration="당신은 손을 멈춥니다. 지금은 그 물건을 쓸 이유가 없습니다.",
    )

    events = [
        event
        async for event in run_graph_input_turn_stream(
            llm,
            repo,
            "game-1",
            player_input,
        )
    ]
    graph = await repo.load_graph("game-1")
    logs = await repo.load_log_entries("game-1")
    progress = await repo.load_progress("game-1")

    assert events[0]["type"] == "result"
    assert events[-1]["type"] == "final"
    assert all(event["type"] == "narration_delta" for event in events[1:-1])
    assert events[0]["result"].status == "executed"
    assert events[0]["result"].outcome == "neutral"
    assert "".join(event["text"] for event in events[1:-1]) == (
        "당신은 손을 멈춥니다. 지금은 그 물건을 쓸 이유가 없습니다."
    )
    assert events[-1]["result"].status == "rejected"
    assert [entry.kind for entry in logs] == ["player", "gm"]
    assert logs[0].text == player_input
    assert logs[1].text == "당신은 손을 멈춥니다. 지금은 그 물건을 쓸 이유가 없습니다."
    assert raw_error not in logs[1].text
    assert f"carries:player_01:{item_id}" in graph.edges
    assert progress.turn_count == 1


@pytest.mark.parametrize(
    ("item_id", "player_input", "expected"),
    [
        (
            "ghost_item",
            "유령 물건을 사용한다",
            "그런 물건은 없습니다. 주변이나 소지품을 살펴보고 실제로 보이는 물건을 사용해야 합니다.",
        ),
        (
            "supply_token",
            "보급 표식을 사용한다",
            "그 물건을 가지고 있지 않습니다. 주변에 보이는 물건이라면 먼저 줍거나 챙겨야 합니다.",
        ),
    ],
)
async def test_graph_input_rejects_unusable_item_intent_with_public_next_step(
    tmp_path,
    item_id,
    player_input,
    expected,
):
    repo = await _repo(tmp_path)
    llm = _FakeLLM({"actions": [{"verb": "use", "what": item_id}]}, narration="")

    result = await run_graph_input_turn(llm, repo, "game-1", player_input)
    graph = await repo.load_graph("game-1")
    logs = await repo.load_log_entries("game-1")

    assert result.status == "rejected"
    assert logs[-1].text == expected
    assert [entry.kind for entry in logs] == ["player", "gm"]
    assert logs[0].text == player_input
    assert "carries:player_01:supply_token" not in graph.edges
    assert "located_at:supply_token:town" in graph.edges


@pytest.mark.parametrize(
    ("action", "player_input", "expected"),
    [
        (
            {
                "verb": "transfer",
                "what": "potion",
                "from": "goblin_01",
                "to": "player_01",
                "how": "trade",
            },
            "고블린에게 회복 물약을 산다",
            "금화가 부족해 거래할 수 없습니다. 금화를 더 모으거나 다른 물건을 고르셔야 합니다.",
        ),
        (
            {
                "verb": "transfer",
                "what": "gem",
                "from": "player_01",
                "to": "goblin_01",
                "how": "trade",
            },
            "고블린에게 보석을 판다",
            "상대의 금화가 부족해 거래할 수 없습니다. 다른 물건을 고르거나 나중에 다시 거래해야 합니다.",
        ),
        (
            {
                "verb": "transfer",
                "what": "dagger",
                "from": "player_01",
                "to": "goblin_01",
                "how": "trade",
            },
            "장착한 단검을 판다",
            "장착 중인 물건은 팔 수 없습니다. 먼저 장착을 해제해야 합니다.",
        ),
        (
            {
                "verb": "transfer",
                "what": "gem",
                "from": "goblin_01",
                "to": "player_01",
                "how": "trade",
            },
            "고블린에게 보석을 산다",
            "상대가 그 물건을 가지고 있지 않습니다. 다른 물건을 고르거나 거래 가능한 물건을 확인해야 합니다.",
        ),
    ],
)
async def test_graph_input_rejects_blocked_trade_with_public_repair_path(
    tmp_path,
    action,
    player_input,
    expected,
):
    repo = await _repo_with_trade_fixture(tmp_path)
    llm = _FakeLLM({"actions": [action]}, narration="")

    result = await run_graph_input_turn(llm, repo, "game-1", player_input)
    graph = await repo.load_graph("game-1")
    logs = await repo.load_log_entries("game-1")

    assert result.status == "rejected"
    assert logs[-1].text == expected
    assert [entry.kind for entry in logs] == ["player", "gm"]
    assert logs[0].text == player_input
    assert graph.nodes["player_01"].properties["gold"] == 2
    assert graph.nodes["goblin_01"].properties["gold"] == 1
    assert "carries:goblin_01:potion" in graph.edges
    assert "carries:player_01:gem" in graph.edges
    assert "equips:player_01:dagger" in graph.edges
    assert "carries:player_01:potion" not in graph.edges


async def test_graph_input_rejects_low_affinity_trade_with_public_repair_path(
    tmp_path,
):
    repo = await _repo_with_trade_fixture(tmp_path)
    graph = await repo.load_graph("game-1")
    graph.nodes["player_01"].properties["gold"] = 20
    graph.edges["relation:goblin_01:player_01"] = GraphEdge(
        id="relation:goblin_01:player_01",
        type="relation",
        from_node_id="goblin_01",
        to_node_id="player_01",
        properties={"affinity": -1},
    )
    await repo.save_graph("game-1", graph)
    llm = _FakeLLM(
        {
            "actions": [
                {
                    "verb": "transfer",
                    "what": "potion",
                    "from": "goblin_01",
                    "to": "player_01",
                    "how": "trade",
                }
            ]
        },
        narration="",
    )

    result = await run_graph_input_turn(llm, repo, "game-1", "고블린에게 회복 물약을 산다")
    graph = await repo.load_graph("game-1")
    logs = await repo.load_log_entries("game-1")

    assert result.status == "rejected"
    assert (
        logs[-1].text
        == "친밀도가 부족해 거래가 되지 않습니다. 먼저 대화하거나 신뢰를 얻어야 합니다."
    )
    assert graph.nodes["player_01"].properties["gold"] == 20
    assert graph.nodes["goblin_01"].properties["gold"] == 1
    assert "carries:goblin_01:potion" in graph.edges


async def test_graph_input_uncertain_inspection_preserves_reason_and_original_input(
    tmp_path,
):
    repo = await _repo(tmp_path)
    reason = "광장의 흔적이 서로 맞물리는지 자세히 살펴야 합니다."
    llm = _FakeLLM(
        {
            "actions": [{"verb": "perceive", "what": "town"}],
            "action_checks": [{"required": True, "reason": reason}],
        }
    )

    result = await run_graph_input_turn(llm, repo, "game-1", "광장의 흔적을 자세히 조사한다")
    progress = await repo.load_progress("game-1")
    logs = await repo.load_log_entries("game-1")

    assert result.status == "roll_required"
    assert progress.pending_roll["kind"] == "perceive"
    assert progress.pending_roll["body"] == reason
    assert progress.pending_roll["check_reason"] == reason
    assert progress.pending_roll["player_input"] == "광장의 흔적을 자세히 조사한다"
    assert [entry.kind for entry in logs] == ["player"]


async def test_graph_input_perceive_creates_pending_roll(tmp_path):
    repo = await _repo(tmp_path)
    llm = _FakeLLM({"actions": [{"verb": "perceive", "what": "town"}]})

    result = await run_graph_input_turn(llm, repo, "game-1", "주변을 자세히 살펴본다")
    logs = await repo.load_log_entries("game-1")
    progress = await repo.load_progress("game-1")

    assert result.status == "roll_required"
    assert progress.pending_roll["kind"] == "perceive"
    assert progress.pending_roll["stat"] == "mind"
    assert progress.pending_roll["required_roll"] == 13
    assert [entry.kind for entry in logs] == ["player"]
    assert logs[0].text == "주변을 자세히 살펴본다"
    assert result.front_state.pending_roll is not None


async def test_graph_input_stream_perceive_streams_preroll_before_roll(
    tmp_path,
):
    repo = await _repo(tmp_path)
    llm = _FakeLLM(
        {"actions": [{"verb": "perceive", "what": "town"}]},
        narration="당신은 훈련실 바닥의 흔적을 따라 시선을 낮춥니다.",
    )

    events = [
        event
        async for event in run_graph_input_turn_stream(
            llm,
            repo,
            "game-1",
            "주변을 자세히 살펴본다",
        )
    ]
    progress = await repo.load_progress("game-1")
    logs = await repo.load_log_entries("game-1")

    assert events[0]["type"] == "result"
    assert events[-1]["type"] == "final"
    deltas = [event for event in events[1:-1] if event["type"] == "narration_delta"]
    assert len(deltas) == 2
    assert events[0]["result"].status == "roll_required"
    assert events[0]["result"].front_state.pending_roll is not None
    assert events[0]["result"].front_state.log == [logs[0]]
    assert events[-1]["result"].status == "roll_required"
    assert "".join(event["text"] for event in deltas) == llm.narration
    assert progress.pending_roll["body"] == llm.narration
    assert progress.pending_roll["player_input"] == "주변을 자세히 살펴본다"
    assert events[-1]["result"].front_state.pending_roll.body == progress.pending_roll["body"]
    assert events[-1]["result"].front_state.log[-1].text == llm.narration
    assert [entry.kind for entry in logs] == ["player", "gm"]
    assert [call["agent"] for call in llm.calls] == ["classify", "graph_narrate"]


async def test_graph_input_pickup_visible_location_item_transfers_to_inventory(
    tmp_path,
):
    repo = await _repo(tmp_path)
    llm = _FakeLLM({"actions": [{"verb": "pass"}]})

    result = await run_graph_input_turn(llm, repo, "game-1", "보급 표식을 획득한다")
    graph = await repo.load_graph("game-1")
    logs = await repo.load_log_entries("game-1")

    assert result.status == "executed"
    assert "located_at:supply_token:town" not in graph.edges
    assert "carries:player_01:supply_token" in graph.edges
    assert logs[-2].text == "당신은 보급 표식을 챙깁니다."
    assert logs[-1].kind == "gm"
    assert [call["agent"] for call in llm.calls] == ["graph_narrate"]


async def test_graph_input_targetless_speak_defaults_to_nearby_living_npc(tmp_path):
    repo = await _repo(tmp_path)
    llm = _FakeLLM({"actions": [{"verb": "speak", "how": "friendly"}]})

    await run_graph_input_turn(llm, repo, "game-1", "근처 사람에게 말을 건다")
    progress = await repo.load_progress("game-1")
    narrate_call = [call for call in llm.calls if call["agent"] == "graph_narrate"][0]
    user_prompt = json.loads(narrate_call["messages"][1]["content"])

    assert progress.active_subject_id == "goblin_01"
    assert user_prompt["scene_state"]["target_view"]["id"] == "goblin_01"
    assert user_prompt["scene_state"]["target_view"]["name"] == "goblin_01"
    assert user_prompt["engine_event"]["kind"] == "dialogue"
    assert "NPC가 직접 반응" in narrate_call["messages"][0]["content"]


async def test_graph_input_targetless_repeated_speak_prefers_active_subject(tmp_path):
    repo = await _repo(tmp_path)
    graph = await repo.load_graph("game-1")
    graph.nodes["merchant_01"] = _character("merchant_01")
    graph.edges["located_at:merchant_01:town"] = GraphEdge(
        id="located_at:merchant_01:town",
        type="located_at",
        from_node_id="merchant_01",
        to_node_id="town",
    )
    await repo.save_graph("game-1", graph)
    progress = await repo.load_progress("game-1")
    await repo.save_progress(
        progress.model_copy(update={"active_subject_id": "merchant_01"})
    )
    llm = _FakeLLM({"actions": [{"verb": "speak", "how": "friendly"}]})

    await run_graph_input_turn(llm, repo, "game-1", "그에게 다시 묻는다")
    saved = await repo.load_progress("game-1")
    narrate_call = [call for call in llm.calls if call["agent"] == "graph_narrate"][0]
    user_prompt = json.loads(narrate_call["messages"][1]["content"])

    assert saved.active_subject_id == "merchant_01"
    assert user_prompt["scene_state"]["target_view"]["id"] == "merchant_01"
    assert user_prompt["engine_event"]["target"]["id"] == "merchant_01"


async def test_graph_input_narration_payload_includes_recent_narration(tmp_path):
    repo = await _repo(tmp_path)
    await repo.append_log_entries(
        "game-1",
        [
            GMLogEntry(id=1, kind="gm", text="경비병이 북문을 지킵니다."),
        ],
    )
    llm = _FakeLLM(
        {"actions": [{"verb": "speak", "what": "goblin_01", "how": "friendly"}]}
    )

    await run_graph_input_turn(llm, repo, "game-1", "경비병에게 인사한다")
    narrate_call = [call for call in llm.calls if call["agent"] == "graph_narrate"][0]
    payload = json.loads(narrate_call["messages"][1]["content"])
    encoded = json.dumps(payload, ensure_ascii=False)

    assert "recent_log" not in payload
    assert payload["reference_context"]["recent_narration"] == [
        {"text": "경비병이 북문을 지킵니다."}
    ]
    assert "경비병이 북문을 지킵니다." in encoded
    assert "recent_exchanges" not in payload["reference_context"]


async def test_graph_input_speak_times_out_slow_narration_and_uses_fallback(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv("GRAPH_INPUT_NARRATION_TIMEOUT_S", "0.01")
    repo = await _repo(tmp_path)
    llm = _SlowGraphNarrateLLM(
        {"actions": [{"verb": "speak", "what": "goblin_01", "how": "friendly"}]}
    )

    result = await run_graph_input_turn(llm, repo, "game-1", "고블린에게 말을 건다")
    logs = await repo.load_log_entries("game-1")

    assert result.status == "executed"
    assert [entry.kind for entry in logs] == ["player", "gm"]
    assert logs[1].text == "goblin_01는 당신의 말을 듣고 잠시 침묵합니다."


async def test_graph_input_speak_rate_limited_narration_uses_fallback(tmp_path):
    repo = await _repo(tmp_path)
    llm = _RateLimitedGraphNarrateLLM(
        {"actions": [{"verb": "speak", "what": "goblin_01", "how": "friendly"}]}
    )

    result = await run_graph_input_turn(llm, repo, "game-1", "고블린에게 말을 건다")
    logs = await repo.load_log_entries("game-1")

    assert result.status == "executed"
    assert [entry.kind for entry in logs] == ["player", "gm"]
    assert logs[1].text == "goblin_01는 당신의 말을 듣고 잠시 침묵합니다."


async def test_graph_input_runs_multiple_actions_in_order(tmp_path):
    repo = await _repo(tmp_path)
    llm = _FakeLLM(
        {
            "actions": [
                {"verb": "move", "to": "forest"},
                {"verb": "pass", "note": "주변을 살핀다"},
            ]
        },
        narration="당신은 주변을 살핍니다.",
    )

    result = await run_graph_input_turn(
        llm, repo, "game-1", "광장으로 가서 주변을 살핀다"
    )
    graph = await repo.load_graph("game-1")
    progress = await repo.load_progress("game-1")
    logs = await repo.load_log_entries("game-1")

    assert result.status == "executed"
    assert "located_at:player_01:forest" in graph.edges
    assert "located_at:player_01:town" not in graph.edges
    assert progress.turn_count == 2
    assert [entry.kind for entry in logs] == ["player", "act", "gm", "gm"]
    assert logs[1].text == "당신은 광장으로 이동합니다."
    assert logs[-1].text == "당신은 주변을 살핍니다."


async def test_graph_input_executes_valid_parts_of_mixed_multi_intent(tmp_path):
    repo = await _repo(tmp_path)
    llm = _FakeLLM(
        {
            "actions": [
                {"verb": "move", "to": "forest"},
                {"verb": "use", "what": "ghost_item"},
            ]
        },
        narration="당신은 가능한 행동만 이어 갑니다.",
    )

    result = await run_graph_input_turn(
        llm,
        repo,
        "game-1",
        "광장으로 가서 유령 물건을 사용한다",
    )
    graph = await repo.load_graph("game-1")
    logs = await repo.load_log_entries("game-1")

    assert result.status == "executed"
    assert "located_at:player_01:forest" in graph.edges
    assert "located_at:player_01:town" not in graph.edges
    assert [entry.kind for entry in logs] == ["player", "act", "gm", "gm"]
    assert "유령 물건" in logs[0].text
    assert "carries:player_01:ghost_item" not in graph.edges


async def test_graph_input_executes_later_valid_part_after_invalid_multi_intent(
    tmp_path,
):
    repo = await _repo(tmp_path)
    llm = _FakeLLM(
        {
            "actions": [
                {"verb": "use", "what": "ghost_item"},
                {"verb": "move", "to": "forest"},
            ]
        },
        narration="당신은 가능한 행동만 이어 갑니다.",
    )

    result = await run_graph_input_turn(
        llm,
        repo,
        "game-1",
        "유령 물건을 사용하고 광장으로 간다",
    )
    graph = await repo.load_graph("game-1")
    logs = await repo.load_log_entries("game-1")

    assert result.status == "executed"
    assert "located_at:player_01:forest" in graph.edges
    assert [entry.kind for entry in logs] == ["player", "gm", "act", "gm"]
    assert "carries:player_01:ghost_item" not in graph.edges


async def test_graph_input_stops_multiple_actions_at_confirmation(tmp_path):
    repo = await _repo(tmp_path)
    llm = _FakeLLM(
        {
            "actions": [
                {"verb": "attack", "what": "goblin_01"},
                {"verb": "pass"},
            ]
        }
    )

    result = await run_graph_input_turn(llm, repo, "game-1", "공격하고 기다린다")
    progress = await repo.load_progress("game-1")
    logs = await repo.load_log_entries("game-1")

    assert result.status == "confirmation_required"
    assert progress.pending_confirmation["kind"] == "attack_start"
    assert progress.turn_count == 0
    assert [entry.kind for entry in logs] == ["player"]
    assert logs[0].text == "공격하고 기다린다"
