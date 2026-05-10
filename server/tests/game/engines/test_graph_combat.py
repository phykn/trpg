import pytest

from src.game.domain.graph import Graph, GraphEdge, GraphNode, apply_graph_change
from src.game.engines.graph_combat import (
    GraphCombatAction,
    GraphCombatError,
    GraphCombatState,
    plan_combat_exchange,
    plan_combat_start,
)


def _character(
    character_id: str,
    *,
    hp: int = 30,
    max_hp: int = 30,
    mp: int = 10,
    max_mp: int = 10,
    alive: bool = True,
    stats: dict | None = None,
    status: list[str] | None = None,
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
            "alive": alive,
            "stats": stats
            or {
                "body": 3,
                "agility": 2,
                "mind": 3,
                "presence": 2,
            },
            "status": status or [],
        },
    )


def _skill(skill_id: str, *, mp_cost: int = 4, power: int = 16) -> GraphNode:
    return GraphNode(
        id=skill_id,
        type="skill",
        properties={
            "name": skill_id,
            "kind": "attack",
            "type": "attack",
            "mp_cost": mp_cost,
            "power": power,
        },
    )


def _located(character_id: str, location_id: str = "town_gate") -> GraphEdge:
    return GraphEdge(
        id=f"located_at:{character_id}:{location_id}",
        type="located_at",
        from_node_id=character_id,
        to_node_id=location_id,
    )


def _graph(
    *,
    player: GraphNode | None = None,
    enemy: GraphNode | None = None,
    include_skill: bool = False,
    player_location: str = "town_gate",
    enemy_location: str = "town_gate",
) -> Graph:
    nodes = {
        "town_gate": GraphNode(id="town_gate", type="location", properties={}),
        "forest": GraphNode(id="forest", type="location", properties={}),
        "player_01": player or _character("player_01"),
        "goblin_01": enemy or _character("goblin_01", hp=24, max_hp=24),
    }
    if include_skill:
        nodes["fireball"] = _skill("fireball")
    edges = {
        f"located_at:player_01:{player_location}": _located(
            "player_01", player_location
        ),
        f"located_at:goblin_01:{enemy_location}": _located("goblin_01", enemy_location),
    }
    if include_skill:
        edges["knows_skill:player_01:fireball"] = GraphEdge(
            id="knows_skill:player_01:fireball",
            type="knows_skill",
            from_node_id="player_01",
            to_node_id="fireball",
        )
    return Graph(nodes=nodes, edges=edges)


def _apply_all(graph: Graph, changes) -> Graph:
    for change in changes:
        graph = apply_graph_change(graph, change)
    return graph


def _started(graph: Graph) -> GraphCombatState:
    return plan_combat_start(graph, "player_01", "goblin_01").state


def test_combat_start_builds_progress_without_graph_changes():
    result = plan_combat_start(_graph(), "player_01", "goblin_01")

    assert result.changes == []
    assert result.state.location_id == "town_gate"
    assert result.state.player_id == "player_01"
    assert result.state.enemy_ids == ["goblin_01"]
    assert result.state.participant_ids == ["player_01", "goblin_01"]
    assert result.state.sides == {"player_01": "player", "goblin_01": "enemy"}
    assert result.state.round == 1
    assert result.state.outcome == "ongoing"
    assert result.state.trace[-1].kind == "combat_started"


def test_combat_start_validates_target_and_location():
    with pytest.raises(GraphCombatError, match="missing character"):
        plan_combat_start(_graph(), "player_01", "ghost")

    graph = _graph()
    graph.nodes["stone"] = GraphNode(id="stone", type="item", properties={})
    graph.edges["located_at:stone:town_gate"] = GraphEdge(
        id="located_at:stone:town_gate",
        type="located_at",
        from_node_id="stone",
        to_node_id="town_gate",
    )
    with pytest.raises(GraphCombatError, match="not a character"):
        plan_combat_start(graph, "player_01", "stone")

    with pytest.raises(GraphCombatError, match="cannot fight"):
        plan_combat_start(
            _graph(player=_character("player_01", hp=0, max_hp=30)),
            "player_01",
            "goblin_01",
        )

    with pytest.raises(GraphCombatError, match="same location"):
        plan_combat_start(
            _graph(player_location="town_gate", enemy_location="forest"),
            "player_01",
            "goblin_01",
        )


