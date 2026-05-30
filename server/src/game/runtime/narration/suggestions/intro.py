from __future__ import annotations

from src.game.domain.content import node_label
from src.game.domain.graph import GraphNode
from src.game.domain.graph.character import is_visible_character
from src.game.domain.graph.query import (
    characters_at,
    connection_is_unlocked,
    edges_from,
    location_of,
)
from src.locale.ko.suggestion_text import (
    ko_as_ask,
    ko_ask_label,
    ko_at_topic,
    ko_close_quote,
    ko_current_situation,
    ko_direction_particle,
    ko_here,
    ko_inspect,
    ko_inspect_label,
    ko_meaning,
    ko_move,
    ko_object,
    ko_open_quote,
    ko_possessive,
    ko_room,
    ko_room_question,
    ko_situation,
    ko_surroundings,
    ko_to_person,
    ko_what_to_check_question,
)

from ...state import GameRuntimeState
from .model import GraphSuggestion
from .refs import move_edge_priority


def build_intro_suggestions(runtime: GameRuntimeState) -> list[GraphSuggestion]:
    suggestions: list[GraphSuggestion] = []
    suggestions.extend(intro_talk_suggestions(runtime, limit=1))
    suggestions.extend(intro_quest_beat_suggestions(runtime, limit=1))
    suggestions.extend(intro_move_suggestions(runtime, limit=1))
    suggestions.append(
        GraphSuggestion(
            label=f"{ko_surroundings()} {ko_inspect_label()}",
            input_text=f"{ko_surroundings()}{ko_object()} {ko_inspect()}",
            intent="inspect",
        )
    )
    return suggestions[:3]


def intro_talk_suggestions(
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
        topic, question = intro_talk_topic(runtime, place_id)
        out.append(
            GraphSuggestion(
                label=f"{topic} {ko_ask_label()}",
                input_text=(
                    f"{name}{ko_to_person()} "
                    f"{ko_open_quote()}{question}{ko_close_quote()}{ko_as_ask()}"
                ),
                intent="talk",
            )
        )
        if len(out) == limit:
            break
    return out


def intro_talk_topic(
    runtime: GameRuntimeState,
    place_id: str,
) -> tuple[str, str]:
    node = runtime.graph.nodes.get(place_id)
    place_name = node_label(runtime.content, node).strip() if node is not None else ""
    if ko_room() in place_name:
        return (
            f"{ko_room()}{ko_possessive()} {ko_meaning()}",
            ko_room_question(),
        )
    if place_name:
        return (
            f"{place_name} {ko_situation()}",
            f"{place_name}{ko_at_topic()} {ko_what_to_check_question()}",
        )
    return (
        ko_current_situation(),
        f"{ko_here()}{ko_at_topic()} {ko_what_to_check_question()}",
    )


def intro_move_suggestions(
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
        key=move_edge_priority,
    ):
        if not connection_is_unlocked(runtime.graph_index, edge):
            continue
        node = runtime.graph.nodes.get(edge.to_node_id)
        if node is None or node.type != "location":
            continue
        name = node_label(runtime.content, node)
        out.append(
            GraphSuggestion(
                label=f"{name}{ko_direction_particle(name)}",
                input_text=f"{name}{ko_direction_particle(name)} {ko_move()}",
                intent="move",
            )
        )
        if len(out) == limit:
            break
    return out


def intro_quest_beat_suggestions(
    runtime: GameRuntimeState,
    *,
    limit: int,
) -> list[GraphSuggestion]:
    out: list[GraphSuggestion] = []
    for node in sorted(
        runtime.graph.nodes.values(),
        key=quest_beat_sort_key,
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


def quest_beat_sort_key(node: GraphNode) -> tuple[int, str]:
    turn_id = node.properties.get("turn_id")
    return (turn_id if isinstance(turn_id, int) else -1, node.id)
