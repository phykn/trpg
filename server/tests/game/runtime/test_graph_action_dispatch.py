import pytest

from src.game.domain.action import Action
from src.game.domain.clock import next_dawn_turn
from src.game.domain.graph import Graph, GraphEdge, GraphNode
from src.game.domain.progress import GameProgress
from src.game.runtime import GameRuntimeState
from src.game.runtime.dispatch import (
    GraphActionDispatchError,
    dispatch_graph_action,
)
from src.game.rules import RULES


def _character(
    character_id: str,
    *,
    hp: int = 30,
    max_hp: int = 30,
    mp: int = 10,
    max_mp: int = 10,
    gold: int | None = None,
) -> GraphNode:
    properties = {
        "name": character_id,
        "hp": hp,
        "max_hp": max_hp,
        "mp": mp,
        "max_mp": max_mp,
        "alive": hp > 0,
        "stats": {"body": 3, "agility": 2, "mind": 2, "presence": 2},
        "status": [],
        "visited_location_ids": [],
    }
    if gold is not None:
        properties["gold"] = gold
    return GraphNode(id=character_id, type="character", properties=properties)


def _item(
    item_id: str,
    *,
    effect: str | None = None,
    amount: int = 0,
) -> GraphNode:
    effects = None
    if effect is not None:
        effects = {"type": "consumable", "effect": effect, "amount": amount}
    return GraphNode(
        id=item_id,
        type="item",
        properties={
            "name": item_id,
            "consumable": effect is not None,
            "effects": effects,
        },
    )


def _runtime() -> GameRuntimeState:
    return GameRuntimeState(
        graph=Graph(
            nodes={
                "town": GraphNode(id="town", type="location", properties={}),
                "forest": GraphNode(id="forest", type="location", properties={}),
                "danger_room": GraphNode(
                    id="danger_room",
                    type="location",
                    properties={
                        "sleep_risk": "dangerous",
                        "sleep_encounters": ["goblin_01"],
                    },
                ),
                "player_01": _character(
                    "player_01",
                    hp=12,
                    max_hp=30,
                    mp=3,
                    max_mp=10,
                    gold=RULES.recovery.cost_gold,
                ),
                "goblin_01": _character("goblin_01", hp=24, max_hp=24),
                "merchant_01": _character("merchant_01", gold=0),
                "quest_rat": GraphNode(
                    id="quest_rat",
                    type="quest",
                    properties={"status": "locked"},
                ),
                "sword": _item("sword"),
                "potion": _item("potion", effect="heal", amount=10),
                "merchant_potion": GraphNode(
                    id="merchant_potion",
                    type="item",
                    properties={"price": 4},
                ),
            },
            edges={
                "located_at:player_01:town": GraphEdge(
                    id="located_at:player_01:town",
                    type="located_at",
                    from_node_id="player_01",
                    to_node_id="town",
                ),
                "located_at:goblin_01:town": GraphEdge(
                    id="located_at:goblin_01:town",
                    type="located_at",
                    from_node_id="goblin_01",
                    to_node_id="town",
                ),
                "located_at:merchant_01:town": GraphEdge(
                    id="located_at:merchant_01:town",
                    type="located_at",
                    from_node_id="merchant_01",
                    to_node_id="town",
                ),
                "connects_to:town:forest": GraphEdge(
                    id="connects_to:town:forest",
                    type="connects_to",
                    from_node_id="town",
                    to_node_id="forest",
                ),
                "connects_to:town:danger_room": GraphEdge(
                    id="connects_to:town:danger_room",
                    type="connects_to",
                    from_node_id="town",
                    to_node_id="danger_room",
                ),
                "carries:player_01:sword": GraphEdge(
                    id="carries:player_01:sword",
                    type="carries",
                    from_node_id="player_01",
                    to_node_id="sword",
                ),
                "carries:player_01:potion": GraphEdge(
                    id="carries:player_01:potion",
                    type="carries",
                    from_node_id="player_01",
                    to_node_id="potion",
                ),
                "carries:merchant_01:merchant_potion": GraphEdge(
                    id="carries:merchant_01:merchant_potion",
                    type="carries",
                    from_node_id="merchant_01",
                    to_node_id="merchant_potion",
                ),
            },
        ),
        progress=GameProgress(game_id="game-1", player_id="player_01", turn_count=5),
    )


def test_move_dispatch_applies_location_change_and_advances_turn():
    result = dispatch_graph_action(_runtime(), Action(verb="move", to="forest"))

    assert result.kind == "move"
    assert result.runtime.progress.turn_count == 6
    assert "located_at:player_01:forest" in result.runtime.graph.edges
    assert "located_at:player_01:town" not in result.runtime.graph.edges