def test_attack_exchange_changes_hp_and_advances_round():
    graph = _graph()
    state = _started(graph)

    result = plan_combat_exchange(
        graph,
        state,
        "player_01",
        GraphCombatAction(kind="attack"),
    )
    changed = _apply_all(graph, result.changes)

    assert changed.nodes["goblin_01"].properties["hp"] < 24
    assert changed.nodes["player_01"].properties["hp"] < 30
    assert result.state.round == 2
    assert result.state.outcome == "ongoing"
    assert all("damage" not in event.model_dump() for event in result.state.trace)


def test_three_ordinary_attacks_can_end_in_victory():
    graph = _graph()
    state = _started(graph)

    for _ in range(3):
        result = plan_combat_exchange(
            graph,
            state,
            "player_01",
            GraphCombatAction(kind="attack"),
        )
        graph = _apply_all(graph, result.changes)
        state = result.state
        if state.outcome != "ongoing":
            break

    enemy = graph.nodes["goblin_01"].properties
    assert state.outcome == "victory"
    assert enemy["hp"] == 0
    assert enemy["defeat_mode"] == "unconscious"
    assert "defeated" in enemy["status"]


def test_cast_requires_known_skill_and_deducts_mp():
    graph = _graph(include_skill=True)
    state = _started(graph)

    result = plan_combat_exchange(
        graph,
        state,
        "player_01",
        GraphCombatAction(kind="cast", skill_id="fireball"),
    )
    changed = _apply_all(graph, result.changes)

    assert changed.nodes["player_01"].properties["mp"] == 6
    assert changed.nodes["goblin_01"].properties["hp"] < 24

    no_skill_graph = _graph(include_skill=True)
    del no_skill_graph.edges["knows_skill:player_01:fireball"]
    with pytest.raises(GraphCombatError, match="does not know"):
        plan_combat_exchange(
            no_skill_graph,
            _started(no_skill_graph),
            "player_01",
            GraphCombatAction(kind="cast", skill_id="fireball"),
        )

    low_mp_graph = _graph(
        include_skill=True,
        player=_character("player_01", mp=1, max_mp=10),
    )
    with pytest.raises(GraphCombatError, match="not enough mp"):
        plan_combat_exchange(
            low_mp_graph,
            _started(low_mp_graph),
            "player_01",
            GraphCombatAction(kind="cast", skill_id="fireball"),
        )


def test_flee_ends_combat_without_graph_changes():
    graph = _graph()
    state = _started(graph)

    result = plan_combat_exchange(
        graph,
        state,
        "player_01",
        GraphCombatAction(kind="flee"),
    )

    assert result.changes == []
    assert result.state.outcome == "fled"
    assert result.state.trace[-1].kind == "player_fled"


def test_defend_reduces_incoming_hp_loss():
    graph = _graph(enemy=_character("goblin_01", hp=80, max_hp=80))
    state = _started(graph)

    attack_result = plan_combat_exchange(
        graph,
        state,
        "player_01",
        GraphCombatAction(kind="attack"),
    )
    after_attack = _apply_all(graph, attack_result.changes)

    defend_result = plan_combat_exchange(
        graph,
        state,
        "player_01",
        GraphCombatAction(kind="defend"),
    )
    after_defend = _apply_all(graph, defend_result.changes)

    attack_loss = 30 - after_attack.nodes["player_01"].properties["hp"]
    defend_loss = 30 - after_defend.nodes["player_01"].properties["hp"]
    assert defend_loss < attack_loss
    assert defend_result.state.round == 2


def test_fourth_exchange_forces_terminal_outcome():
    graph = _graph(enemy=_character("goblin_01", hp=200, max_hp=200))
    state = _started(graph).model_copy(update={"round": 4})

    result = plan_combat_exchange(
        graph,
        state,
        "player_01",
        GraphCombatAction(kind="defend"),
    )
    changed = _apply_all(graph, result.changes)

    assert result.state.round == 4
    assert result.state.outcome == "victory"
    assert changed.nodes["goblin_01"].properties["defeat_mode"] == "escaped"
    assert result.state.trace[-1].kind == "forced_end"


def test_exchange_changes_are_valid_graph_changes():
    graph = _graph(include_skill=True)
    result = plan_combat_exchange(
        graph,
        _started(graph),
        "player_01",
        GraphCombatAction(kind="cast", skill_id="fireball"),
    )

    for change in result.changes:
        graph = apply_graph_change(graph, change)

    assert graph.nodes["player_01"].properties["mp"] == 6
