from typing import Literal

from pydantic import BaseModel, ConfigDict

from src.game.domain.graph import (
    Graph,
    GraphChange,
    GraphEdge,
    RemoveEdgeChange,
    SetNodePropertyChange,
)
from src.game.domain.graph.query import edges_from


ItemUseKind = Literal["heal", "mp_restore", "buff", "trigger"]


class GraphItemUseError(ValueError):
    pass


class GraphItemUseResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    changes: list[GraphChange]
    item_id: str
    actor_id: str
    target_id: str
    kind: ItemUseKind
    amount: int | None = None
    consumed: bool = False
    on_use: str | None = None


def plan_item_use(
    graph: Graph,
    actor_id: str,
    item_id: str,
    *,
    target_id: str | None = None,
) -> GraphItemUseResult:
    item = _require_item(graph, item_id)
    _require_character(graph, actor_id)
    resolved_target_id = target_id or actor_id
    target = _require_character(graph, resolved_target_id)
    carry_edge = _require_carried_by(graph, actor_id, item_id)

    item_props = item.properties
    effects = item_props.get("effects")
    on_use = _optional_str(item_props.get("on_use"))
    changes: list[GraphChange] = []
    amount: int | None = None

    if effects is None:
        kind: ItemUseKind = "trigger"
    elif not isinstance(effects, dict) or effects.get("type") != "consumable":
        raise GraphItemUseError(f"item is not consumable: {item_id}")
    else:
        kind, amount = _plan_consumable_effect(
            target.properties,
            item_props,
            effects,
            resolved_target_id,
            changes,
        )

    consumed = item_props.get("consumable") is True
    if consumed:
        changes.append(RemoveEdgeChange(type="remove_edge", edge_id=carry_edge.id))

    return GraphItemUseResult(
        changes=changes,
        item_id=item_id,
        actor_id=actor_id,
        target_id=resolved_target_id,
        kind=kind,
        amount=amount,
        consumed=consumed,
        on_use=on_use,
    )


def _plan_consumable_effect(
    target_props: dict,
    item_props: dict,
    effects: dict,
    target_id: str,
    changes: list[GraphChange],
) -> tuple[ItemUseKind, int | None]:
    effect = effects.get("effect")
    if effect == "heal":
        restored = _plan_resource_restore(
            target_props,
            target_id,
            current_key="hp",
            max_key="max_hp",
            amount=_int_effect(effects, "amount"),
            changes=changes,
        )
        return "heal", restored
    if effect == "mp_restore":
        return "mp_restore", _plan_resource_restore(
            target_props,
            target_id,
            current_key="mp",
            max_key="max_mp",
            amount=_int_effect(effects, "amount"),
            changes=changes,
        )
    if effect == "buff":
        _plan_buff(target_props, item_props, effects, target_id, changes)
        return "buff", None
    if effect == "damage":
        raise GraphItemUseError("damage item use belongs to graph-native combat")
    raise GraphItemUseError(f"unsupported consumable effect: {effect}")


def _plan_resource_restore(
    target_props: dict,
    target_id: str,
    *,
    current_key: Literal["hp", "mp"],
    max_key: Literal["max_hp", "max_mp"],
    amount: int,
    changes: list[GraphChange],
) -> int:
    current = _int_prop(target_props, current_key, target_id)
    maximum = _int_prop(target_props, max_key, target_id)
    if current >= maximum:
        raise GraphItemUseError(f"{current_key} already full: {target_id}")
    restored = min(maximum, current + amount) - current
    changes.append(
        SetNodePropertyChange(
            type="set_node_property",
            node_id=target_id,
            path=current_key,
            value=current + restored,
        )
    )
    return restored


def _plan_buff(
    target_props: dict,
    item_props: dict,
    effects: dict,
    target_id: str,
    changes: list[GraphChange],
) -> None:
    duration = _int_effect(effects, "duration")
    if duration < 1:
        raise GraphItemUseError(f"buff duration must be positive: {duration}")
    description = _optional_str(effects.get("description"))
    if description is None:
        description = _optional_str(item_props.get("name")) or "buff"
    raw_buffs = target_props.get("active_buffs", [])
    buffs = list(raw_buffs) if isinstance(raw_buffs, list) else []
    buffs.append({"description": description, "duration": duration})
    changes.append(
        SetNodePropertyChange(
            type="set_node_property",
            node_id=target_id,
            path="active_buffs",
            value=buffs,
        )
    )


def _require_item(graph: Graph, item_id: str):
    node = graph.nodes.get(item_id)
    if node is None:
        raise GraphItemUseError(f"missing item: {item_id}")
    if node.type != "item":
        raise GraphItemUseError(f"node is not an item: {item_id}")
    return node


def _require_character(graph: Graph, character_id: str):
    node = graph.nodes.get(character_id)
    if node is None:
        raise GraphItemUseError(f"missing character: {character_id}")
    if node.type != "character":
        raise GraphItemUseError(f"node is not a character: {character_id}")
    return node


def _require_carried_by(graph: Graph, actor_id: str, item_id: str) -> GraphEdge:
    for edge in edges_from(graph, actor_id, "carries"):
        if edge.to_node_id == item_id:
            return edge
    raise GraphItemUseError(f"item is not carried by {actor_id}: {item_id}")


def _int_prop(props: dict, key: str, node_id: str) -> int:
    value = props.get(key)
    if not isinstance(value, int):
        raise GraphItemUseError(f"missing numeric property {node_id}.{key}")
    return value


def _int_effect(effects: dict, key: str) -> int:
    value = effects.get(key)
    if not isinstance(value, int):
        raise GraphItemUseError(f"missing numeric effect field: {key}")
    return value


def _optional_str(value: object) -> str | None:
    return value if isinstance(value, str) and value else None
