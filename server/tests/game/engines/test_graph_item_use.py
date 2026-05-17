import pytest

from src.game.domain.graph import Graph, GraphEdge, GraphNode
from src.game.domain.graph.apply import apply_graph_change
from src.game.engines.graph.item_use import GraphItemUseError, plan_item_use


def _item(
    item_id: str,
    *,
    consumable: bool = True,
    effect_id: str | None = None,
    amount: int | None = None,
    on_use: str | None = None,
) -> GraphNode:
    properties = {
        "name": item_id,
        "consumable": consumable,
        "effect": effect_id,
        "on_use": on_use,
    }
    if amount is not None:
        properties["amount"] = amount
    return GraphNode(
        id=item_id,
        type="item",
        properties=properties,
    )


def _effect(
    effect_id: str,
    *,
    kind: str,
    description: str | None = None,
    duration: int | None = None,
) -> GraphNode:
    return GraphNode(
        id=effect_id,
        type="effect",
        properties={
            "kind": kind,
            "description": description,
            "duration": duration,
        },
    )


def _graph() -> Graph:
    item_ids = ["potion", "mana", "scroll", "key", "bomb", "uncarried"]
    nodes = {
        "player_01": GraphNode(
            id="player_01",
            type="character",
            properties={
                "hp": 10,
                "max_hp": 20,
                "mp": 2,
                "max_mp": 10,
                "active_buffs": [],
            },
        ),
        "ally_01": GraphNode(
            id="ally_01",
            type="character",
            properties={"hp": 18, "max_hp": 20, "active_buffs": []},
        ),
        "potion": _item("potion", effect_id="heal", amount=15),
        "mana": _item("mana", effect_id="mp_restore", amount=5),
        "scroll": _item("scroll", effect_id="strength_buff"),
        "key": _item(
            "key",
            consumable=False,
            on_use="open_ancient_door",
        ),
        "bomb": _item("bomb", effect_id="damage", amount=10),
        "uncarried": _item("uncarried", effect_id="heal", amount=5),
        "heal": _effect("heal", kind="heal"),
        "mp_restore": _effect("mp_restore", kind="mp_restore"),
        "strength_buff": _effect(
            "strength_buff",
            kind="buff",
            description="근력 일시 강화",
            duration=5,
        ),
        "damage": _effect("damage", kind="damage"),
    }
    edges = {
        f"carries:player_01:{item_id}": GraphEdge(
            id=f"carries:player_01:{item_id}",
            type="carries",
            from_node_id="player_01",
            to_node_id=item_id,
        )
        for item_id in item_ids
        if item_id != "uncarried"
    }
    return Graph(nodes=nodes, edges=edges)


def _apply_all(graph: Graph, changes) -> Graph:
    for change in changes:
        graph = apply_graph_change(graph, change)
    return graph


def test_heal_consumable_caps_hp_and_removes_item():
    result = plan_item_use(_graph(), "player_01", "potion")
    changed = _apply_all(_graph(), result.changes)

    assert result.kind == "heal"
    assert result.amount == 10
    assert result.consumed is True
    assert changed.nodes["player_01"].properties["hp"] == 20
    assert "carries:player_01:potion" not in changed.edges


def test_mp_restore_caps_mp():
    result = plan_item_use(_graph(), "player_01", "mana")
    changed = _apply_all(_graph(), result.changes)

    assert result.kind == "mp_restore"
    assert result.amount == 5
    assert changed.nodes["player_01"].properties["mp"] == 7


def test_buff_appends_active_buff_and_consumes_item():
    result = plan_item_use(_graph(), "player_01", "scroll")
    changed = _apply_all(_graph(), result.changes)

    assert result.kind == "buff"
    assert changed.nodes["player_01"].properties["active_buffs"] == [
        {"description": "근력 일시 강화", "duration": 5}
    ]
    assert "carries:player_01:scroll" not in changed.edges


def test_trigger_item_is_not_consumed():
    result = plan_item_use(_graph(), "player_01", "key")
    changed = _apply_all(_graph(), result.changes)

    assert result.kind == "trigger"
    assert result.on_use == "open_ancient_door"
    assert result.consumed is False
    assert "carries:player_01:key" in changed.edges


def test_validation_rejects_missing_and_not_carried_items():
    with pytest.raises(GraphItemUseError, match="missing item"):
        plan_item_use(_graph(), "player_01", "ghost")
    with pytest.raises(GraphItemUseError, match="missing character"):
        plan_item_use(_graph(), "ghost", "potion")
    with pytest.raises(GraphItemUseError, match="not carried"):
        plan_item_use(_graph(), "player_01", "uncarried")


def test_full_hp_heal_and_damage_consumable_are_rejected():
    graph = _graph()
    graph.nodes["player_01"].properties["hp"] = 20
    with pytest.raises(GraphItemUseError, match="hp already full"):
        plan_item_use(graph, "player_01", "potion")
    with pytest.raises(GraphItemUseError, match="combat"):
        plan_item_use(_graph(), "player_01", "bomb", target_id="ally_01")


def test_item_use_changes_are_individually_valid_graph_changes():
    graph = _graph()
    result = plan_item_use(graph, "player_01", "potion")

    for change in result.changes:
        graph = apply_graph_change(graph, change)

    assert graph.nodes["player_01"].properties["hp"] == 20
