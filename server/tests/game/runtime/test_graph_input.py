import json
import asyncio

import httpx
import pytest
from openai import RateLimitError

from src.db.graph.local_fs import LocalFsGraphRepo
from src.game.domain.action import Action
from src.game.domain.combat import GraphCombatState
from src.game.domain.graph import Graph, GraphEdge, GraphNode
from src.game.domain.memory import DialoguePair, GMLogEntry, TurnLogEntry
from src.game.domain.progress import GameProgress
from src.game.runtime.flow.confirmation import GraphConfirmationActive
from src.game.runtime.flow.input import (
    run_graph_input_turn,
    run_graph_input_turn_stream,
)
from src.game.runtime.flow.roll import build_pending_roll


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
    ) -> None:
        self.payload = payload
        self.narration = narration
        self.turn_summary = turn_summary
        self.importance = importance
        self.suggestions = suggestions or []
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
        if not self.turn_summary and not self.suggestions and self.importance == 1:
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
    assert payload["current_event"]["outcome"] == "action_rejected"
    assert payload["current_event"]["target"]["id"] == "goblin_01"
    assert payload["target_view"]["id"] == "goblin_01"


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
    assert narrate_call["temperature"] == 1.0


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


async def test_graph_input_passes_env_graph_narrate_temperature(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv("LLM_GRAPH_NARRATE_TEMPERATURE", "0.7")
    repo = await _repo(tmp_path)
    llm = _FakeLLM(
        {"actions": [{"verb": "speak", "what": "goblin_01", "how": "friendly"}]}
    )

    await run_graph_input_turn(llm, repo, "game-1", "고블린에게 말을 건다")
    narrate_call = [call for call in llm.calls if call["agent"] == "graph_narrate"][0]

    assert narrate_call["temperature"] == 0.7


async def test_graph_input_reflects_speak_turn_into_memory_dialogue_and_suggestions(
    tmp_path,
):
    repo = await _repo(tmp_path)
    llm = _FakeLLM(
        {"actions": [{"verb": "speak", "what": "goblin_01", "how": "friendly"}]},
        narration="고블린은 북문에 낯선 발자국이 있다고 말합니다.",
        turn_summary="고블린에게서 북문의 낯선 발자국 정보를 들었습니다.",
        importance=3,
        suggestions=[
            "북문으로 이동합니다",
            "발자국을 자세히 살펴봅니다",
        ],
    )

    result = await run_graph_input_turn(llm, repo, "game-1", "고블린에게 북문을 묻는다")
    history = await repo.load_history_entries("game-1")
    dialogue = await repo.load_dialogue_entries("game-1")

    assert [suggestion.model_dump() for suggestion in result.suggestions] == [
        {
            "label": "북문으로 이동합니다",
            "input_text": "북문으로 이동합니다",
            "intent": None,
            "action": None,
        },
        {
            "label": "발자국을 자세히 살펴봅니다",
            "input_text": "발자국을 자세히 살펴봅니다",
            "intent": None,
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
    assert dialogue == [
        DialoguePair(
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
    await repo.append_dialogue_entries(
        "game-1",
        [
            DialoguePair(
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

    assert set(payload) == {"player_input", "context"}
    assert payload["context"]["player_input"] == "그걸 따라간다"
    assert "history" not in payload
    assert "recent_dialogue" not in payload
    assert payload["context"]["references"]["recent_dialogue"] == [
        {
            "turn": 2,
            "player": "북문에 대해 묻는다",
            "summary": "고블린은 발자국을 보았다고 말합니다.",
        }
    ]


async def test_graph_input_passes_env_classify_temperature(tmp_path, monkeypatch):
    monkeypatch.setenv("LLM_CLASSIFY_TEMPERATURE", "0.25")
    repo = await _repo(tmp_path)
    llm = _FakeLLM({"actions": [{"verb": "pass"}]}, narration="당신은 잠시 생각합니다.")

    await run_graph_input_turn(llm, repo, "game-1", "잠시 기다린다")

    classify_call = [call for call in llm.calls if call["agent"] == "classify"][0]
    assert classify_call["temperature"] == 0.25


async def test_graph_input_passes_env_classify_context_limits(tmp_path, monkeypatch):
    monkeypatch.setenv("LLM_CLASSIFY_LIMIT_VISIBLE_TARGETS", "1")
    monkeypatch.setenv("LLM_CLASSIFY_LIMIT_INVENTORY", "0")
    repo = await _repo(tmp_path)
    llm = _FakeLLM({"actions": [{"verb": "pass"}]}, narration="당신은 잠시 생각합니다.")

    await run_graph_input_turn(llm, repo, "game-1", "잠시 기다린다")

    classify_call = [call for call in llm.calls if call["agent"] == "classify"][0]
    payload = json.loads(classify_call["messages"][1]["content"])
    context = payload["context"]
    assert len(context["identity"]["visible_targets"]) == 1
    assert context["identity"]["inventory"] == []
    assert context["budget"]["inventory_omitted"] > 0


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
    assert "중요한 기억" not in encoded
    assert payload["context"]["budget"]["visible_targets_omitted"] == 0


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
    assert user_prompt["target_view"]["id"] == "goblin_01"
    assert user_prompt["target_view"]["name"] == "goblin_01"
    assert user_prompt["current_event"]["kind"] == "dialogue"
    assert "NPC가 직접 반응" in narrate_call["messages"][0]["content"]


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
    assert payload["recent_narration"] == [
        {"text": "경비병이 북문을 지킵니다.", "outcome": None}
    ]
    assert "경비병이 북문을 지킵니다." in encoded
    assert "recent_dialogue" in payload


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
