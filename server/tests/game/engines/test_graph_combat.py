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
    hp: int = 5,
    max_hp: int = 5,
    mp: int = 5,
    max_mp: int = 5,
    level: int = 1,
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
            "level": level,
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


def _skill(
    skill_id: str,
    *,
    action: str = "attack",
    mp_cost: int = 2,
    support_bonus: int = 2,
    effect_template: str = "dc_down",
) -> GraphNode:
    return GraphNode(
        id=skill_id,
        type="skill",
        properties={
            "name": skill_id,
            "action": action,
            "mp_cost": mp_cost,
            "support_bonus": support_bonus,
            "effect_template": effect_template,
        },
    )


def _item(
    item_id: str,
    *,
    action: str = "attack",
    support_bonus: int = 0,
    effect_template: str = "extra_heart_damage",
    consumable: bool = True,
) -> GraphNode:
    return GraphNode(
        id=item_id,
        type="item",
        properties={
            "name": item_id,
            "support_action": action,
            "support_bonus": support_bonus,
            "effect_template": effect_template,
            "consumable": consumable,
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
    include_item: bool = False,
    skill: GraphNode | None = None,
    item: GraphNode | None = None,
    player_location: str = "town_gate",
    enemy_location: str = "town_gate",
) -> Graph:
    nodes = {
        "town_gate": GraphNode(id="town_gate", type="location", properties={}),
        "forest": GraphNode(id="forest", type="location", properties={}),
        "player_01": player or _character("player_01"),
        "goblin_01": enemy or _character("goblin_01"),
    }
    if include_skill:
        nodes["focus"] = skill or _skill("focus")
    if include_item:
        nodes["bomb"] = item or _item("bomb")
    edges = {
        f"located_at:player_01:{player_location}": _located(
            "player_01", player_location
        ),
        f"located_at:goblin_01:{enemy_location}": _located("goblin_01", enemy_location),
    }
    if include_skill:
        edges["knows_skill:player_01:focus"] = GraphEdge(
            id="knows_skill:player_01:focus",
            type="knows_skill",
            from_node_id="player_01",
            to_node_id="focus",
        )
    if include_item:
        edges["carries:player_01:bomb"] = GraphEdge(
            id="carries:player_01:bomb",
            type="carries",
            from_node_id="player_01",
            to_node_id="bomb",
        )
    return Graph(nodes=nodes, edges=edges)


def _apply_all(graph: Graph, changes) -> Graph:
    for change in changes:
        graph = apply_graph_change(graph, change)
    return graph


def _started(graph: Graph) -> GraphCombatState:
    return plan_combat_start(graph, "player_01", "goblin_01").state


def test_combat_start_builds_heart_state_without_graph_changes():
    result = plan_combat_start(_graph(), "player_01", "goblin_01")

    assert result.changes == []
    assert result.state.location_id == "town_gate"
    assert result.state.player_id == "player_01"
    assert result.state.active_enemy_id == "goblin_01"
    assert result.state.enemy_ids == ["goblin_01"]
    assert result.state.participant_ids == ["player_01", "goblin_01"]
    assert result.state.sides == {"player_01": "player", "goblin_01": "enemy"}
    assert result.state.player_hearts == 3
    assert result.state.enemy_hearts == 3
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
            _graph(player=_character("player_01", hp=0, max_hp=5)),
            "player_01",
            "goblin_01",
        )

    with pytest.raises(GraphCombatError, match="same location"):
        plan_combat_start(
            _graph(player_location="town_gate", enemy_location="forest"),
            "player_01",
            "goblin_01",
        )


def test_attack_success_reduces_enemy_heart_without_hp_loss():
    graph = _graph()
    state = _started(graph)

    result = plan_combat_exchange(
        graph,
        state,
        "player_01",
        GraphCombatAction(kind="attack"),
        dice=11,
    )

    assert result.changes == []
    assert result.state.enemy_hearts == 2
    assert result.state.player_hearts == 3
    assert result.state.round == 2
    assert result.state.outcome == "ongoing"
    assert result.state.trace[-1].kind == "player_attack_success"


