import json

from src.game.domain.graph import Graph, GraphEdge, GraphNode
from src.game.domain.memory import DialoguePair, TurnLogEntry
from src.game.domain.progress import GameProgress
from src.game.runtime import GameRuntimeState
from src.game.runtime.narration.memory_context import (
    classify_recent_dialogue_payload,
    narrate_recent_dialogue_payload,
    related_memory_payload,
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
        recent_dialogue=[
            DialoguePair(turn=turn, player=f"질문 {turn}", narrator=f"응답 {turn}")
            for turn in range(1, dialogue_count + 1)
        ],
    )


def test_related_memory_prefers_relevance_before_importance():
    runtime = _runtime()
    runtime.turn_log.append(
        TurnLogEntry(
            turn=1, target="unrelated", summary="중요하지만 무관합니다.", importance=3
        )
    )
    runtime.turn_log.append(
        TurnLogEntry(
            turn=2,
            target="npc_merchant",
            summary="상인이 장부를 잃어버렸습니다.",
            importance=2,
        )
    )

    payload = related_memory_payload(
        runtime,
        action=None,
        target=runtime.graph.nodes["npc_merchant"],
        limit=1,
    )

    assert payload == [
        {
            "turn": 2,
            "target": "npc_merchant",
            "summary": "상인이 장부를 잃어버렸습니다.",
            "importance": 2,
        }
    ]


def test_recent_dialogue_is_limited_and_does_not_pull_turn_log():
    runtime = _runtime(dialogue_count=7)
    runtime.turn_log.append(
        TurnLogEntry(turn=99, target="npc_merchant", summary="중요 기억", importance=3)
    )

    payload = classify_recent_dialogue_payload(runtime)

    assert len(payload) == 5
    assert all(set(item) == {"turn", "player", "summary"} for item in payload)
    assert payload[0]["turn"] == 3
    assert "중요 기억" not in json.dumps(payload, ensure_ascii=False)


def test_recent_dialogue_limit_can_come_from_env(monkeypatch):
    monkeypatch.setenv("MAX_RECENT_DIALOGUE", "2")
    runtime = _runtime(dialogue_count=7)

    payload = classify_recent_dialogue_payload(runtime)

    assert [item["turn"] for item in payload] == [6, 7]


def test_narrate_recent_dialogue_uses_narrator_original_text(monkeypatch):
    monkeypatch.setenv("MAX_RECENT_DIALOGUE", "2")
    runtime = _runtime(dialogue_count=3)

    payload = narrate_recent_dialogue_payload(runtime)

    assert payload == [
        {"turn": 2, "player": "질문 2", "narrator": "응답 2", "target": None},
        {"turn": 3, "player": "질문 3", "narrator": "응답 3", "target": None},
    ]


def test_narrate_recent_dialogue_prefers_same_target_then_fills_recent(monkeypatch):
    monkeypatch.setenv("MAX_RECENT_DIALOGUE", "3")
    runtime = _runtime()
    runtime.recent_dialogue = [
        DialoguePair(
            turn=1, player="상인 질문", narrator="상인 답", target="npc_merchant"
        ),
        DialoguePair(
            turn=2, player="다른 질문", narrator="다른 답", target="npc_other"
        ),
        DialoguePair(
            turn=3, player="상인 재질문", narrator="상인 재답", target="npc_merchant"
        ),
        DialoguePair(
            turn=4, player="마지막 질문", narrator="마지막 답", target=None
        ),
    ]

    payload = narrate_recent_dialogue_payload(runtime, target="npc_merchant")

    assert [item["turn"] for item in payload] == [1, 3, 4]
    assert payload[1]["target"] == "npc_merchant"


def test_related_memory_limit_can_come_from_env(monkeypatch):
    monkeypatch.setenv("MAX_NARRATE_RELATED_MEMORY", "1")
    runtime = _runtime()
    runtime.turn_log.extend(
        [
            TurnLogEntry(
                turn=1, target="npc_merchant", summary="첫 기억", importance=2
            ),
            TurnLogEntry(
                turn=2, target="npc_merchant", summary="둘째 기억", importance=2
            ),
        ]
    )

    payload = related_memory_payload(
        runtime,
        action=None,
        target=runtime.graph.nodes["npc_merchant"],
    )

    assert len(payload) == 1


def test_related_memory_default_limit_matches_plan():
    runtime = _runtime()
    runtime.turn_log.extend(
        [
            TurnLogEntry(
                turn=turn,
                target="npc_merchant",
                summary=f"기억 {turn}",
                importance=2,
            )
            for turn in range(1, 18)
        ]
    )

    payload = related_memory_payload(
        runtime,
        action=None,
        target=runtime.graph.nodes["npc_merchant"],
    )

    assert len(payload) == 15
