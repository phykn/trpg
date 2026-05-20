from src.game.domain.action import Action
from src.game.domain.graph import Graph, GraphEdge, GraphNode
from src.game.domain.graph.apply import apply_graph_changes
from src.game.engines.graph.roll import (
    plan_roll_check,
    plan_roll_graph_effects,
    plan_roll_quest_trigger,
)
from src.game.rules import RULES


def _character(character_id: str) -> GraphNode:
    return GraphNode(
        id=character_id,
        type="character",
        properties={
            "name": character_id,
            "xp_pool": 0,
        },
    )


def _graph(*, affinity: int = 0, award_keys=None) -> Graph:
    player = _character("player_01")
    if award_keys is not None:
        player.properties["xp_award_keys"] = award_keys
    return Graph(
        nodes={
            "player_01": player,
            "guard_01": _character("guard_01"),
        },
        edges={
            "relation:guard_01:player_01": GraphEdge(
                id="relation:guard_01:player_01",
                type="relation",
                from_node_id="guard_01",
                to_node_id="player_01",
                properties={"affinity": affinity},
            ),
        },
    )


def test_roll_graph_effects_plan_relation_and_xp_changes():
    graph = _graph(affinity=0)

    result = plan_roll_graph_effects(
        graph,
        player_id="player_01",
        action=Action(verb="speak", to="guard_01", how="friendly"),
        grade="success",
        roll_outcome="success",
    )
    changed = apply_graph_changes(graph, result.changes)

    assert changed.edges["relation:guard_01:player_01"].properties["affinity"] == (
        RULES.social.affinity_success
    )
    assert changed.nodes["player_01"].properties["xp_pool"] == (
        RULES.growth.roll_xp["success"]
    )
    assert changed.nodes["player_01"].properties["xp_award_keys"] == [
        "roll:speak:guard_01"
    ]


def test_roll_graph_effects_skip_repeated_xp_award_key():
    graph = _graph(award_keys=["roll:perceive:town"])

    result = plan_roll_graph_effects(
        graph,
        player_id="player_01",
        action=Action(verb="perceive", what="town"),
        grade="success",
        roll_outcome="success",
    )
    changed = apply_graph_changes(graph, result.changes)

    assert changed.nodes["player_01"].properties["xp_pool"] == 0
    assert changed.nodes["player_01"].properties["xp_award_keys"] == [
        "roll:perceive:town"
    ]


def test_roll_check_plans_action_stat_and_affinity_dc():
    result = plan_roll_check(
        _graph(affinity=20),
        player_properties={"stats": {"presence": 10}},
        player_id="player_01",
        action=Action(verb="speak", to="guard_01", how="friendly"),
        base_dc=13,
    )

    assert result.stat == "presence"
    assert result.effective_dc == 11
    assert result.required_roll == 11


def test_roll_check_uses_transfer_steal_agility():
    result = plan_roll_check(
        _graph(),
        player_properties={"stats": {"agility": 3}},
        player_id="player_01",
        action=Action(
            verb="transfer",
            what="coin_01",
            from_="guard_01",
            to="player_01",
            how="steal",
        ),
        base_dc=13,
    )

    assert result.stat == "agility"
    assert result.required_roll == 17


def test_roll_quest_trigger_maps_social_success_to_target():
    trigger = plan_roll_quest_trigger(
        _graph(),
        player_id="player_01",
        action=Action(verb="speak", to="guard_01", how="friendly"),
    )

    assert trigger == ("social_check", "guard_01")


def test_roll_quest_trigger_ignores_transfer_modes_owned_elsewhere():
    trigger = plan_roll_quest_trigger(
        _graph(),
        player_id="player_01",
        action=Action(verb="transfer", what="coin_01", to="player_01", how="trade"),
    )

    assert trigger is None