def test_attack_failure_reduces_player_heart_and_ignores_stats():
    graph = _graph(
        player=_character(
            "player_01",
            stats={"body": 99, "agility": 99, "mind": 99, "presence": 99},
        )
    )
    state = _started(graph)

    result = plan_combat_exchange(
        graph,
        state,
        "player_01",
        GraphCombatAction(kind="attack"),
        dice=10,
    )

    assert result.state.enemy_hearts == 3
    assert result.state.player_hearts == 2
    assert result.state.round == 2
    assert result.state.trace[-1].kind == "player_attack_failure"


def test_defend_success_recovers_a_player_heart():
    graph = _graph()
    state = _started(graph).model_copy(update={"player_hearts": 2})

    result = plan_combat_exchange(
        graph,
        state,
        "player_01",
        GraphCombatAction(kind="defend"),
        dice=11,
    )

    assert result.state.player_hearts == 3
    assert result.state.enemy_hearts == 3
    assert result.state.round == 2
    assert result.state.trace[-1].kind == "player_defend_success"


def test_defend_failure_loses_one_heart():
    graph = _graph()
    state = _started(graph)

    result = plan_combat_exchange(
        graph,
        state,
        "player_01",
        GraphCombatAction(kind="defend"),
        dice=10,
    )

    assert result.state.player_hearts == 2
    assert result.state.enemy_hearts == 3
    assert result.state.round == 2
    assert result.state.trace[-1].kind == "player_defend_failure"


def test_flee_success_ends_combat_without_graph_changes():
    graph = _graph()
    state = _started(graph)

    result = plan_combat_exchange(
        graph,
        state,
        "player_01",
        GraphCombatAction(kind="flee"),
        dice=11,
    )

    assert result.changes == []
    assert result.state.outcome == "fled"
    assert result.state.player_hearts == 3
    assert result.state.trace[-1].kind == "player_flee_success"


def test_flee_failure_loses_one_heart():
    graph = _graph()
    state = _started(graph)

    result = plan_combat_exchange(
        graph,
        state,
        "player_01",
        GraphCombatAction(kind="flee"),
        dice=10,
    )

    assert result.state.outcome == "ongoing"
    assert result.state.player_hearts == 2
    assert result.state.round == 2
    assert result.state.trace[-1].kind == "player_flee_failure"


def test_social_success_and_failure_use_hearts():
    graph = _graph()
    state = _started(graph)

    success = plan_combat_exchange(
        graph,
        state,
        "player_01",
        GraphCombatAction(kind="social"),
        dice=11,
    )
    failure = plan_combat_exchange(
        graph,
        state,
        "player_01",
        GraphCombatAction(kind="social"),
        dice=10,
    )

    assert success.state.enemy_hearts == 2
    assert success.state.trace[-1].kind == "player_social_success"
    assert failure.state.player_hearts == 2
    assert failure.state.trace[-1].kind == "player_social_failure"


def test_victory_marks_enemy_defeated_without_forced_round_limit():
    graph = _graph()
    state = _started(graph).model_copy(update={"enemy_hearts": 1, "round": 12})

    result = plan_combat_exchange(
        graph,
        state,
        "player_01",
        GraphCombatAction(kind="attack"),
        dice=11,
    )
    changed = _apply_all(graph, result.changes)

    enemy = changed.nodes["goblin_01"].properties
    assert result.state.round == 12
    assert result.state.outcome == "victory"
    assert result.state.enemy_hearts == 0
    assert enemy["hp"] == 5
    assert enemy["defeat_mode"] == "unconscious"
    assert "defeated" in enemy["status"]
    assert result.state.trace[-1].kind == "enemy_defeated"


def test_defeat_deducts_hp_by_remaining_enemy_hearts():
    graph = _graph()
    state = _started(graph).model_copy(update={"player_hearts": 1, "enemy_hearts": 2})

    result = plan_combat_exchange(
        graph,
        state,
        "player_01",
        GraphCombatAction(kind="attack"),
        dice=10,
    )
    changed = _apply_all(graph, result.changes)

    player = changed.nodes["player_01"].properties
    assert result.state.outcome == "defeat"
    assert result.state.player_hearts == 0
    assert player["hp"] == 3
    assert player["defeat_mode"] == "downed"
    assert "downed" in player["status"]
    assert result.state.trace[-1].kind == "player_downed"


