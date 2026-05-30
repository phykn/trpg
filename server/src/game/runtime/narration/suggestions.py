from typing import Any

from pydantic import BaseModel

from src.game.domain.content import node_label
from src.game.domain.graph import GraphEdge, GraphNode
from src.game.domain.graph.character import is_visible_character
from src.game.domain.memory import PlayerLogEntry
from src.game.domain.graph.query import (
    characters_at,
    connection_is_unlocked,
    edges_from,
    inventory_of,
    items_at,
    known_skills_of,
    location_of,
)
from src.locale.ko.suggestion_text import (
    TARGETLESS_GENERIC_SUGGESTIONS,
    TARGETLESS_TALK_LABELS,
    TARGET_PARTICLES,
    ko_abandon as _ko_abandon,
    ko_accept as _ko_accept,
    ko_as_ask as _ko_as_ask,
    ko_ask_label as _ko_ask_label,
    ko_at_topic as _ko_at_topic,
    ko_close_quote as _ko_close_quote,
    ko_current_situation as _ko_current_situation,
    ko_direction_particle as _ko_direction_particle,
    ko_here as _ko_here,
    ko_inspect as _ko_inspect,
    ko_inspect_label as _ko_inspect_label,
    ko_meaning as _ko_meaning,
    ko_move as _ko_move,
    ko_object as _ko_object,
    ko_open_quote as _ko_open_quote,
    ko_possessive as _ko_possessive,
    ko_room as _ko_room,
    ko_room_question as _ko_room_question,
    ko_situation as _ko_situation,
    ko_surroundings as _ko_surroundings,
    ko_to_person as _ko_to_person,
    ko_what_to_check_question as _ko_what_to_check_question,
)

from ..state import GameRuntimeState


class GraphSuggestion(BaseModel):
    label: str
    input_text: str
    intent: str | None = None
    action: dict[str, Any] | None = None


def build_intro_suggestions(runtime: GameRuntimeState) -> list[GraphSuggestion]:
    suggestions: list[GraphSuggestion] = []
    suggestions.extend(_intro_talk_suggestions(runtime, limit=1))
    suggestions.extend(_intro_quest_beat_suggestions(runtime, limit=1))
    suggestions.extend(_intro_move_suggestions(runtime, limit=1))
    suggestions.append(
        GraphSuggestion(
            label=f"{_ko_surroundings()} {_ko_inspect_label()}",
            input_text=f"{_ko_surroundings()}{_ko_object()} {_ko_inspect()}",
            intent="inspect",
        )
    )
    return suggestions[:3]


def next_turn_suggestions(
    runtime: GameRuntimeState,
    narration_suggestions: list[GraphSuggestion],
) -> list[GraphSuggestion]:
    grounded = filter_grounded_suggestions(runtime, narration_suggestions)
    if grounded:
        return grounded
    fallback = build_intro_suggestions(runtime)
    filtered_fallback = filter_grounded_suggestions(runtime, fallback)
    return filtered_fallback or fallback


def filter_grounded_suggestions(
    runtime: GameRuntimeState,
    suggestions: list[GraphSuggestion],
) -> list[GraphSuggestion]:
    can_accept_quest = _has_quest_status(runtime, {"locked", "pending"})
    can_abandon_quest = _has_quest_status(runtime, {"active"})
    recent_inputs = _recent_player_inputs(runtime)
    out: list[GraphSuggestion] = []
    for suggestion in suggestions:
        if not _is_grounded_suggestion(runtime, suggestion):
            continue
        if _normalize(suggestion.input_text) in recent_inputs:
            continue
        if suggestion.intent != "quest":
            out.append(suggestion)
            continue
        text = f"{suggestion.label} {suggestion.input_text}".lower()
        wants_accept = _ko_accept() in text or "accept" in text
        wants_abandon = _ko_abandon() in text or "abandon" in text
        if wants_accept and not can_accept_quest:
            continue
        if wants_abandon and not can_abandon_quest:
            continue
        out.append(suggestion)
    return out


def _recent_player_inputs(runtime: GameRuntimeState) -> set[str]:
    out: set[str] = set()
    for entry in reversed(runtime.log_entries):
        if isinstance(entry, PlayerLogEntry):
            text = _normalize(entry.text)
            if text:
                out.add(text)
            if len(out) >= 5:
                break
    return out


def _is_grounded_suggestion(
    runtime: GameRuntimeState,
    suggestion: GraphSuggestion,
) -> bool:
    if suggestion.intent is None:
        return False
    intent = suggestion.intent.strip().lower()
    if intent == "move":
        return _mentions_any(suggestion, _visible_exit_refs(runtime))
    if intent == "talk":
        return _mentions_any(suggestion, _visible_character_refs(runtime))
    if intent == "use":
        return _mentions_any(suggestion, _usable_refs(runtime))
    if intent == "combat":
        return runtime.progress.graph_combat_state is not None
    if intent == "inspect":
        return _is_grounded_inspect_suggestion(runtime, suggestion)
    if intent == "quest":
        return True
    return False


