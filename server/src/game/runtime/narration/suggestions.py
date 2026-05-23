from typing import Any

from pydantic import BaseModel

from src.game.domain.content import node_label
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

from ..state import GameRuntimeState


class GraphSuggestion(BaseModel):
    label: str
    input_text: str
    intent: str | None = None
    action: dict[str, Any] | None = None


def build_intro_suggestions(runtime: GameRuntimeState) -> list[GraphSuggestion]:
    suggestions: list[GraphSuggestion] = []
    suggestions.extend(_intro_talk_suggestions(runtime, limit=1))
    suggestions.extend(_intro_move_suggestions(runtime, limit=1))
    suggestions.append(
        GraphSuggestion(
            label="inspect",
            input_text=f"{_ko_surroundings()}{_ko_object()} {_ko_inspect()}",
            intent="inspect",
        )
    )
    return suggestions[:3]


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
    for edge in edges_from(runtime.graph_index, place_id, "connects_to"):
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
        out.append(
            GraphSuggestion(
                label="talk",
                input_text=f"{name}{_ko_to_person()} {_ko_start_talk()}",
                intent="talk",
            )
        )
        if len(out) == limit:
            break
    return out


def _intro_move_suggestions(
    runtime: GameRuntimeState,
    *,
    limit: int,
) -> list[GraphSuggestion]:
    place_id = location_of(runtime.graph_index, runtime.progress.player_id)
    if place_id is None:
        return []
    out: list[GraphSuggestion] = []
    for edge in edges_from(runtime.graph_index, place_id, "connects_to"):
        if not connection_is_unlocked(runtime.graph_index, edge):
            continue
        node = runtime.graph.nodes.get(edge.to_node_id)
        if node is None or node.type != "location":
            continue
        name = node_label(runtime.content, node)
        out.append(
            GraphSuggestion(
                label="move",
                input_text=f"{name}{_ko_direction_particle(name)} {_ko_move()}",
                intent="move",
            )
        )
        if len(out) == limit:
            break
    return out


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
    generic = {
        _codepoint_text(0xB300, 0xD654, 0xC2DC, 0xC791, 0xD558, 0xAE30),
        _codepoint_text(0xB300, 0xD654, 0xC2DC, 0xB3C4, 0xD558, 0xAE30),
        _codepoint_text(0xB9D0, 0xAC78, 0xAE30),
        _codepoint_text(0xB9D0, 0xC744, 0xAC74, 0xB2E4),
        _codepoint_text(0xC0C1, 0xD669, 0xD30C, 0xC545, 0xD558, 0xAE30),
    }
    return _normalize(label) in generic and _normalize(input_text) in generic


def _codepoint_text(*values: int) -> str:
    return "".join(chr(value) for value in values)


def _has_quest_status(runtime: GameRuntimeState, statuses: set[str]) -> bool:
    for node in runtime.graph.nodes.values():
        if node.type != "quest":
            continue
        status = node.properties.get("status")
        if isinstance(status, str) and status in statuses:
            return True
    return False


def _ko_accept() -> str:
    return chr(0xC218) + chr(0xB77D)


def _ko_abandon() -> str:
    return chr(0xD3EC) + chr(0xAE30)


def _ko_object() -> str:
    return chr(0xC744)


def _ko_to_person() -> str:
    return chr(0xC5D0) + chr(0xAC8C)


def _ko_start_talk() -> str:
    return _codepoint_text(0xB9D0, 0xC744, 0x20, 0xAC81, 0xB2C8, 0xB2E4)


def _ko_inspect() -> str:
    return _codepoint_text(0xC0B4, 0xD54D, 0xB2C8, 0xB2E4)


def _ko_move() -> str:
    return _codepoint_text(0xC774, 0xB3D9, 0xD569, 0xB2C8, 0xB2E4)


def _ko_surroundings() -> str:
    return chr(0xC8FC) + chr(0xBCC0)


def _ko_possessive() -> str:
    return chr(0xC758)


def _ko_direction_particle(text: str) -> str:
    if not text:
        return _ko_direction_with_final()
    code = ord(text[-1])
    if not (0xAC00 <= code <= 0xD7A3):
        return _ko_direction_with_final()
    final = (code - 0xAC00) % 28
    return _ko_direction_without_final() if final == 0 or final == 8 else _ko_direction_with_final()


def _ko_direction_without_final() -> str:
    return chr(0xB85C)


def _ko_direction_with_final() -> str:
    return chr(0xC73C) + chr(0xB85C)
