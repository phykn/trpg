import pytest

from src.game.domain.action import Action
from src.game.domain.combat import GraphCombatState
from src.game.domain.graph import Graph, GraphEdge, GraphNode
from src.game.domain.progress import GameProgress
from src.game.runtime import GameRuntimeState
from src.game.runtime.action.combat import (
    GraphCombatDispatchError,
    dispatch_graph_combat_action,
)


def _character(
    character_id: str,
    *,
    hp: int = 5,
    max_hp: int = 5,
    mp: int = 5,
    max_mp: int = 5,
    level: int = 1,
) -> GraphNode:
    return GraphNode(
        id=character_id,
        type="character",
        properties={
            "name": character_id,
            "gold": 0,
            "xp_pool": 0,
            "hp": hp,
            "max_hp": max_hp,
            "mp": mp,
            "max_mp": max_mp,
            "level": level,
            "alive": hp > 0,
            "stats": {"body": 3, "agility": 2, "mind": 3, "presence": 2},
            "status": [],
        },
    )


def _enemy(character_id: str = "goblin_01", *, level: int = 1) -> GraphNode:
    node = _character(character_id, level=level)
    for key in ("hp", "max_hp", "mp", "max_mp"):
        node.properties.pop(key)
    return node


def _skill(skill_id: str = "fireball") -> GraphNode:
    return GraphNode(
        id=skill_id,
        type="skill",
        properties={
            "name": skill_id,
            "action": "attack",
            "mp_cost": 2,
            "support_bonus": 2,
            "effect_template": "dc_down",
        },
    )


def _item(item_id: str = "bomb") -> GraphNode:
    return GraphNode(
        id=item_id,
        type="item",
        properties={
            "name": item_id,
            "support_action": "attack",
            "effect_template": "extra_heart_damage",
            "consumable": True,
        },
    )


@pytest.fixture(autouse=True)
def _fixed_combat_roll(monkeypatch):
    monkeypatch.setattr("src.game.engines.graph.combat.randint", lambda _a, _b: 11)