def _is_grounded_inspect_suggestion(
    runtime: GameRuntimeState,
    suggestion: GraphSuggestion,
) -> bool:
    raw_text = suggestion.input_text
    text = _normalize(raw_text)
    if _mentions_any(suggestion, _visible_clue_refs(runtime)):
        return False
    if _normalize(_ko_surroundings()) in text:
        return True
    return _input_mentions_any(suggestion, _inspect_target_refs(runtime)) or (
        _mentions_current_place(runtime, raw_text)
    )


def _inspect_target_refs(runtime: GameRuntimeState) -> set[str]:
    refs: set[str] = set()
    place_id = location_of(runtime.graph_index, runtime.progress.player_id)
    if place_id is None:
        return refs
    refs.update(_visible_exit_refs(runtime))
    refs.update(_visible_character_refs(runtime))
    for item_id in items_at(runtime.graph_index, place_id):
        refs.update(_node_refs(runtime, item_id))
    return refs


def _visible_clue_refs(runtime: GameRuntimeState) -> set[str]:
    refs: set[str] = set()
    for node in runtime.graph.nodes.values():
        if node.type != "knowledge":
            continue
        if node.properties.get("kind") != "clue":
            continue
        if node.properties.get("visibility", "player") != "player":
            continue
        refs.update(_node_refs(runtime, node.id))
    return refs


def _mentions_current_place(runtime: GameRuntimeState, raw_text: str) -> bool:
    place_id = location_of(runtime.graph_index, runtime.progress.player_id)
    if place_id is None:
        return False
    lowered = raw_text.lower()
    for ref in _node_refs(runtime, place_id):
        ref = ref.strip().lower()
        if not ref:
            continue
        if ref in lowered and f"{ref}{_ko_possessive()}" not in lowered:
            return True
    return False


def _visible_exit_refs(runtime: GameRuntimeState) -> set[str]:
    place_id = location_of(runtime.graph_index, runtime.progress.player_id)
    if place_id is None:
        return set()
    refs: set[str] = set()
    for edge in sorted(
        edges_from(runtime.graph_index, place_id, "connects_to"),
        key=_move_edge_priority,
    ):
        if not connection_is_unlocked(runtime.graph_index, edge):
            continue
        node = runtime.graph.nodes.get(edge.to_node_id)
        if node is not None and node.type == "location":
            refs.update(_node_refs(runtime, node.id))
    return refs


def _intro_talk_suggestions(
    runtime: GameRuntimeState,
    *,
    limit: int,
) -> list[GraphSuggestion]:
    place_id = location_of(runtime.graph_index, runtime.progress.player_id)
    if place_id is None:
        return []
    out: list[GraphSuggestion] = []
    for character_id in characters_at(runtime.graph_index, place_id):
        if character_id == runtime.progress.player_id:
            continue
        node = runtime.graph.nodes.get(character_id)
        if node is None or node.type != "character" or not is_visible_character(node):
            continue
        name = node_label(runtime.content, node)
        topic, question = _intro_talk_topic(runtime, place_id)
        out.append(
            GraphSuggestion(
                label=f"{topic} {_ko_ask_label()}",
                input_text=(
                    f"{name}{_ko_to_person()} "
                    f"{_ko_open_quote()}{question}{_ko_close_quote()}{_ko_as_ask()}"
                ),
                intent="talk",
            )
        )
        if len(out) == limit:
            break
    return out


def _intro_talk_topic(
    runtime: GameRuntimeState,
    place_id: str,
) -> tuple[str, str]:
    node = runtime.graph.nodes.get(place_id)
    place_name = node_label(runtime.content, node).strip() if node is not None else ""
    if _ko_room() in place_name:
        return (
            f"{_ko_room()}{_ko_possessive()} {_ko_meaning()}",
            _ko_room_question(),
        )
    if place_name:
        return (
            f"{place_name} {_ko_situation()}",
            f"{place_name}{_ko_at_topic()} {_ko_what_to_check_question()}",
        )
    return (
        _ko_current_situation(),
        f"{_ko_here()}{_ko_at_topic()} {_ko_what_to_check_question()}",
    )


def _intro_move_suggestions(
    runtime: GameRuntimeState,
    *,
    limit: int,
) -> list[GraphSuggestion]:
    place_id = location_of(runtime.graph_index, runtime.progress.player_id)
    if place_id is None:
        return []
    out: list[GraphSuggestion] = []
    for edge in sorted(
        edges_from(runtime.graph_index, place_id, "connects_to"),
        key=_move_edge_priority,
    ):
        if not connection_is_unlocked(runtime.graph_index, edge):
            continue
        node = runtime.graph.nodes.get(edge.to_node_id)
        if node is None or node.type != "location":
            continue
        name = node_label(runtime.content, node)
        out.append(
            GraphSuggestion(
                label=f"{name}{_ko_direction_particle(name)}",
                input_text=f"{name}{_ko_direction_particle(name)} {_ko_move()}",
                intent="move",
            )
        )
        if len(out) == limit:
            break
    return out


def _move_edge_priority(edge: GraphEdge) -> int:
    if edge.properties.get("requires_quest") or edge.properties.get("requires_active_quest"):
        return 0
    return 1