def test_move_dispatch_rejects_downed_player():
    runtime = _runtime()
    runtime.graph.nodes["player_01"].properties["status"] = ["downed"]
    runtime.graph.nodes["player_01"].properties["defeat_mode"] = "downed"

    with pytest.raises(GraphActionDispatchError, match="downed"):
        dispatch_graph_action(runtime, Action(verb="move", to="forest"))


def test_transfer_equip_dispatch_equips_carried_item():
    result = dispatch_graph_action(
        _runtime(),
        Action(verb="transfer", what="sword", how="equip", to="weapon"),
    )

    assert result.kind == "equip"
    assert result.runtime.progress.turn_count == 6
    edge = result.runtime.graph.edges["equips:player_01:sword"]
    assert edge.properties == {"slot": "weapon"}
    assert "carries:player_01:sword" not in result.runtime.graph.edges


def test_transfer_trade_dispatch_buys_item_and_advances_turn():
    result = dispatch_graph_action(
        _runtime(),
        Action(
            verb="transfer",
            what="merchant_potion",
            how="trade",
            from_="merchant_01",
            to="player_01",
        ),
    )

    assert result.kind == "trade_buy"
    assert result.runtime.progress.turn_count == 6
    assert "carries:player_01:merchant_potion" in result.runtime.graph.edges
    assert result.runtime.graph.nodes["player_01"].properties["gold"] == 6


def test_use_dispatch_applies_healing_and_consumes_item():
    result = dispatch_graph_action(_runtime(), Action(verb="use", what="potion"))

    assert result.kind == "use"
    assert result.runtime.graph.nodes["player_01"].properties["hp"] == 22
    assert "carries:player_01:potion" not in result.runtime.graph.edges


def test_quest_accept_dispatch_updates_status():
    result = dispatch_graph_action(
        _runtime(),
        Action(verb="transfer", what="quest_rat", how="accept"),
    )

    assert result.kind == "quest_accept"
    assert result.runtime.progress.turn_count == 6
    assert result.runtime.progress.active_quest_id == "quest_rat"
    assert result.runtime.graph.nodes["quest_rat"].properties["status"] == "active"


def test_quest_abandon_dispatch_clears_active_quest():
    runtime = _runtime()
    runtime.graph.nodes["quest_rat"].properties["status"] = "active"
    runtime = runtime.model_copy(
        update={
            "progress": runtime.progress.model_copy(
                update={"active_quest_id": "quest_rat"}
            )
        }
    )

    result = dispatch_graph_action(
        runtime,
        Action(verb="transfer", what="quest_rat", how="abandon"),
    )

    assert result.kind == "quest_abandon"
    assert result.runtime.progress.active_quest_id is None
    assert result.runtime.graph.nodes["quest_rat"].properties["status"] == "abandoned"


def test_rest_dispatch_restores_resources_and_jumps_turn_count():
    runtime = _runtime()

    result = dispatch_graph_action(runtime, Action(verb="rest"))

    player = result.runtime.graph.nodes["player_01"].properties
    assert result.kind == "rest"
    assert player["hp"] == 30
    assert player["mp"] == 10
    assert result.runtime.progress.turn_count == next_dawn_turn(5)


def test_rest_dispatch_in_danger_starts_encounter_instead_of_recovery():
    runtime = _runtime()
    runtime.graph.edges.pop("located_at:player_01:town")
    runtime.graph.edges["located_at:player_01:danger_room"] = GraphEdge(
        id="located_at:player_01:danger_room",
        type="located_at",
        from_node_id="player_01",
        to_node_id="danger_room",
    )
    runtime.graph.edges.pop("located_at:goblin_01:town")
    runtime.graph.edges["located_at:goblin_01:danger_room"] = GraphEdge(
        id="located_at:goblin_01:danger_room",
        type="located_at",
        from_node_id="goblin_01",
        to_node_id="danger_room",
    )

    result = dispatch_graph_action(runtime, Action(verb="rest"))

    assert result.kind == "rest_encounter"
    assert result.runtime.progress.graph_combat_state is not None
    assert result.runtime.progress.graph_combat_state.enemy_ids == ["goblin_01"]
    assert result.runtime.graph.nodes["player_01"].properties["hp"] == 12


def test_attack_dispatch_delegates_to_graph_combat_dispatch():
    result = dispatch_graph_action(
        _runtime(),
        Action(verb="attack", what="goblin_01"),
    )

    assert result.kind == "combat"
    assert result.outcome == "ongoing"
    assert result.runtime.progress.graph_combat_state is not None
    assert result.runtime.progress.turn_count == 6


def test_query_dispatch_is_rejected():
    with pytest.raises(GraphActionDispatchError, match="read-only"):
        dispatch_graph_action(_runtime(), Action(verb="query", what="status"))
