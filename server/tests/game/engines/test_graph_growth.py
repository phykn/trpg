import pytest

from src.game.domain.graph import Graph, GraphEdge, GraphNode, apply_graph_change
from src.game.engines.graph_growth import (
    GraphGrowthError,
    plan_level_up,
    plan_skill_learn,
    plan_skill_level_up,
    plan_skill_upgrade,
    plan_xp_grant,
)
from src.game.engines.growth import calc_max_hp, calc_max_mp, xp_for_next_level


def _character(**properties) -> GraphNode:
    base = {
        "level": 1,
        "xp_pool": 1,
        "stats": {"body": 10, "agility": 10, "mind": 10, "presence": 10},
        "hp": 5,
        "max_hp": 5,
        "mp": 5,
        "max_mp": 5,
        "status": [],
    }
    base.update(properties)
    return GraphNode(id="player_01", type="character", properties=base)


def _graph(character: GraphNode | None = None) -> Graph:
    return Graph(
        nodes={
            "player_01": character or _character(),
            "fireball": GraphNode(id="fireball", type="skill", properties={}),
        }
    )


def _apply_all(graph: Graph, changes) -> Graph:
    for change in changes:
        graph = apply_graph_change(graph, change)
    return graph


def test_xp_grant_increments_pool():
    result = plan_xp_grant(_graph(), "player_01", 7)
    changed = _apply_all(_graph(), result.changes)

    assert result.kind == "xp_grant"
    assert changed.nodes["player_01"].properties["xp_pool"] == 8


def test_growth_formula_uses_ten_scale_and_level_cap():
    assert xp_for_next_level(1) == 1
    assert xp_for_next_level(9) == 9
    assert xp_for_next_level(10) == 0
    assert calc_max_hp(1) == 5
    assert calc_max_hp(6) == 10
    assert calc_max_hp(10) == 10
    assert calc_max_mp(1) == 5
    assert calc_max_mp(6) == 10
    assert calc_max_mp(10) == 10


def test_level_up_can_raise_max_hp_to_cap_10():
    graph = _graph()
    result = plan_level_up(graph, "player_01", growth={"kind": "max_hp"})
    changed = _apply_all(graph, result.changes)
    player = changed.nodes["player_01"].properties

    assert result.kind == "level_up"
    assert player["level"] == 2
    assert player["xp_pool"] == 0
    assert player["max_hp"] == 6
    assert player["hp"] == 6
    assert player["max_mp"] == 5


def test_level_up_can_raise_max_mp_to_cap_10():
    graph = _graph()
    result = plan_level_up(graph, "player_01", growth={"kind": "max_mp"})
    changed = _apply_all(graph, result.changes)
    player = changed.nodes["player_01"].properties

    assert player["level"] == 2
    assert player["max_hp"] == 5
    assert player["max_mp"] == 6
    assert player["mp"] == 6


def test_level_up_rejects_resource_cap_and_max_level():
    with pytest.raises(GraphGrowthError, match="max_hp already at cap"):
        plan_level_up(
            _graph(_character(max_hp=10)),
            "player_01",
            growth={"kind": "max_hp"},
        )

    with pytest.raises(GraphGrowthError, match="already at max level 10"):
        plan_level_up(
            _graph(_character(level=10, xp_pool=10)),
            "player_01",
            growth={"kind": "max_mp"},
        )


def test_level_up_rejects_insufficient_xp():
    graph = _graph(_character(xp_pool=0))

    with pytest.raises(GraphGrowthError, match="not enough xp"):
        plan_level_up(graph, "player_01", growth={"kind": "max_hp"})


def test_skill_learn_adds_learned_edge_at_tier_1():
    graph = _graph()
    result = plan_skill_learn(graph, "player_01", "fireball")
    changed = _apply_all(graph, result.changes)
    edge = changed.edges["knows_skill:learned:player_01:fireball"]

    assert result.kind == "skill_learn"
    assert edge.type == "knows_skill"
    assert edge.properties == {"source": "learned", "tier": 1}


def test_skill_learn_rejects_duplicate_known_skill():
    graph = _graph()
    graph.edges["knows_skill:learned:player_01:fireball"] = GraphEdge(
        id="knows_skill:learned:player_01:fireball",
        type="knows_skill",
        from_node_id="player_01",
        to_node_id="fireball",
        properties={"source": "learned", "tier": 1},
    )

    with pytest.raises(GraphGrowthError, match="already knows"):
        plan_skill_learn(graph, "player_01", "fireball")


def test_skill_learn_rejects_more_than_three_known_skills():
    graph = _graph()
    for index in range(3):
        skill_id = f"skill_{index}"
        graph.nodes[skill_id] = GraphNode(id=skill_id, type="skill", properties={})
        graph.edges[f"knows_skill:learned:player_01:{skill_id}"] = GraphEdge(
            id=f"knows_skill:learned:player_01:{skill_id}",
            type="knows_skill",
            from_node_id="player_01",
            to_node_id=skill_id,
            properties={"source": "learned", "tier": 1},
        )

    with pytest.raises(GraphGrowthError, match="skill slots full"):
        plan_skill_learn(graph, "player_01", "fireball")


def test_skill_upgrade_increments_tier_to_cap_3():
    graph = _graph()
    graph.edges["knows_skill:learned:player_01:fireball"] = GraphEdge(
        id="knows_skill:learned:player_01:fireball",
        type="knows_skill",
        from_node_id="player_01",
        to_node_id="fireball",
        properties={"source": "learned", "tier": 1},
    )

    result = plan_skill_upgrade(graph, "player_01", "fireball")
    changed = _apply_all(graph, result.changes)

    assert result.kind == "skill_upgrade"
    assert (
        changed.edges["knows_skill:learned:player_01:fireball"].properties["tier"] == 2
    )

    changed.edges["knows_skill:learned:player_01:fireball"].properties["tier"] = 3
    with pytest.raises(GraphGrowthError, match="already at tier 3"):
        plan_skill_upgrade(changed, "player_01", "fireball")


def test_skill_level_up_learns_or_upgrades_and_consumes_xp_once():
    graph = _graph()

    learn = plan_skill_level_up(
        graph,
        "player_01",
        learn_skill_id="fireball",
    )
    learned = _apply_all(graph, learn.changes)

    assert learned.nodes["player_01"].properties["level"] == 2
    assert learned.nodes["player_01"].properties["xp_pool"] == 0
    assert (
        learned.edges["knows_skill:learned:player_01:fireball"].properties["tier"] == 1
    )

    learned.nodes["player_01"].properties["xp_pool"] = xp_for_next_level(2)
    upgrade = plan_skill_level_up(
        learned,
        "player_01",
        upgrade_skill_id="fireball",
    )
    upgraded = _apply_all(learned, upgrade.changes)

    assert upgraded.nodes["player_01"].properties["level"] == 3
    assert (
        upgraded.edges["knows_skill:learned:player_01:fireball"].properties["tier"] == 2
    )


def test_growth_changes_are_individually_valid_graph_changes():
    graph = _graph()
    result = plan_level_up(graph, "player_01", growth={"kind": "max_hp"})

    for change in result.changes:
        graph = apply_graph_change(graph, change)

    assert graph.nodes["player_01"].properties["level"] == 2
