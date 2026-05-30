import json

from src.game.domain.graph import Graph, GraphEdge, GraphNode
from src.game.domain.memory import ExchangePair, Memory, TurnLogEntry
from src.game.domain.progress import GameProgress
from src.game.runtime import GameRuntimeState
from src.game.runtime.narration.memory_context import (
    classify_recent_exchanges_payload,
    narrate_recent_exchanges_payload,
    previous_scene_payload,
    subject_memories_payload,
)


def _runtime(*, dialogue_count: int = 0) -> GameRuntimeState:
    return GameRuntimeState(
        graph=Graph(
            nodes={
                "town": GraphNode(
                    id="town", type="location", properties={"name": "마을"}
                ),
                "player_01": GraphNode(id="player_01", type="character"),
                "npc_merchant": GraphNode(
                    id="npc_merchant",
                    type="character",
                    properties={"name": "상인"},
                ),
            },
            edges={
                "located_at:player_01:town": GraphEdge(
                    id="located_at:player_01:town",
                    type="located_at",
                    from_node_id="player_01",
                    to_node_id="town",
                ),
                "located_at:npc_merchant:town": GraphEdge(
                    id="located_at:npc_merchant:town",
                    type="located_at",
                    from_node_id="npc_merchant",
                    to_node_id="town",
                ),
            },
        ),
        progress=GameProgress(game_id="game-1", player_id="player_01"),
        recent_exchanges=[
            ExchangePair(turn=turn, player=f"질문 {turn}", narrator=f"응답 {turn}")
            for turn in range(1, dialogue_count + 1)
        ],
    )


def test_recent_exchanges_is_limited_and_does_not_pull_turn_log():
    runtime = _runtime(dialogue_count=7)
    runtime.turn_log.append(
        TurnLogEntry(turn=99, target="npc_merchant", summary="중요 기억", importance=3)
    )

    payload = classify_recent_exchanges_payload(runtime)

    assert len(payload) == 3
    assert all(set(item) == {"turn", "player", "summary"} for item in payload)
    assert payload[0]["turn"] == 5
    assert "중요 기억" not in json.dumps(payload, ensure_ascii=False)


def test_recent_exchanges_limit_can_come_from_env(monkeypatch):
    monkeypatch.setenv("MAX_RECENT_EXCHANGES", "2")
    runtime = _runtime(dialogue_count=7)

    payload = classify_recent_exchanges_payload(runtime)

    assert [item["turn"] for item in payload] == [6, 7]


def test_narrate_recent_exchanges_uses_narrator_original_text(monkeypatch):
    monkeypatch.setenv("MAX_RECENT_EXCHANGES", "2")
    runtime = _runtime(dialogue_count=3)

    payload = narrate_recent_exchanges_payload(runtime)

    assert payload == [
        {"turn": 2, "player": "질문 2", "narrator": "응답 2"},
        {"turn": 3, "player": "질문 3", "narrator": "응답 3"},
    ]


def test_previous_scene_uses_entries_before_recent_raw_exchanges(monkeypatch):
    monkeypatch.setenv("MAX_RECENT_EXCHANGES", "2")
    runtime = _runtime(dialogue_count=5)
    runtime.turn_log = [
        TurnLogEntry(turn=turn, target=f"npc_{turn}", summary=f"요약 {turn}")
        for turn in range(1, 6)
    ]

    payload = previous_scene_payload(runtime, limit=2)

    assert payload == [
        {"turn": 2, "target": "npc_2", "summary": "요약 2"},
        {"turn": 3, "target": "npc_3", "summary": "요약 3"},
    ]


def test_previous_scene_limit_can_come_from_env(monkeypatch):
    monkeypatch.setenv("MAX_RECENT_EXCHANGES", "1")
    monkeypatch.setenv("MAX_PREVIOUS_SCENE", "2")
    runtime = _runtime(dialogue_count=5)
    runtime.turn_log = [
        TurnLogEntry(turn=turn, target=f"npc_{turn}", summary=f"요약 {turn}")
        for turn in range(1, 6)
    ]

    payload = previous_scene_payload(runtime)

    assert [item["turn"] for item in payload] == [3, 4]


def test_narrate_recent_exchanges_keeps_only_same_target(monkeypatch):
    monkeypatch.setenv("MAX_RECENT_EXCHANGES", "3")
    runtime = _runtime()
    runtime.recent_exchanges = [
        ExchangePair(
            turn=1, player="상인 질문", narrator="상인 답", target="npc_merchant"
        ),
        ExchangePair(
            turn=2, player="다른 질문", narrator="다른 답", target="npc_other"
        ),
        ExchangePair(
            turn=3, player="상인 재질문", narrator="상인 재답", target="npc_merchant"
        ),
        ExchangePair(
            turn=4, player="마지막 질문", narrator="마지막 답", target=None
        ),
    ]

    payload = narrate_recent_exchanges_payload(runtime, target="npc_merchant")

    assert [item["turn"] for item in payload] == [1, 3]
    assert payload[1]["target"] == "npc_merchant"


def test_subject_memories_keep_campaign_and_target_only():
    runtime = _runtime()
    runtime.memories = [
        Memory(turn=1, target=None, content="항구에는 2인 승선 규칙이 있습니다."),
        Memory(turn=2, target="npc_other", content="다른 인물의 기억입니다."),
        Memory(
            turn=3,
            target="npc_merchant",
            content="상인은 당신이 젖은 표를 확인했다고 기억합니다.",
            importance=2,
        ),
    ]

    payload = subject_memories_payload(runtime, target="npc_merchant")

    assert payload == [
        {
            "turn": 1,
            "content": "항구에는 2인 승선 규칙이 있습니다.",
            "importance": 1,
        },
        {
            "turn": 3,
            "target": "npc_merchant",
            "content": "상인은 당신이 젖은 표를 확인했다고 기억합니다.",
            "importance": 2,
        },
    ]
