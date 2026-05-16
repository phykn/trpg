import pytest
from src.game.domain.graph import Graph, GraphEdge, GraphNode
from src.game.domain.progress import GameProgress
from src.game.engines.graph.rest import GraphRestError, plan_rest, plan_safe_rest
from src.game.rules import RULES
from src.game.runtime import GameRuntimeState
from src.game.runtime.action.apply import apply_runtime_graph_changes


def _runtime(
    *,
    gold: int | None = None,
    sleep_risk: str = "safe",
    include_actor: bool = True,
) -> GameRuntimeState:
    if gold is None:
        gold = RULES.recovery.cost_gold + 5
    nodes = {
        "inn": GraphNode(
            id="inn",
            type="location",
            properties={
                "sleep_risk": sleep_risk,
                "sleep_encounters": ["goblin_01"],
            },
        )
    }
    if include_actor:
        nodes["player_01"] = GraphNode(
            id="player_01",
            type="character",
            properties={
                "alive": True,
                "hp": 3,
                "max_hp": 20,
                "mp": 1,
                "max_mp": 10,
                "gold": gold,
            },
        )
        nodes["goblin_01"] = GraphNode(
            id="goblin_01",
            type="character",
            properties={
                "alive": True,
                "hp": 12,
                "max_hp": 12,
                "mp": 0,
                "max_mp": 0,
                "stats": {"body": 3, "agility": 1, "mind": 1, "presence": 1},
                "status": [],
            },
        )
    edges = {}
    if include_actor:
        edges["located_at:player_01:inn"] = GraphEdge(
            id="located_at:player_01:inn",
            type="located_at",
            from_node_id="player_01",
            to_node_id="inn",
        )
        edges["located_at:goblin_01:inn"] = GraphEdge(
            id="located_at:goblin_01:inn",
            type="located_at",
            from_node_id="goblin_01",
            to_node_id="inn",
        )
    return GameRuntimeState(
        graph=Graph(nodes=nodes, edges=edges),
        progress=GameProgress(game_id="game-1", player_id="player_01", turn_count=13),
    )


def test_safe_rest_restores_hp_mp_and_deducts_gold():
    runtime = _runtime()
    result = plan_safe_rest(runtime, "player_01")
    applied = apply_runtime_graph_changes(runtime, result.changes)
    player = applied.runtime.graph.nodes["player_01"].properties

    assert result.kind == "full_recovery"
    assert player["hp"] == 20
    assert player["mp"] == 10
    assert player["gold"] == 5


def test_safe_rest_advances_one_turn_without_time_phase():
    runtime = _runtime()
    result = plan_safe_rest(runtime, "player_01")

    assert result.next_turn_count == runtime.progress.turn_count + 1


def test_unsafe_location_is_rejected():
    with pytest.raises(GraphRestError, match="unsafe"):
        plan_safe_rest(_runtime(sleep_risk="dangerous"), "player_01")


def test_risky_rest_starts_listed_encounter_without_recovery():
    runtime = _runtime(sleep_risk="dangerous")

    result = plan_rest(runtime, "player_01")

    assert result.kind == "encounter"
    assert result.encounter_id == "goblin_01"
    assert result.changes == []
    assert result.state is not None
    assert result.state.enemy_ids == ["goblin_01"]


def test_insufficient_gold_is_rejected():
    with pytest.raises(GraphRestError, match="gold"):
        plan_safe_rest(_runtime(gold=RULES.recovery.cost_gold - 1), "player_01")


def test_missing_actor_is_rejected():
    with pytest.raises(GraphRestError, match="missing character"):
        plan_safe_rest(_runtime(include_actor=False), "player_01")


def test_dead_actor_is_rejected():
    runtime = _runtime()
    runtime.graph.nodes["player_01"].properties["alive"] = False

    with pytest.raises(GraphRestError, match="dead"):
        plan_safe_rest(runtime, "player_01")