def _intro_quest_beat_suggestions(
    runtime: GameRuntimeState,
    *,
    limit: int,
) -> list[GraphSuggestion]:
    out: list[GraphSuggestion] = []
    for node in sorted(
        runtime.graph.nodes.values(),
        key=_quest_beat_sort_key,
        reverse=True,
    ):
        if node.type != "quest":
            continue
        if node.properties.get("status") != "pending":
            continue
        if node.properties.get("required") is not False:
            continue
        label = node.properties.get("title")
        input_text = node.properties.get("description")
        if not isinstance(label, str) or not label.strip():
            continue
        if not isinstance(input_text, str) or not input_text.strip():
            continue
        out.append(
            GraphSuggestion(
                label=label.strip(),
                input_text=input_text.strip(),
                intent="quest",
            )
        )
        if len(out) == limit:
            break
    return out


def _quest_beat_sort_key(node: GraphNode) -> tuple[int, str]:
    turn_id = node.properties.get("turn_id")
    return (turn_id if isinstance(turn_id, int) else -1, node.id)


def _visible_character_refs(runtime: GameRuntimeState) -> set[str]:
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
        refs.update(_node_refs(runtime, character_id))
    return refs


def _usable_refs(runtime: GameRuntimeState) -> set[str]:
    refs: set[str] = set()
    player_id = runtime.progress.player_id
    for item_id in inventory_of(runtime.graph_index, player_id):
        refs.update(_node_refs(runtime, item_id))
    for skill_edge in known_skills_of(runtime.graph_index, player_id):
        refs.update(_node_refs(runtime, skill_edge.to_node_id))
    return refs


def _node_refs(runtime: GameRuntimeState, node_id: str) -> set[str]:
    node = runtime.graph.nodes.get(node_id)
    if node is None:
        return {node_id}
    return {node_id, node_label(runtime.content, node)}


def _mentions_any(suggestion: GraphSuggestion, refs: set[str]) -> bool:
    text = _normalize(f"{suggestion.label} {suggestion.input_text}")
    return any(_normalize(ref) in text for ref in refs if _normalize(ref))


def _input_mentions_any(suggestion: GraphSuggestion, refs: set[str]) -> bool:
    text = _normalize(suggestion.input_text)
    return any(_normalize(ref) in text for ref in refs if _normalize(ref))


def _normalize(value: str) -> str:
    return "".join(ch for ch in value.lower() if ch.isalnum())


def normalize_suggestion(value: object) -> GraphSuggestion | None:
    if isinstance(value, GraphSuggestion):
        label = value.label.strip()
        input_text = value.input_text.strip()
        if not label or not input_text:
            return None
        if _is_targetless_generic_suggestion(label, input_text):
            return None
        return value.model_copy(update={"label": label, "input_text": input_text})
    if isinstance(value, dict):
        raw_label = value.get("label")
        raw_input_text = value.get("input_text")
        if not isinstance(raw_label, str) or not isinstance(raw_input_text, str):
            return None
        label = raw_label.strip()
        input_text = raw_input_text.strip()
        if not label or not input_text:
            return None
        if _looks_like_json_fragment(label) or _looks_like_json_fragment(input_text):
            return None
        if _is_targetless_generic_suggestion(label, input_text):
            return None
        intent = value.get("intent")
        return GraphSuggestion(
            label=label,
            input_text=input_text,
            intent=intent.strip() if isinstance(intent, str) and intent.strip() else None,
            action=value.get("action")
            if isinstance(value.get("action"), dict)
            else None,
        )
    return None


def _looks_like_json_fragment(text: str) -> bool:
    if text.startswith(("{", "[")):
        return True
    lowered = text.lower()
    return '"label"' in lowered or '"input_text"' in lowered or '"input_te' in lowered


def _is_targetless_generic_suggestion(label: str, input_text: str) -> bool:
    generic = set(TARGETLESS_GENERIC_SUGGESTIONS)
    normalized_label = _normalize(label)
    normalized_input = _normalize(input_text)
    targetless_talk = _targetless_talk_labels()
    if normalized_label in targetless_talk:
        return True
    if _has_targeted_generic_talk_label(normalized_label, targetless_talk):
        return True
    if normalized_label in generic and normalized_input in generic:
        return True
    if normalized_label != normalized_input:
        return False
    return any(phrase in normalized_label for phrase in targetless_talk)


def _targetless_talk_labels() -> set[str]:
    return {_normalize(value) for value in TARGETLESS_TALK_LABELS}


def _has_targeted_generic_talk_label(
    normalized_label: str,
    targetless_talk: set[str],
) -> bool:
    target_particles = {_normalize(value) for value in TARGET_PARTICLES}
    return any(
        f"{particle}{phrase}" in normalized_label
        for particle in target_particles
        for phrase in targetless_talk
    )


def _has_quest_status(runtime: GameRuntimeState, statuses: set[str]) -> bool:
    for node in runtime.graph.nodes.values():
        if node.type != "quest":
            continue
        status = node.properties.get("status")
        if isinstance(status, str) and status in statuses:
            return True
    return False
