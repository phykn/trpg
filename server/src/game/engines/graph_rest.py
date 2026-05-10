from typing import Literal

from pydantic import BaseModel, ConfigDict

from src.game.domain.clock import next_dawn_turn
from src.game.domain.graph import Graph, GraphChange, GraphNode, SetNodePropertyChange
from src.game.domain.graph_query import location_of
from src.game.rules import RULES
from src.game.runtime.state import GameRuntimeState


class GraphRestError(ValueError):
    pass


class GraphRestResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    changes: list[GraphChange]
    actor_id: str
    kind: Literal["full_recovery"]
    next_turn_count: int
    cost_gold: int


def plan_safe_rest(runtime: GameRuntimeState, actor_id: str) -> GraphRestResult:
    graph = runtime.graph
    actor = _require_character(graph, actor_id)
    if actor.properties.get("alive") is False:
        raise GraphRestError(f"dead character cannot rest: {actor_id}")
    _require_safe_location(graph, actor_id)

    cost = RULES.recovery.cost_gold
    gold = _int_prop(actor, "gold")
    if gold < cost:
        raise GraphRestError(f"not enough gold to rest: {gold} < {cost}")

    changes: list[GraphChange] = [
        _set(actor_id, "gold", gold - cost),
        _set(actor_id, "hp", _int_prop(actor, "max_hp")),
        _set(actor_id, "mp", _int_prop(actor, "max_mp")),
    ]
    return GraphRestResult(
        changes=changes,
        actor_id=actor_id,
        kind="full_recovery",
        next_turn_count=next_dawn_turn(runtime.progress.turn_count),
        cost_gold=cost,
    )


def _require_character(graph: Graph, character_id: str) -> GraphNode:
    node = graph.nodes.get(character_id)
    if node is None:
        raise GraphRestError(f"missing character: {character_id}")
    if node.type != "character":
        raise GraphRestError(f"node is not a character: {character_id}")
    return node


def _require_safe_location(graph: Graph, actor_id: str) -> None:
    location_id = location_of(graph, actor_id)
    if location_id is None:
        return
    location = graph.nodes.get(location_id)
    if location is None:
        raise GraphRestError(f"missing location: {location_id}")
    risk = location.properties.get("sleep_risk", "safe")
    if risk != "safe":
        raise GraphRestError(f"unsafe rest requires encounter resolver: {risk}")


def _int_prop(node: GraphNode, key: str) -> int:
    value = node.properties.get(key)
    if not isinstance(value, int):
        raise GraphRestError(f"missing numeric property {node.id}.{key}")
    return value


def _set(node_id: str, path: str, value: int) -> SetNodePropertyChange:
    return SetNodePropertyChange(
        type="set_node_property",
        node_id=node_id,
        path=path,
        value=value,
    )
