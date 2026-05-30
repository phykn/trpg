from __future__ import annotations

from src.game.domain.content import node_label
from src.game.domain.graph import GraphEdge
from src.game.domain.graph.character import is_visible_character
from src.game.domain.graph.query import (
    characters_at,
    connection_is_unlocked,
    edges_from,
    inventory_of,
    items_at,
    known_skills_of,
    location_of,
)
from src.game.domain.memory import PlayerLogEntry
from src.locale.ko.suggestion_text import ko_possessive

from ...state import GameRuntimeState
from .model import GraphSuggestion
from .normalize import normalize_text


def recent_player_inputs(runtime: GameRuntimeState) -> set[str]:
    out: set[str] = set()
    for entry in reversed(runtime.log_entries):
        if isinstance(entry, PlayerLogEntry):
            text = normalize_text(entry.text)
            if text:
                out.add(text)
            if len(out) >= 5:
                break
    return out


def inspect_target_refs(runtime: GameRuntimeState) -> set[str]:
    refs: set[str] = set()
    place_id = location_of(runtime.graph_index, runtime.progress.player_id)
    if place_id is None:
        return refs
    refs.update(visible_exit_refs(runtime))
    refs.update(visible_character_refs(runtime))
    for item_id in items_at(runtime.graph_index, place_id):
        refs.update(node_refs(runtime, item_id))
    return refs


def visible_clue_refs(runtime: GameRuntimeState) -> set[str]:
    refs: set[str] = set()
    for node in runtime.graph.nodes.values():
        if node.type != "knowledge":
            continue
        if node.properties.get("kind") != "clue":
            continue
        if node.properties.get("visibility", "player") != "player":
            continue
        refs.update(node_refs(runtime, node.id))
    return refs


def mentions_current_place(runtime: GameRuntimeState, raw_text: str) -> bool:
    place_id = location_of(runtime.graph_index, runtime.progress.player_id)
    if place_id is None:
        return False
    lowered = raw_text.lower()
    for ref in node_refs(runtime, place_id):
        ref = ref.strip().lower()
        if not ref:
            continue
        if ref in lowered and f"{ref}{ko_possessive()}" not in lowered:
            return True
    return False


def visible_exit_refs(runtime: GameRuntimeState) -> set[str]:
    place_id = location_of(runtime.graph_index, runtime.progress.player_id)
    if place_id is None:
        return set()
    refs: set[str] = set()
    for edge in sorted(
        edges_from(runtime.graph_index, place_id, "connects_to"),
        key=move_edge_priority,
    ):
        if not connection_is_unlocked(runtime.graph_index, edge):
            continue
        node = runtime.graph.nodes.get(edge.to_node_id)
        if node is not None and node.type == "location":
            refs.update(node_refs(runtime, node.id))
    return refs


def visible_character_refs(runtime: GameRuntimeState) -> set[str]:
    place_id = location_of(runtime.graph_index, runtime.progress.player_id)
    if place_id is None:
        return set()
    refs: set[str] = set()
    for character_id in characters_at(runtime.graph_index, place_id):
        if character_id == runtime.progress.player_id:
            continue
        node = runtime.graph.nodes.get(character_id)
        if node is None or node.type != "character" or not is_visible_character(node):
            continue
        refs.update(node_refs(runtime, character_id))
    return refs


def usable_refs(runtime: GameRuntimeState) -> set[str]:
    refs: set[str] = set()
    player_id = runtime.progress.player_id
    for item_id in inventory_of(runtime.graph_index, player_id):
        refs.update(node_refs(runtime, item_id))
    for skill_edge in known_skills_of(runtime.graph_index, player_id):
        refs.update(node_refs(runtime, skill_edge.to_node_id))
    return refs


def node_refs(runtime: GameRuntimeState, node_id: str) -> set[str]:
    node = runtime.graph.nodes.get(node_id)
    if node is None:
        return {node_id}
    return {node_id, node_label(runtime.content, node)}


def mentions_any(suggestion: GraphSuggestion, refs: set[str]) -> bool:
    text = normalize_text(f"{suggestion.label} {suggestion.input_text}")
    return any(normalize_text(ref) in text for ref in refs if normalize_text(ref))


def input_mentions_any(suggestion: GraphSuggestion, refs: set[str]) -> bool:
    text = normalize_text(suggestion.input_text)
    return any(normalize_text(ref) in text for ref in refs if normalize_text(ref))


def has_quest_status(runtime: GameRuntimeState, statuses: set[str]) -> bool:
    for node in runtime.graph.nodes.values():
        if node.type != "quest":
            continue
        status = node.properties.get("status")
        if isinstance(status, str) and status in statuses:
            return True
    return False


def move_edge_priority(edge: GraphEdge) -> int:
    if edge.properties.get("requires_quest") or edge.properties.get("requires_active_quest"):
        return 0
    return 1
