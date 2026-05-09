import pytest

from src.game.domain.graph import Graph, GraphEdge, GraphNode, apply_graph_change
from src.game.engines.graph_growth import (
    GraphGrowthError,
    plan_level_up,
    plan_skill_learn,
    plan_xp_grant,
)
from src.game.engines.growth import calc_max_hp, calc_max_mp, xp_for_next_level


def _character(**properties) -> GraphNode:
    base = {
        "level": 1,
        "xp_pool": xp_for_next_level(1),
        "stats": {"body": 10, "agility": 10, "mind": 10, "presence": 10},
        "hp": 12,
        "max_hp": calc_max_hp(1, 10),
        "mp": 4,
        "max_mp": calc_max_mp(1, 10),
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
    assert changed.nodes["player_01"].properties["xp_pool"] == xp_for_next_level(1) + 7


def test_level_up_applies_pair_trade_and_recalculates_resources():
    graph = _graph()
    result = plan_level_up(graph, "player_01", "body")
    changed = _apply_all(graph, result.changes)
    player = changed.nodes["player_01"].properties

    assert result.kind == "level_up"
    assert player["xp_pool"] == 0
    assert player["level"] == 2
    assert player["stats"] == {"body": 11, "agility": 10, "mind": 10, "presence": 10}
    assert player["max_hp"] == calc_max_hp(2, 11)
    assert player["max_mp"] == calc_max_mp(2, 10)


def test_level_up_rejects_insufficient_xp():
    graph = _graph(_character(xp_pool=0))

    with pytest.raises(GraphGrowthError, match="not enough xp"):
        plan_level_up(graph, "player_01", "body")


def test_level_up_rejects_capped_pair_trade():
    graph = _graph(
        _character(
            stats={
                "body": 20,
                "agility": 10,
                "mind": 10,
                "presence": 10,
            }
        )
    )

    with pytest.raises(GraphGrowthError, match="cap"):
        plan_level_up(graph, "player_01", "body")


def test_skill_learn_adds_learned_edge():
    graph = _graph()
    result = plan_skill_learn(graph, "player_01", "fireball")
    changed = _apply_all(graph, result.changes)
    edge = changed.edges["knows_skill:learned:player_01:fireball"]

    assert result.kind == "skill_learn"
    assert edge.type == "knows_skill"
    assert edge.properties == {"source": "learned"}


def test_skill_learn_rejects_duplicate_known_skill():
    graph = _graph()
    graph.edges["knows_skill:learned:player_01:fireball"] = GraphEdge(
        id="knows_skill:learned:player_01:fireball",
        type="knows_skill",
        from_node_id="player_01",
        to_node_id="fireball",
        properties={"source": "learned"},
    )

    with pytest.raises(GraphGrowthError, match="already knows"):
        plan_skill_learn(graph, "player_01", "fireball")


def test_growth_changes_are_individually_valid_graph_changes():
    graph = _graph()
    result = plan_level_up(graph, "player_01", "body")

    for change in result.changes:
        graph = apply_graph_change(graph, change)

    assert graph.nodes["player_01"].properties["level"] == 2
