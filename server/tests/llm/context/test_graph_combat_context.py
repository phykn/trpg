import pytest

from src.game.domain.graph import Graph, GraphEdge, GraphNode
from src.game.domain.graph.apply import apply_graph_change
from src.game.engines.graph.combat import (
    GraphCombatAction,
    plan_combat_exchange,
    plan_combat_start,
)
from src.llm.context.graph_combat import (
    GraphCombatContextError,
    build_graph_combat_context,
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
        },
    )


def _graph() -> Graph:
    return Graph(
        nodes={
            "town_gate": GraphNode(id="town_gate", type="location", properties={}),
            "player_01": _character("player_01"),
            "goblin_01": _character("goblin_01", hp=24, max_hp=24, mp=0, max_mp=0),
        },
        edges={
            "located_at:player_01:town_gate": GraphEdge(
                id="located_at:player_01:town_gate",
                type="located_at",
                from_node_id="player_01",
                to_node_id="town_gate",
            ),
            "located_at:goblin_01:town_gate": GraphEdge(
                id="located_at:goblin_01:town_gate",
                type="located_at",
                from_node_id="goblin_01",
                to_node_id="town_gate",
            ),
        },
    )


def _apply_all(graph: Graph, changes) -> Graph:
    for change in changes:
        graph = apply_graph_change(graph, change)
    return graph


def _forbidden_keys(value) -> set[str]:
    forbidden = {"hp", "max_hp", "mp", "max_mp", "damage", "changes"}
    found: set[str] = set()
    if isinstance(value, dict):
        for key, child in value.items():
            if key in forbidden:
                found.add(key)
            found.update(_forbidden_keys(child))
    elif isinstance(value, list):
        for child in value:
            found.update(_forbidden_keys(child))
    return found


def test_build_graph_combat_context_exposes_state_words_without_raw_numbers():
    graph = _graph()
    state = plan_combat_start(graph, "player_01", "goblin_01").state
    result = plan_combat_exchange(
        graph,
        state,
        "player_01",
        GraphCombatAction(kind="precise"),
        dice=11,
    )
    changed = _apply_all(graph, result.changes)

    context = build_graph_combat_context(changed, result.state)
    dumped = context.model_dump()

    assert context.location_id == "town_gate"
    assert context.round == 2
    assert context.player_hearts == 3
    assert context.enemy_hearts == 2
    assert context.outcome == "ongoing"
    assert [participant.id for participant in context.participants] == [
        "player_01",
        "goblin_01",
    ]
    assert context.participants[0].hp_state == "healthy"
    assert context.participants[0].mp_state == "ready"
    assert context.participants[1].hp_state is None
    assert context.participants[1].mp_state is None
    assert context.trace[-1].kind == "player_precise_success"
    assert _forbidden_keys(dumped) == set()


def test_combat_context_exposes_hearts_not_damage_numbers():
    graph = _graph()
    state = plan_combat_start(graph, "player_01", "goblin_01").state.model_copy(
        update={"player_hearts": 2, "enemy_hearts": 1}
    )

    context = build_graph_combat_context(graph, state)

    assert context.player_hearts == 2
    assert context.enemy_hearts == 1
    assert context.round >= 1


def test_context_rejects_missing_participant():
    graph = _graph()
    state = plan_combat_start(graph, "player_01", "goblin_01").state
    del graph.nodes["goblin_01"]

    with pytest.raises(GraphCombatContextError, match="missing participant"):
        build_graph_combat_context(graph, state)
