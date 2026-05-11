from src.game.domain.action import Action
from src.game.domain.combat import GraphCombatTraceEvent
from src.game.domain.graph import Graph, GraphEdge, GraphNode
from src.game.domain.memory import GMLogEntry
from src.game.domain.progress import GameProgress
from src.game.runtime import GameRuntimeState
from src.game.runtime.dispatch import GraphActionDispatchResult
from src.game.runtime.narration_context import (
    build_action_narration_payload,
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


def test_action_payload_contains_recent_log_and_named_combat_trace():
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

    assert payload["action"]["verb"] == "attack"
    assert payload["resolved_results"] == ["전투가 이어집니다."]
    assert payload["recent_log"] == [
        {"kind": "gm", "text": "경비병이 북문을 지킵니다."}
    ]
    assert payload["combat"]["trace"] == [
        {
            "kind": "player_attacked",
            "actor": {"id": "player_01", "name": "당신"},
            "target": {"id": "guard_01", "name": "경비병"},
            "state": "hurt",
        }
    ]
