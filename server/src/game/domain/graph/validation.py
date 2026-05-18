from typing import Any

from .models import EdgeType, Graph, GraphInvariantError, NodeType


_EDGE_NODE_TYPES: dict[EdgeType, tuple[set[NodeType], set[NodeType]]] = {
    "located_at": ({"character", "item"}, {"location"}),
    "hidden_at": ({"character", "item"}, {"location"}),
    "carries": ({"character"}, {"item"}),
    "equips": ({"character"}, {"item"}),
    "connects_to": ({"location"}, {"location"}),
    "has_companion": ({"character"}, {"character"}),
    "knows_skill": ({"character"}, {"skill"}),
    "belongs_to_race": ({"character"}, {"race"}),
    "grants_skill": ({"race"}, {"skill"}),
    "gives_quest": ({"character", "location"}, {"quest"}),
    "target_of": ({"character", "item", "location"}, {"quest"}),
    "required_by": ({"character", "item", "location"}, {"quest"}),
    "reward_of": ({"item"}, {"quest"}),
    "part_of_chapter": ({"quest"}, {"chapter"}),
    "relation": ({"character"}, {"character"}),
    "uses_effect": ({"item", "skill"}, {"effect"}),
    "applies_status": ({"item", "skill", "character", "location"}, {"status"}),
    "uses_slot": ({"item"}, {"slot"}),
    "member_of_faction": ({"character"}, {"faction"}),
    "faction_relation": ({"faction"}, {"faction"}),
    "uses_action": ({"skill"}, {"action"}),
    "has_knowledge": ({"character", "item", "location", "quest"}, {"knowledge"}),
    "uses_dialogue_style": ({"character"}, {"dialogue_style"}),
    "has_mbti": ({"character"}, {"mbti"}),
}

_ITEM_PLACEMENT_FROM_ITEM: frozenset[EdgeType] = frozenset(
    {"located_at", "hidden_at", "reward_of"}
)
_ITEM_PLACEMENT_TO_ITEM: frozenset[EdgeType] = frozenset({"carries", "equips"})


def validate_graph(graph: Graph) -> None:
    _validate_edge_endpoints(graph)
    _validate_edge_node_types(graph)
    _validate_equips_owner(graph)
    _validate_item_placement(graph)
    _validate_character_location(graph)
    _validate_quest_trigger_targets(graph)


def _validate_edge_endpoints(graph: Graph) -> None:
    for edge in graph.edges.values():
        if edge.from_node_id not in graph.nodes:
            raise GraphInvariantError(f"missing node: {edge.from_node_id}")
        if edge.to_node_id not in graph.nodes:
            raise GraphInvariantError(f"missing node: {edge.to_node_id}")


def _validate_edge_node_types(graph: Graph) -> None:
    for edge in graph.edges.values():
        from_type = graph.nodes[edge.from_node_id].type
        to_type = graph.nodes[edge.to_node_id].type
        allowed_from, allowed_to = _EDGE_NODE_TYPES[edge.type]
        if from_type not in allowed_from or to_type not in allowed_to:
            raise GraphInvariantError(
                "edge type mismatch: "
                f"{edge.type} cannot connect {from_type} to {to_type}"
            )


def _validate_equips_owner(graph: Graph) -> None:
    for edge in graph.edges.values():
        if edge.type != "equips":
            continue
        owner = graph.nodes[edge.from_node_id]
        if owner.properties.get("is_player") is True or owner.id == "player_01":
            continue
        raise GraphInvariantError(f"equips owner must be player: {edge.id}")


def _validate_item_placement(graph: Graph) -> None:
    placements: dict[str, list[str]] = {}
    for edge in graph.edges.values():
        if edge.type in _ITEM_PLACEMENT_FROM_ITEM:
            item_id = edge.from_node_id
        elif edge.type in _ITEM_PLACEMENT_TO_ITEM:
            item_id = edge.to_node_id
        else:
            continue
        if graph.nodes[item_id].type != "item":
            continue
        placements.setdefault(item_id, []).append(edge.id)

    for item_id, edge_ids in placements.items():
        if len(edge_ids) > 1:
            joined = ", ".join(edge_ids)
            raise GraphInvariantError(f"item placement conflict: {item_id} ({joined})")


def _validate_character_location(graph: Graph) -> None:
    locations: dict[str, list[str]] = {}
    for edge in graph.edges.values():
        if edge.type != "located_at":
            continue
        if graph.nodes[edge.from_node_id].type != "character":
            continue
        locations.setdefault(edge.from_node_id, []).append(edge.id)

    for character_id, edge_ids in locations.items():
        if len(edge_ids) > 1:
            joined = ", ".join(edge_ids)
            raise GraphInvariantError(
                f"character location conflict: {character_id} ({joined})"
            )


def _validate_quest_trigger_targets(graph: Graph) -> None:
    for quest in graph.nodes.values():
        if quest.type != "quest":
            continue
        for trigger in _dicts(quest.properties.get("triggers")):
            target = trigger.get("target")
            if isinstance(target, str) and target not in graph.nodes:
                raise GraphInvariantError(
                    f"quest trigger target missing: {quest.id} -> {target}"
                )


def _dicts(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [entry for entry in value if isinstance(entry, dict)]
