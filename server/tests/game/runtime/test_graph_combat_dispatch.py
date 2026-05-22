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
            "bonus": 2,
        },
    )


def _item(item_id: str = "bomb") -> GraphNode:
    return GraphNode(
        id=item_id,
        type="item",
        properties={
            "name": item_id,
            "action": "attack",
            "effect": "dc_down",
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


def test_attack_starts_combat_without_spending_first_exchange():
    runtime = _runtime()

    result = dispatch_graph_combat_action(
        runtime,
        Action(verb="attack", what="goblin_01"),
    )

    assert result.started is True
    assert result.outcome == "ongoing"
    assert result.runtime.progress.graph_combat_state is not None
    assert result.runtime.progress.graph_combat_state.round == 1
    assert result.runtime.progress.graph_combat_state.enemy_hearts == 3
    assert result.runtime.progress.graph_combat_state.last_roll is None
    assert "hp" not in result.runtime.graph.nodes["goblin_01"].properties
    assert result.runtime.graph.nodes["player_01"].properties["hp"] == 5
    assert runtime.progress.graph_combat_state is None
    assert "hp" not in runtime.graph.nodes["goblin_01"].properties


def test_attack_with_weapon_id_starts_combat_without_exchange():
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
    assert result.runtime.progress.graph_combat_state.round == 1
    assert result.runtime.progress.graph_combat_state.enemy_hearts == 3
    assert result.runtime.progress.graph_combat_state.last_roll is None


def test_attack_with_carried_item_does_not_consume_support_on_start():
    runtime = _runtime(include_item=True)

    result = dispatch_graph_combat_action(
        runtime,
        Action(verb="attack", what="goblin_01", with_="bomb"),
    )

    assert result.runtime.progress.graph_combat_state is not None
    assert result.runtime.progress.graph_combat_state.enemy_hearts == 3
    assert "carries:player_01:bomb" in result.runtime.graph.edges


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


def test_victory_grants_xp_reward_but_leaves_carried_items_on_corpse():
    enemy = _enemy()
    enemy.properties["xp_reward"] = 4
    runtime = _runtime(
        enemy=enemy,
        graph_combat_state=_ongoing_state(round_no=3).model_copy(
            update={"enemy_hearts": 1}
        ),
    )
    runtime.graph.nodes["fang_01"] = GraphNode(
        id="fang_01",
        type="item",
        properties={"name": "송곳니"},
    )
    runtime.graph.edges["carries:goblin_01:fang_01"] = GraphEdge(
        id="carries:goblin_01:fang_01",
        type="carries",
        from_node_id="goblin_01",
        to_node_id="fang_01",
    )

    result = dispatch_graph_combat_action(
        runtime,
        Action(verb="attack", what="goblin_01"),
    )

    player = result.runtime.graph.nodes["player_01"].properties
    assert player["xp_pool"] == 4
    assert "carries:goblin_01:fang_01" in result.runtime.graph.edges
    assert "carries:player_01:fang_01" not in result.runtime.graph.edges


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
                    "target": "goblin_01",
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


def test_flee_success_escapes_without_graph_changes():
    runtime = _runtime(graph_combat_state=_ongoing_state())

    result = dispatch_graph_combat_action(
        runtime,
        Action(verb="move", how="hasty"),
    )

    assert result.outcome == "escaped"
    assert result.runtime.progress.graph_combat_state is None
    assert result.applied == 0
    assert result.runtime.graph == runtime.graph


def test_pass_defend_advances_round():
    runtime = _runtime(
        graph_combat_state=_ongoing_state(),
    )

    result = dispatch_graph_combat_action(
        runtime,
        Action(verb="pass", how="defend"),
    )

    assert result.outcome == "ongoing"
    assert result.runtime.progress.graph_combat_state.round == 3
    assert result.runtime.progress.graph_combat_state.last_action == "defend"
    assert result.runtime.progress.graph_combat_state.player_hearts == 3
    assert result.runtime.graph.nodes["player_01"].properties["hp"] == 5


def test_pass_defend_failure_loses_player_heart(monkeypatch):
    monkeypatch.setattr("src.game.engines.graph.combat.randint", lambda _a, _b: 1)
    runtime = _runtime(
        graph_combat_state=_ongoing_state(),
    )

    result = dispatch_graph_combat_action(
        runtime,
        Action(verb="pass", how="defend"),
    )

    assert result.outcome == "ongoing"
    assert result.runtime.progress.graph_combat_state.player_hearts == 2
    assert result.runtime.progress.graph_combat_state.last_action == "defend"


def test_pass_with_skill_support_attaches_defend_support():
    runtime = _runtime(
        include_skill=True,
        graph_combat_state=_ongoing_state(),
    )
    runtime.graph.nodes["fireball"].properties.update(
        {"action": "defend", "bonus": 1}
    )

    result = dispatch_graph_combat_action(
        runtime,
        Action(verb="pass", how="defend", with_="fireball"),
    )

    state = result.runtime.progress.graph_combat_state
    assert state is not None
    assert state.last_action == "defend"
    assert state.last_support_id == "fireball"
    assert state.last_support_kind == "skill"
    assert result.runtime.graph.nodes["player_01"].properties["mp"] == 3


def test_move_with_skill_support_attaches_flee_support():
    runtime = _runtime(
        include_skill=True,
        graph_combat_state=_ongoing_state(),
    )
    runtime.graph.nodes["fireball"].properties.update(
        {"action": "flee", "bonus": 2}
    )

    result = dispatch_graph_combat_action(
        runtime,
        Action(verb="move", how="flee", with_="fireball"),
    )

    state = result.combat.state
    assert state is not None
    assert result.runtime.progress.graph_combat_state is None
    assert result.outcome == "escaped"
    assert state.last_action == "flee"
    assert state.last_support_id == "fireball"
    assert state.last_support_kind == "skill"
    assert result.runtime.graph.nodes["player_01"].properties["mp"] == 3


def test_missing_combat_support_raises_dispatch_error():
    runtime = _runtime(graph_combat_state=_ongoing_state())

    with pytest.raises(GraphCombatDispatchError, match="missing combat support"):
        dispatch_graph_combat_action(
            runtime,
            Action(verb="attack", what="goblin_01", with_="missing_skill"),
        )


def test_attack_auto_skill_uses_attack_tactic_with_matching_skill():
    runtime = _runtime(
        include_skill=True,
        graph_combat_state=_ongoing_state(),
    )

    result = dispatch_graph_combat_action(
        runtime,
        Action(verb="attack", what="goblin_01", how="auto"),
    )

    state = result.runtime.progress.graph_combat_state
    assert state is not None
    assert state.last_action == "attack"
    assert state.last_support_id == "fireball"
    assert state.last_dc == 9
    assert result.runtime.graph.nodes["player_01"].properties["mp"] == 3


def test_speak_maps_to_talk_and_can_stop_combat():
    runtime = _runtime(
        graph_combat_state=_ongoing_state().model_copy(update={"enemy_pressure": 1}),
    )

    result = dispatch_graph_combat_action(
        runtime,
        Action(verb="speak", to="goblin_01"),
    )

    assert result.outcome == "combat_stopped"
    assert result.runtime.progress.graph_combat_state is None


def test_attack_with_skill_starts_combat_without_spending_first_exchange():
    runtime = _runtime(include_skill=True)

    result = dispatch_graph_combat_action(
        runtime,
        Action(verb="attack", what="goblin_01", with_="fireball"),
    )

    assert result.started is True
    assert result.outcome == "ongoing"
    assert result.runtime.graph.nodes["player_01"].properties["mp"] == 5
    assert result.runtime.progress.graph_combat_state is not None
    assert result.runtime.progress.graph_combat_state.round == 1
    assert result.runtime.progress.graph_combat_state.enemy_hearts == 3


def test_unsupported_action_raises_dispatch_error():
    with pytest.raises(GraphCombatDispatchError, match="cannot start"):
        dispatch_graph_combat_action(_runtime(), Action(verb="rest"))
