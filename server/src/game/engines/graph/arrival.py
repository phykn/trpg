from dataclasses import dataclass
from typing import Any

from src.game.domain.graph import Graph, GraphChange, RemoveEdgeChange
from src.game.domain.graph.query import edges_from, inventory_of


@dataclass(frozen=True)
class GraphArrivalEffectResult:
    changes: list[GraphChange]
    removed_companion_ids: list[str]
    hidden_character_ids: list[str]


def plan_arrival_branch_effects(
    graph: Graph,
    player_id: str,
    destination_id: str,
) -> GraphArrivalEffectResult:
    destination = graph.nodes.get(destination_id)
    if destination is None or destination.type != "location":
        return _empty_result()

    removed_companion_ids: set[str] = set()
    hidden_character_ids: set[str] = set()
    remove_edge_ids: set[str] = set()

    for branch in _dicts(destination.properties.get("arrival_branches")):
        if not _branch_condition_matches(graph, player_id, branch):
            continue
        for companion_id in _effect_ids(branch, "remove_companions"):
            for edge in edges_from(graph, player_id, "has_companion"):
                if edge.to_node_id != companion_id:
                    continue
                remove_edge_ids.add(edge.id)
                removed_companion_ids.add(companion_id)
        for character_id in _effect_ids(branch, "hide_characters"):
            if character_id == player_id:
                continue
            for edge in edges_from(graph, character_id, "located_at"):
                remove_edge_ids.add(edge.id)
                hidden_character_ids.add(character_id)

    return GraphArrivalEffectResult(
        changes=[
            RemoveEdgeChange(type="remove_edge", edge_id=edge_id)
            for edge_id in sorted(remove_edge_ids)
        ],
        removed_companion_ids=sorted(removed_companion_ids),
        hidden_character_ids=sorted(hidden_character_ids),
    )


def _empty_result() -> GraphArrivalEffectResult:
    return GraphArrivalEffectResult(
        changes=[],
        removed_companion_ids=[],
        hidden_character_ids=[],
    )


def _branch_condition_matches(
    graph: Graph,
    player_id: str,
    branch: dict[str, Any],
) -> bool:
    property_name = branch.get("inventory_item_property")
    if not isinstance(property_name, str) or not property_name:
        return False
    for item_id in inventory_of(graph, player_id):
        item = graph.nodes.get(item_id)
        if item is not None and item.properties.get(property_name) is True:
            return True
    return False


def _effect_ids(branch: dict[str, Any], key: str) -> list[str]:
    raw = branch.get(key)
    if isinstance(raw, str) and raw:
        return [raw]
    if isinstance(raw, list):
        return [item for item in raw if isinstance(item, str) and item]
    return []


def _dicts(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]
