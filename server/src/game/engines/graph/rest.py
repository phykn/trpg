from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel, ConfigDict

from src.game.domain.combat import GraphCombatState
from src.game.domain.graph import Graph, GraphChange, GraphNode, SetNodePropertyChange
from src.game.domain.graph.query import location_of
from src.game.engines.graph.combat import GraphCombatError, plan_combat_start
from src.game.rules import RULES

if TYPE_CHECKING:
    from src.game.runtime.state import GameRuntimeState


class GraphRestError(ValueError):
    pass


class GraphRestResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    changes: list[GraphChange]
    actor_id: str
    kind: Literal["full_recovery", "encounter"]
    next_turn_count: int
    cost_gold: int
    encounter_id: str | None = None
    state: GraphCombatState | None = None


def plan_safe_rest(runtime: GameRuntimeState, actor_id: str) -> GraphRestResult:
    result = plan_rest(runtime, actor_id)
    if result.kind != "full_recovery":
        raise GraphRestError("unsafe rest requires encounter resolver")
    return result


def plan_rest(runtime: GameRuntimeState, actor_id: str) -> GraphRestResult:
    graph = runtime.graph
    actor = _require_character(graph, actor_id)
    if actor.properties.get("alive") is False:
        raise GraphRestError(f"dead character cannot rest: {actor_id}")
    location = _rest_location(graph, actor_id)
    if location is not None and location.properties.get("sleep_risk", "safe") != "safe":
        return _plan_encounter_rest(runtime, actor_id, location)

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
        next_turn_count=runtime.progress.turn_count + 1,
        cost_gold=cost,
    )


def _require_character(graph: Graph, character_id: str) -> GraphNode:
    node = graph.nodes.get(character_id)
    if node is None:
        raise GraphRestError(f"missing character: {character_id}")
    if node.type != "character":
        raise GraphRestError(f"node is not a character: {character_id}")
    return node


def _rest_location(graph: Graph, actor_id: str) -> GraphNode | None:
    location_id = location_of(graph, actor_id)
    if location_id is None:
        return None
    location = graph.nodes.get(location_id)
    if location is None:
        raise GraphRestError(f"missing location: {location_id}")
    if location.type != "location":
        raise GraphRestError(f"node is not a location: {location_id}")
    return location


def _plan_encounter_rest(
    runtime: GameRuntimeState,
    actor_id: str,
    location: GraphNode,
) -> GraphRestResult:
    encounter_id = _first_encounter_id(location)
    if encounter_id is None:
        risk = location.properties.get("sleep_risk", "unsafe")
        raise GraphRestError(f"unsafe rest requires encounter resolver: {risk}")
    try:
        combat = plan_combat_start(runtime.graph, actor_id, encounter_id)
    except GraphCombatError as exc:
        raise GraphRestError(str(exc)) from exc
    return GraphRestResult(
        changes=[],
        actor_id=actor_id,
        kind="encounter",
        next_turn_count=runtime.progress.turn_count + 1,
        cost_gold=0,
        encounter_id=encounter_id,
        state=combat.state,
    )


def _first_encounter_id(location: GraphNode) -> str | None:
    encounters = location.properties.get("sleep_encounters", [])
    if not isinstance(encounters, list):
        return None
    for encounter_id in encounters:
        if isinstance(encounter_id, str) and encounter_id:
            return encounter_id
    return None


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