def test_dc_uses_level_difference_support_bonus_and_clamp():
    graph = _graph(
        include_skill=True,
        enemy=_character("goblin_01", level=20),
        skill=_skill("focus", support_bonus=2),
    )
    state = _started(graph)

    fail_without_support = plan_combat_exchange(
        graph,
        state,
        "player_01",
        GraphCombatAction(kind="attack"),
        dice=17,
    )
    success_with_support = plan_combat_exchange(
        graph,
        state,
        "player_01",
        GraphCombatAction(
            kind="attack",
            support_id="focus",
            support_kind="skill",
        ),
        dice=18,
    )
    changed = _apply_all(graph, success_with_support.changes)

    assert fail_without_support.state.player_hearts == 2
    assert success_with_support.state.enemy_hearts == 2
    assert success_with_support.state.last_dc == 18
    assert changed.nodes["player_01"].properties["mp"] == 3


def test_skill_support_requires_known_skill_and_mp():
    graph = _graph(include_skill=True)
    state = _started(graph)

    no_skill_graph = _graph(include_skill=True)
    del no_skill_graph.edges["knows_skill:player_01:focus"]
    with pytest.raises(GraphCombatError, match="does not know"):
        plan_combat_exchange(
            no_skill_graph,
            _started(no_skill_graph),
            "player_01",
            GraphCombatAction(
                kind="attack",
                support_id="focus",
                support_kind="skill",
            ),
            dice=11,
        )

    low_mp_graph = _graph(
        include_skill=True,
        player=_character("player_01", mp=1, max_mp=5),
    )
    with pytest.raises(GraphCombatError, match="not enough mp"):
        plan_combat_exchange(
            low_mp_graph,
            _started(low_mp_graph),
            "player_01",
            GraphCombatAction(
                kind="attack",
                support_id="focus",
                support_kind="skill",
            ),
            dice=11,
        )

    mismatch_graph = _graph(
        include_skill=True,
        skill=_skill("focus", action="defend"),
    )
    with pytest.raises(GraphCombatError, match="does not support action"):
        plan_combat_exchange(
            mismatch_graph,
            state,
            "player_01",
            GraphCombatAction(
                kind="attack",
                support_id="focus",
                support_kind="skill",
            ),
            dice=11,
        )


def test_item_support_can_consume_and_deal_extra_heart_damage():
    graph = _graph(include_item=True)
    state = _started(graph)

    result = plan_combat_exchange(
        graph,
        state,
        "player_01",
        GraphCombatAction(
            kind="attack",
            support_id="bomb",
            support_kind="item",
        ),
        dice=11,
    )
    changed = _apply_all(graph, result.changes)

    assert result.state.enemy_hearts == 1
    assert "carries:player_01:bomb" not in changed.edges


def test_guard_item_can_prevent_failure_heart_loss():
    graph = _graph(
        include_item=True,
        item=_item(
            "bomb",
            action="defend",
            effect_template="prevent_heart_loss",
            consumable=True,
        ),
    )
    state = _started(graph)

    result = plan_combat_exchange(
        graph,
        state,
        "player_01",
        GraphCombatAction(
            kind="defend",
            support_id="bomb",
            support_kind="item",
        ),
        dice=10,
    )
    changed = _apply_all(graph, result.changes)

    assert result.state.player_hearts == 3
    assert result.state.trace[-1].kind == "player_defend_failure"
    assert "carries:player_01:bomb" not in changed.edges


def test_exchange_changes_are_valid_graph_changes():
    graph = _graph(include_skill=True, include_item=True)
    result = plan_combat_exchange(
        graph,
        _started(graph),
        "player_01",
        GraphCombatAction(
            kind="attack",
            support_id="focus",
            support_kind="skill",
        ),
        dice=11,
    )

    for change in result.changes:
        graph = apply_graph_change(graph, change)

    assert graph.nodes["player_01"].properties["mp"] == 3
