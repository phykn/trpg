import json

from src.game.domain.action import Action
from src.game.domain.combat import GraphCombatState, GraphCombatTraceEvent
from src.game.domain.graph import Graph, GraphEdge, GraphNode
from src.game.domain.memory import ExchangePair, GMLogEntry
from src.game.domain.progress import GameProgress
from src.game.runtime import GameRuntimeState
from src.game.runtime.narration.context import build_input_narration_payload
from src.llm.context.classify_view import build_classify_context_view


FORBIDDEN_CONTEXT_TOKENS = [
    "recent_log",
    "combat_started",
    "player_attack_success",
    "player_defend_success",
    "player_flee_success",
    "enemy_pressed",
    "enemy_defeated",
    "forced_end",
    "critical",
    "hurt",
    "healthy",
    '"hp"',
    '"damage"',
]

CLASSIFY_FORBIDDEN_CONTEXT_TOKENS = [
    *FORBIDDEN_CONTEXT_TOKENS,
    "GM 원문",
]


def _character(node_id: str, *, name: str) -> GraphNode:
    return GraphNode(
        id=node_id,
        type="character",
        properties={
            "name": name,
            "description": f"{name} 설명은 LLM payload에 들어가면 안 됩니다.",
            "hp": 10,
            "max_hp": 10,
            "alive": True,
        },
    )


def _runtime(
    *,
    with_combat: bool = False,
    visible_character_count: int = 1,
    inventory_count: int = 1,
    skill_count: int = 1,
    dialogue_count: int = 1,
) -> GameRuntimeState:
    nodes: dict[str, GraphNode] = {
        "town": GraphNode(
            id="town",
            type="location",
            properties={"name": "마을", "description": "마을 설명은 넓은 원문입니다."},
        ),
        "forest": GraphNode(id="forest", type="location", properties={"name": "숲"}),
        "player_01": _character("player_01", name="당신"),
    }
    edges: dict[str, GraphEdge] = {
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
    }
    for index in range(visible_character_count):
        node_id = f"npc_{index}"
        nodes[node_id] = _character(node_id, name=f"상대 {index}")
        edges[f"located_at:{node_id}:town"] = GraphEdge(
            id=f"located_at:{node_id}:town",
            type="located_at",
            from_node_id=node_id,
            to_node_id="town",
        )
    for index in range(inventory_count):
        node_id = f"item_{index}"
        nodes[node_id] = GraphNode(
            id=node_id,
            type="item",
            properties={"name": f"물건 {index}", "description": "아이템 원문"},
        )
        edges[f"carries:player_01:{node_id}"] = GraphEdge(
            id=f"carries:player_01:{node_id}",
            type="carries",
            from_node_id="player_01",
            to_node_id=node_id,
        )
    for index in range(skill_count):
        node_id = f"skill_{index}"
        nodes[node_id] = GraphNode(
            id=node_id,
            type="skill",
            properties={"name": f"기술 {index}", "description": "기술 원문"},
        )
        edges[f"knows_skill:player_01:{node_id}"] = GraphEdge(
            id=f"knows_skill:player_01:{node_id}",
            type="knows_skill",
            from_node_id="player_01",
            to_node_id=node_id,
        )

    progress = GameProgress(game_id="game-1", player_id="player_01")
    if with_combat:
        progress = progress.model_copy(
            update={
                "graph_combat_state": GraphCombatState(
                    location_id="town",
                    player_id="player_01",
                    active_enemy_id="npc_0",
                    enemy_ids=["npc_0"],
                    participant_ids=["player_01", "npc_0"],
                    sides={"player_01": "player", "npc_0": "enemy"},
                    round=2,
                    last_action="attack",
                    trace=[
                        GraphCombatTraceEvent(
                            kind="combat_started",
                            actor_id="npc_0",
                            target="player_01",
                            state="healthy",
                        ),
                        GraphCombatTraceEvent(
                            kind="player_attack_success",
                            actor_id="player_01",
                            target="npc_0",
                            state="hurt",
                        ),
                    ],
                )
            }
        )

    return GameRuntimeState(
        graph=Graph(nodes=nodes, edges=edges),
        progress=progress,
        log_entries=[GMLogEntry(id=1, kind="gm", text="GM 원문이 새면 실패합니다.")],
        recent_exchanges=[
            ExchangePair(turn=turn, player=f"질문 {turn}", narrator=f"요약 {turn}")
            for turn in range(1, dialogue_count + 1)
        ],
    )


def test_classify_context_forbidden_tokens():
    runtime = _runtime(with_combat=True)
    payload = json.dumps(
        build_classify_context_view(runtime, "공격합니다"),
        ensure_ascii=False,
    )

    for token in CLASSIFY_FORBIDDEN_CONTEXT_TOKENS:
        assert token not in payload


def test_narrate_context_forbidden_tokens():
    runtime = _runtime(with_combat=True)
    payload = json.dumps(
        build_input_narration_payload(
            runtime=runtime,
            player_input="대련을 계속합니다",
            action=Action(verb="attack", what="npc_0"),
            dialogue_target=None,
        ),
        ensure_ascii=False,
    )

    for token in FORBIDDEN_CONTEXT_TOKENS:
        assert token not in payload
    assert "GM 원문이 새면 실패합니다." in payload


def test_context_payloads_stay_compact():
    runtime = _runtime(
        visible_character_count=20,
        inventory_count=25,
        skill_count=20,
        dialogue_count=20,
    )

    classify_payload = json.dumps(
        build_classify_context_view(runtime, "말을 겁니다"),
        ensure_ascii=False,
    )
    narrate_payload = json.dumps(
        build_input_narration_payload(
            runtime=runtime,
            player_input="말을 겁니다",
            action=Action(verb="speak", what="npc_0"),
            dialogue_target=runtime.graph.nodes["npc_0"],
        ),
        ensure_ascii=False,
    )

    assert len(classify_payload) < 12000
    assert len(narrate_payload) < 12000
