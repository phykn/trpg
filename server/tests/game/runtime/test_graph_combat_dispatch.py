import pytest

from src.game.domain.action import Action
from src.game.domain.combat import GraphCombatState
from src.game.domain.graph import Graph, GraphEdge, GraphNode
from src.game.domain.progress import GameProgress
from src.game.runtime import GameRuntimeState
from src.game.runtime.combat import (
    GraphCombatDispatchError,
    dispatch_graph_combat_action,
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
            "stats": {"body": 3, "agility": 2, "mind": 3, "presence": 2},
            "status": [],
        },
    )


def _skill(skill_id: str = "fireball") -> GraphNode:
    return GraphNode(
        id=skill_id,
        type="skill",
        properties={
            "name": skill_id,
            "kind": "attack",
            "type": "attack",
            "mp_cost": 4,
            "power": 16,
        },
    )


def _runtime(
    *,
    enemy: GraphNode | None = None,
    include_skill: bool = False,
    graph_combat_state: GraphCombatState | None = None,
) -> GameRuntimeState:
    nodes = {
        "town_gate": GraphNode(id="town_gate", type="location", properties={}),
        "player_01": _character("player_01"),
        "goblin_01": enemy or _character("goblin_01", hp=24, max_hp=24),
    }
    if include_skill:
        nodes["fireball"] = _skill()
    edges = {
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
    }
    if include_skill:
        edges["knows_skill:player_01:fireball"] = GraphEdge(
            id="knows_skill:player_01:fireball",
            type="knows_skill",
            from_node_id="player_01",
            to_node_id="fireball",
        )
    return GameRuntimeState(
        graph=Graph(nodes=nodes, edges=edges),
        progress=GameProgress(
            game_id="game-1",
            player_id="player_01",
            graph_combat_state=graph_combat_state,
        ),
    )


def _ongoing_state(round_no: int = 2) -> GraphCombatState:
    return GraphCombatState(
        location_id="town_gate",
        player_id="player_01",
        enemy_ids=["goblin_01"],
        participant_ids=["player_01", "goblin_01"],
        sides={"player_01": "player", "goblin_01": "enemy"},
        round=round_no,
    )


def test_attack_starts_combat_applies_exchange_and_stores_progress():
    runtime = _runtime()

    result = dispatch_graph_combat_action(
        runtime,
        Action(verb="attack", what="goblin_01"),
    )

    assert result.started is True
    assert result.outcome == "ongoing"
    assert result.runtime.progress.graph_combat_state is not None
    assert result.runtime.progress.graph_combat_state.round == 2
    assert result.runtime.graph.nodes["goblin_01"].properties["hp"] < 24
    assert result.runtime.graph.nodes["player_01"].properties["hp"] < 30
    assert runtime.progress.graph_combat_state is None
    assert runtime.graph.nodes["goblin_01"].properties["hp"] == 24


def test_attack_can_finish_existing_combat_and_clear_progress():
    runtime = _runtime(
        enemy=_character("goblin_01", hp=8, max_hp=24),
        graph_combat_state=_ongoing_state(round_no=3),
    )

    result = dispatch_graph_combat_action(
        runtime,
        Action(verb="attack", what="goblin_01"),
    )

    assert result.started is False
    assert result.outcome == "victory"
    assert result.runtime.progress.graph_combat_state is None
    enemy = result.runtime.graph.nodes["goblin_01"].properties
    assert enemy["hp"] == 0
    assert enemy["defeat_mode"] == "unconscious"


def test_flee_clears_existing_graph_combat_state_without_graph_changes():
    runtime = _runtime(graph_combat_state=_ongoing_state())

    result = dispatch_graph_combat_action(
        runtime,
        Action(verb="move", how="flee"),
    )

    assert result.outcome == "fled"
    assert result.runtime.progress.graph_combat_state is None
    assert result.applied == 0
    assert result.runtime.graph == runtime.graph


def test_pass_maps_to_defend_and_advances_round():
    runtime = _runtime(
        enemy=_character("goblin_01", hp=80, max_hp=80),
        graph_combat_state=_ongoing_state(),
    )

    result = dispatch_graph_combat_action(
        runtime,
        Action(verb="pass", how="defend"),
    )

    assert result.outcome == "ongoing"
    assert result.runtime.progress.graph_combat_state.round == 3
    player_hp = result.runtime.graph.nodes["player_01"].properties["hp"]
    assert player_hp == 27


def test_cast_starts_combat_and_deducts_mp():
    runtime = _runtime(include_skill=True)

    result = dispatch_graph_combat_action(
        runtime,
        Action(verb="cast", what="fireball", to="goblin_01"),
    )

    assert result.started is True
    assert result.outcome == "ongoing"
    assert result.runtime.graph.nodes["player_01"].properties["mp"] == 6
    assert result.runtime.graph.nodes["goblin_01"].properties["hp"] == 8


def test_unsupported_action_raises_dispatch_error():
    with pytest.raises(GraphCombatDispatchError, match="cannot start"):
        dispatch_graph_combat_action(_runtime(), Action(verb="rest"))

    with pytest.raises(GraphCombatDispatchError, match="unsupported"):
        dispatch_graph_combat_action(
            _runtime(graph_combat_state=_ongoing_state()),
            Action(verb="speak", what="goblin_01"),
        )
