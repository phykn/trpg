import json

from src.game.domain.action import Action
from src.game.domain.combat import GraphCombatState, GraphCombatTraceEvent
from src.game.domain.graph import Graph, GraphEdge, GraphNode
from src.game.domain.memory import DialoguePair, GMLogEntry, TurnLogEntry
from src.game.domain.progress import GameProgress
from src.game.runtime import GameRuntimeState
from src.game.runtime.dispatch import GraphActionDispatchResult
from src.game.runtime.narration_context import (
    build_action_narration_payload,
    build_input_narration_payload,
    build_intro_narration_payload,
)


def _character(node_id: str, *, name: str) -> GraphNode:
    return GraphNode(
        id=node_id,
        type="character",
        properties={
            "name": name,
            "hp": 10,
            "max_hp": 10,
            "mp": 5,
            "max_mp": 5,
            "alive": True,
            "stats": {"body": 3, "agility": 2, "mind": 2, "presence": 2},
            "status": [],
        },
    )


def _runtime() -> GameRuntimeState:
    return GameRuntimeState(
        graph=Graph(
            nodes={
                "square": GraphNode(
                    id="square",
                    type="location",
                    properties={
                        "name": "광장",
                        "description": "차가운 돌바닥이 이어집니다.",
                    },
                ),
                "north_gate": GraphNode(
                    id="north_gate",
                    type="location",
                    properties={"name": "북문"},
                ),
                "player_01": _character("player_01", name="당신"),
                "guard_01": _character("guard_01", name="경비병"),
                "sword_01": GraphNode(
                    id="sword_01",
                    type="item",
                    properties={"name": "검", "kind": "weapon"},
                ),
            },
            edges={
                "located_at:player_01:square": GraphEdge(
                    id="located_at:player_01:square",
                    type="located_at",
                    from_node_id="player_01",
                    to_node_id="square",
                ),
                "located_at:guard_01:square": GraphEdge(
                    id="located_at:guard_01:square",
                    type="located_at",
                    from_node_id="guard_01",
                    to_node_id="square",
                ),
                "connects_to:square:north_gate": GraphEdge(
                    id="connects_to:square:north_gate",
                    type="connects_to",
                    from_node_id="square",
                    to_node_id="north_gate",
                ),
                "carries:player_01:sword_01": GraphEdge(
                    id="carries:player_01:sword_01",
                    type="carries",
                    from_node_id="player_01",
                    to_node_id="sword_01",
                ),
            },
        ),
        progress=GameProgress(game_id="game-1", player_id="player_01"),
        log_entries=[GMLogEntry(id=1, kind="gm", text="경비병이 북문을 지킵니다.")],
        turn_log=[
            TurnLogEntry(
                turn=1,
                target="guard_01",
                summary="경비병은 북문을 신경 씁니다.",
                importance=2,
            )
        ],
        recent_dialogue=[
            DialoguePair(
                turn=1,
                player="북문에 대해 묻습니다.",
                narrator="경비병은 북문 쪽을 봅니다.",
            )
        ],
    )


def test_intro_payload_contains_grounded_first_scene_context():
    payload = build_intro_narration_payload(_runtime())

    assert payload["player"]["name"] == "당신"
    assert payload["place"]["name"] == "광장"
    assert payload["place"]["description"] == "차가운 돌바닥이 이어집니다."
    assert payload["visible_targets"] == [
        {"id": "guard_01", "name": "경비병", "type": "npc"}
    ]
    assert payload["exits"] == [{"id": "north_gate", "name": "북문"}]
    assert payload["inventory"] == [
        {"id": "sword_01", "name": "검", "kind": "weapon"}
    ]


def test_input_payload_excludes_recent_log_and_keeps_player_input():
    runtime = _runtime()

    payload = build_input_narration_payload(
        runtime=runtime,
        player_input="경비병에게 북문을 묻습니다",
        action=Action(verb="speak", to="guard_01", how="friendly"),
        dialogue_target=runtime.graph.nodes["guard_01"],
    )
    encoded = json.dumps(payload, ensure_ascii=False)

    assert payload["player_input"] == "경비병에게 북문을 묻습니다"
    assert payload["current_event"]["kind"] == "dialogue"
    assert payload["target_view"]["id"] == "guard_01"
    assert "recent_log" not in payload
    assert "경비병이 북문을 지킵니다." not in encoded
    assert payload["recent_dialogue"] == [
        {
            "turn": 1,
            "player": "북문에 대해 묻습니다.",
            "summary": "경비병은 북문 쪽을 봅니다.",
        }
    ]


def test_action_payload_contains_safe_current_event_and_combat_view():
    runtime = _runtime()
    dispatch = GraphActionDispatchResult(
        runtime=runtime,
        kind="combat",
        applied=1,
        changed_node_ids=["guard_01"],
        changed_edge_ids=[],
        removed_edge_ids=[],
        outcome="ongoing",
        combat_trace=[
            GraphCombatTraceEvent(
                kind="player_attacked",
                actor_id="player_01",
                target_id="guard_01",
                state="hurt",
            )
        ],
    )

    payload = build_action_narration_payload(
        before=runtime,
        after=runtime,
        action=Action(verb="attack", what="guard_01"),
        dispatch=dispatch,
        card_texts=["전투가 이어집니다."],
    )

    encoded = json.dumps(payload, ensure_ascii=False)

    assert payload["player_input"] is None
    assert payload["current_event"]["kind"] == "combat"
    assert payload["current_event"]["outcome"] == "ongoing"
    assert payload["result_cards"] == [{"text": "전투가 이어집니다."}]
    assert "recent_log" not in payload
    assert payload["combat_view"]["kind"] == "combat_exchange"
    assert payload["combat_view"]["events"]
    assert "player_attacked" not in encoded
    assert "hurt" not in encoded
    assert "damage" not in encoded
    assert "hp" not in encoded.lower()


def test_action_payload_keeps_terminal_combat_trace_after_state_clears():
    before = _runtime().model_copy(
        update={
            "progress": _runtime().progress.model_copy(
                update={
                    "graph_combat_state": GraphCombatState(
                        location_id="square",
                        player_id="player_01",
                        enemy_ids=["guard_01"],
                        participant_ids=["player_01", "guard_01"],
                        sides={"player_01": "player", "guard_01": "enemy"},
                        round=2,
                    )
                }
            )
        }
    )
    after = before.model_copy(
        update={
            "progress": before.progress.model_copy(update={"graph_combat_state": None})
        }
    )
    dispatch = GraphActionDispatchResult(
        runtime=after,
        kind="combat",
        applied=1,
        changed_node_ids=["guard_01"],
        changed_edge_ids=[],
        removed_edge_ids=[],
        outcome="victory",
        combat_trace=[
            GraphCombatTraceEvent(
                kind="enemy_defeated",
                actor_id="player_01",
                target_id="guard_01",
                state="downed",
            )
        ],
    )

    payload = build_action_narration_payload(
        before=before,
        after=after,
        action=Action(verb="attack", what="guard_01"),
        dispatch=dispatch,
        card_texts=["전투가 끝납니다."],
    )
    encoded = json.dumps(payload["combat_view"], ensure_ascii=False)

    assert payload["combat_view"]["outcome"] == "victory"
    assert payload["combat_view"]["events"]
    assert "enemy_defeated" not in encoded
    assert "downed" not in encoded