def _runtime(
    *,
    enemy: GraphNode | None = None,
    include_skill: bool = False,
    include_item: bool = False,
    graph_combat_state: GraphCombatState | None = None,
) -> GameRuntimeState:
    nodes = {
        "town_gate": GraphNode(id="town_gate", type="location", properties={}),
        "player_01": _character("player_01"),
        "goblin_01": enemy or _enemy(),
    }
    if include_skill:
        nodes["fireball"] = _skill()
    if include_item:
        nodes["bomb"] = _item()
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
    if include_item:
        edges["carries:player_01:bomb"] = GraphEdge(
            id="carries:player_01:bomb",
            type="carries",
            from_node_id="player_01",
            to_node_id="bomb",
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
        active_enemy_id="goblin_01",
        enemy_ids=["goblin_01"],
        participant_ids=["player_01", "goblin_01"],
        sides={"player_01": "player", "goblin_01": "enemy"},
        player_hearts=3,
        enemy_hearts=3,
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
    assert result.runtime.progress.graph_combat_state.enemy_hearts == 2
    assert "hp" not in result.runtime.graph.nodes["goblin_01"].properties
    assert result.runtime.graph.nodes["player_01"].properties["hp"] == 5
    assert runtime.progress.graph_combat_state is None
    assert "hp" not in runtime.graph.nodes["goblin_01"].properties


def test_attack_with_weapon_id_starts_as_basic_attack():
    runtime = _runtime()
    runtime.graph.nodes["practice_dagger"] = GraphNode(
        id="practice_dagger",
        type="item",
        properties={"name": "훈련 단검"},
    )

    result = dispatch_graph_combat_action(
        runtime,
        Action(verb="attack", what="goblin_01", with_="practice_dagger"),
    )

    assert result.started is True
    assert result.outcome == "ongoing"
    assert result.runtime.progress.graph_combat_state is not None
    assert result.runtime.progress.graph_combat_state.enemy_hearts == 2


def test_attack_with_carried_item_uses_item_support_and_consumes_it():
    runtime = _runtime(include_item=True)

    result = dispatch_graph_combat_action(
        runtime,
        Action(verb="attack", what="goblin_01", with_="bomb"),
    )

    assert result.runtime.progress.graph_combat_state is not None
    assert result.runtime.progress.graph_combat_state.enemy_hearts == 1
    assert "carries:player_01:bomb" not in result.runtime.graph.edges


def test_attack_can_finish_existing_combat_and_clear_progress():
    runtime = _runtime(
        graph_combat_state=_ongoing_state(round_no=3).model_copy(
            update={"enemy_hearts": 1}
        ),
    )

    result = dispatch_graph_combat_action(
        runtime,
        Action(verb="attack", what="goblin_01"),
    )

    assert result.started is False
    assert result.outcome == "victory"
    assert result.runtime.progress.graph_combat_state is None
    enemy = result.runtime.graph.nodes["goblin_01"].properties
    assert "hp" not in enemy
    assert enemy["alive"] is False
    assert enemy["defeat_mode"] == "dead"
    assert "dead" in enemy["status"]


def test_victory_completes_matching_active_quest_and_clears_active_id():
    runtime = _runtime(
        graph_combat_state=_ongoing_state(round_no=3).model_copy(
            update={"enemy_hearts": 1}
        ),
    )
    runtime.graph.nodes["quest_01"] = GraphNode(
        id="quest_01",
        type="quest",
        properties={
            "status": "active",
            "rewards": {"gold": 5, "exp": 10, "items": ["reward_sword"]},
            "triggers": [
                {
                    "id": "trigger_01",
                    "name": "고블린 물리치기",
                    "type": "character_death",
                    "target_id": "goblin_01",
                }
            ],
            "triggers_met": [False],
        },
    )
    runtime.graph.nodes["reward_sword"] = GraphNode(
        id="reward_sword",
        type="item",
        properties={"name": "보상 검"},
    )
    runtime.graph.edges["reward_of:reward_sword:quest_01"] = GraphEdge(
        id="reward_of:reward_sword:quest_01",
        type="reward_of",
        from_node_id="reward_sword",
        to_node_id="quest_01",
    )
    runtime = runtime.model_copy(
        update={
            "progress": runtime.progress.model_copy(
                update={"active_quest_id": "quest_01"}
            )
        }
    )

    result = dispatch_graph_combat_action(
        runtime,
        Action(verb="attack", what="goblin_01"),
    )

    quest = result.runtime.graph.nodes["quest_01"].properties
    assert quest["triggers_met"] == [True]
    assert quest["status"] == "completed"
    player = result.runtime.graph.nodes["player_01"].properties
    assert player["gold"] == 5
    assert player["xp_pool"] == 10
    assert "reward_of:reward_sword:quest_01" not in result.runtime.graph.edges
    assert "carries:player_01:reward_sword" in result.runtime.graph.edges
    assert result.runtime.progress.active_quest_id is None


def test_flee_clears_existing_graph_combat_state_without_graph_changes():
    runtime = _runtime(graph_combat_state=_ongoing_state())

    result = dispatch_graph_combat_action(
        runtime,
        Action(verb="move", how="hasty"),
    )

    assert result.outcome == "fled"
    assert result.runtime.progress.graph_combat_state is None
    assert result.applied == 0
    assert result.runtime.graph == runtime.graph


def test_pass_maps_to_defend_and_advances_round():
    runtime = _runtime(
        graph_combat_state=_ongoing_state(),
    )

    result = dispatch_graph_combat_action(
        runtime,
        Action(verb="pass", how="defend"),
    )

    assert result.outcome == "ongoing"
    assert result.runtime.progress.graph_combat_state.round == 3
    assert result.runtime.progress.graph_combat_state.player_hearts == 3
    assert result.runtime.graph.nodes["player_01"].properties["hp"] == 5


def test_cast_starts_combat_and_deducts_mp():
    runtime = _runtime(include_skill=True)

    result = dispatch_graph_combat_action(
        runtime,
        Action(verb="cast", what="fireball", to="goblin_01"),
    )

    assert result.started is True
    assert result.outcome == "ongoing"
    assert result.runtime.graph.nodes["player_01"].properties["mp"] == 3
    assert result.runtime.progress.graph_combat_state is not None
    assert result.runtime.progress.graph_combat_state.enemy_hearts == 2


def test_unsupported_action_raises_dispatch_error():
    with pytest.raises(GraphCombatDispatchError, match="cannot start"):
        dispatch_graph_combat_action(_runtime(), Action(verb="rest"))

    with pytest.raises(GraphCombatDispatchError, match="unsupported"):
        dispatch_graph_combat_action(
            _runtime(graph_combat_state=_ongoing_state()),
            Action(verb="speak", what="goblin_01"),
        )
