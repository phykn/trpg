import re
from typing import Any

from src.game.domain.action import Action
from src.game.domain.content import node_label, node_text, node_value
from src.game.domain.graph import GraphNode
from src.game.domain.graph.character import graph_character_kind, is_visible_character
from src.game.domain.memory import RollLogEntry
from src.game.domain.graph.query import (
    characters_at,
    edges_from,
    inventory_of,
    items_at,
    location_of,
)
from src.locale.render import render

from ..action.dispatch import GraphActionDispatchResult
from ..env import env_nonnegative_int
from ..state import GameRuntimeState
from .combat_view import combat_narration_view
from .memory_context import (
    narrate_recent_dialogue_payload,
    related_memory_payload,
)


def build_action_narration_payload(
    *,
    before: GameRuntimeState,
    after: GameRuntimeState,
    action: Action,
    dispatch: GraphActionDispatchResult,
    card_texts: list[str],
) -> dict[str, Any]:
    place_id = location_of(after.graph_index, after.progress.player_id)
    place = after.graph.nodes.get(place_id or "")
    target = _action_target(after, action)
    scene_anchor = _scene_anchor(after)
    current_event = {
        "kind": dispatch.kind,
        "outcome": dispatch.outcome,
        "action": action.model_dump(mode="json", by_alias=True, exclude_none=True),
        "resolved_results": card_texts,
    }
    quest_trigger = _quest_trigger_payload(action, dispatch.kind)
    if quest_trigger is not None:
        current_event["quest_trigger"] = quest_trigger
    payload = {
        "world_guidance": _world_guidance(after),
        "player_input": None,
        "current_place": _node_ref(after, place),
        "current_event": current_event,
        "scene_anchor": scene_anchor,
        "target_view": _target_view(after, target),
        "result_cards": _result_cards(card_texts),
        "related_memory": related_memory_payload(
            after,
            action=action,
            target=target,
        ),
        "recent_narration": _recent_narration_payload(before),
        "recent_dialogue": narrate_recent_dialogue_payload(
            after,
            target=target.id if target is not None else None,
        ),
        "combat_view": combat_narration_view(
            after,
            trace=dispatch.combat_trace,
            outcome=dispatch.outcome,
        ),
        "budget": _narrate_budget(after),
    }
    return compact_narration_payload(payload)


def build_roll_narration_payload(
    *,
    runtime: GameRuntimeState,
    action: Action,
    pending: dict[str, Any],
    roll_entry: RollLogEntry,
    outcome: str,
    result_texts: list[str] | None = None,
) -> dict[str, Any]:
    target = _action_target(runtime, action)
    check_reason = pending.get("check_reason")
    if not isinstance(check_reason, str):
        check_reason = pending.get("body")
    preroll_narration = pending.get("body")
    player_input = pending.get("player_input")
    resolved_results = result_texts or [
        _roll_result_card(roll_entry, outcome, runtime.progress.locale)
    ]
    payload = {
        "world_guidance": _world_guidance(runtime),
        "player_input": player_input if isinstance(player_input, str) else None,
        "current_event": {
            "kind": "roll",
            "outcome": outcome,
            "action": action.model_dump(mode="json", by_alias=True, exclude_none=True),
            "check_reason": check_reason if isinstance(check_reason, str) else "",
            "preroll_narration": (
                preroll_narration if isinstance(preroll_narration, str) else ""
            ),
            "roll": {
                "check": roll_entry.check,
                "result": roll_entry.result,
                "margin": roll_entry.margin,
            },
            "resolved_results": resolved_results,
        },
        "scene_anchor": _scene_anchor(runtime),
        "target_view": _target_view(runtime, target),
        "result_cards": _result_cards(resolved_results),
        "related_memory": related_memory_payload(
            runtime,
            action=action,
            target=target,
        ),
        "recent_narration": _recent_narration_payload(
            runtime,
            exclude_texts=[
                text
                for text in (check_reason, preroll_narration)
                if isinstance(text, str)
            ],
        ),
        "recent_dialogue": narrate_recent_dialogue_payload(
            runtime,
            target=target.id if target is not None else None,
        ),
        "combat_view": combat_narration_view(runtime),
        "budget": _narrate_budget(runtime),
    }
    return compact_narration_payload(payload)


def build_input_narration_payload(
    *,
    runtime: GameRuntimeState,
    player_input: str,
    action: Action,
    dialogue_target: GraphNode | None,
) -> dict[str, Any]:
    payload = {
        "world_guidance": _world_guidance(runtime),
        "player_input": player_input,
        "current_event": _input_current_event(runtime, action, dialogue_target),
        "scene_anchor": _scene_anchor(runtime),
        "target_view": _target_view(
            runtime,
            dialogue_target,
            player_input=player_input,
        ),
        "result_cards": [],
        "related_memory": related_memory_payload(
            runtime,
            action=action,
            target=dialogue_target,
        ),
        "recent_narration": _recent_narration_payload(runtime),
        "recent_dialogue": narrate_recent_dialogue_payload(
            runtime,
            target=dialogue_target.id if dialogue_target is not None else None,
        ),
        "combat_view": combat_narration_view(runtime),
        "budget": _narrate_budget(runtime),
    }
    return compact_narration_payload(payload)


def compact_narration_payload(source: dict[str, Any]) -> dict[str, Any]:
    """Build the compact LLM contract: request, event, scene, references."""
    event = source.get("current_event")
    scene_state = {
        "current_place": source.get("current_place"),
        "scene_anchor": source.get("scene_anchor"),
        "target_view": source.get("target_view"),
    }
    payload = {
        "user_request": {
            "player_input": source.get("player_input"),
        },
        "engine_event": event,
        "scene_state": scene_state,
        "result_cards": source.get("result_cards"),
        "combat_view": source.get("combat_view"),
        "reference_context": {
            "world_guidance": source.get("world_guidance"),
            "related_memory": source.get("related_memory"),
            "recent_dialogue": source.get("recent_dialogue"),
            "recent_narration": source.get("recent_narration"),
        },
        "budget": source.get("budget"),
    }
    return _drop_empty_narration_values(payload)


def update_compact_narration_event(
    payload: dict[str, Any],
    event: dict[str, Any],
    *,
    player_input: str | None = None,
    result_cards: list[dict[str, Any]] | None = None,
) -> None:
    payload["engine_event"] = event
    if player_input is not None:
        payload["user_request"] = {"player_input": player_input}
    elif "user_request" in payload:
        payload.pop("user_request")
    if result_cards is not None:
        payload["result_cards"] = result_cards


def _drop_empty_narration_values(value: Any) -> Any:
    if isinstance(value, dict):
        out = {}
        for key, item in value.items():  # ssot-allow: recursive payload cleanup
            cleaned = _drop_empty_narration_values(item)
            if cleaned is None or cleaned == [] or cleaned == {}:
                continue
            out[key] = cleaned
        return out
    if isinstance(value, list):
        return [_drop_empty_narration_values(item) for item in value]
    return value


def _place_payload(
    runtime: GameRuntimeState,
    node: GraphNode | None,
) -> dict[str, Any] | None:
    if node is None or node.type != "location":
        return None
    payload = {"id": node.id, "name": node_label(runtime.content, node)}
    description = node_text(runtime.content, node, "description")
    if description:
        payload["description"] = description
    _add_text_field(runtime, node, payload, "mood")
    _add_list_field(runtime, node, payload, "traits")
    return payload


def _world_guidance(runtime: GameRuntimeState) -> str | None:
    text = runtime.content.world_guidance.strip()
    if not text:
        return None
    max_chars = env_nonnegative_int("GRAPH_NARRATION_WORLD_GUIDANCE_CHARS", 1600)
    return text[:max_chars]


def _visible_character_payloads(
    runtime: GameRuntimeState,
    place_id: str | None,
    *,
    exclude_id: str,
) -> list[dict[str, Any]]:
    if place_id is None:
        return []
    out: list[dict[str, str]] = []
    for character_id in characters_at(runtime.graph_index, place_id):
        if character_id == exclude_id:
            continue
        node = runtime.graph.nodes.get(character_id)
        if node is None or node.type != "character" or not is_visible_character(node):
            continue
        payload: dict[str, Any] = {
            "id": node.id,
            "name": node_label(runtime.content, node),
            "type": graph_character_kind(node),
        }
        _add_character_style_fields(runtime, node, payload)
        dialogue_style = _dialogue_style_payload(runtime, node)
        if dialogue_style:
            payload["dialogue_style"] = dialogue_style
        mbti = _mbti_payload(runtime, node)
        if mbti:
            payload["mbti"] = mbti
        out.append(payload)
    return out


def _visible_item_payloads(
    runtime: GameRuntimeState,
    place_id: str | None,
) -> list[dict[str, Any]]:
    if place_id is None:
        return []
    out: list[dict[str, str]] = []
    for item_id in items_at(runtime.graph_index, place_id):
        item = runtime.graph.nodes.get(item_id)
        if item is None or item.type != "item":
            continue
        out.append(_item_payload(runtime, item))
    return out


def _exit_payloads(
    runtime: GameRuntimeState,
    place_id: str | None,
) -> list[dict[str, str]]:
    if place_id is None:
        return []
    out: list[dict[str, str]] = []
    for edge in edges_from(runtime.graph_index, place_id, "connects_to"):
        target = runtime.graph.nodes.get(edge.to_node_id)
        if target is not None and target.type == "location":
            out.append({"id": target.id, "name": node_label(runtime.content, target)})
    return out


def _inventory_payloads(
    runtime: GameRuntimeState,
    player_id: str,
) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for item_id in inventory_of(runtime.graph_index, player_id):
        item = runtime.graph.nodes.get(item_id)
        if item is not None and item.type == "item":
            out.append(_item_payload(runtime, item))
    return out


def _item_payload(runtime: GameRuntimeState, item: GraphNode) -> dict[str, Any]:
    kind = node_value(runtime.content, item, "kind") or node_value(
        runtime.content,
        item,
        "type",
    )
    payload: dict[str, Any] = {
        "id": item.id,
        "name": node_label(runtime.content, item),
        "kind": kind if isinstance(kind, str) and kind else "item",
    }
    description = node_text(runtime.content, item, "description")
    if description:
        payload["description"] = description
    _add_list_field(runtime, item, payload, "traits")
    return payload


def _node_ref(runtime: GameRuntimeState, node: GraphNode | None) -> dict[str, str]:
    if node is None:
        return {"id": "", "name": render("runtime.none", runtime.progress.locale)}
    return {"id": node.id, "name": node_label(runtime.content, node)}


def _scene_anchor(runtime: GameRuntimeState) -> dict[str, Any]:
    graph = runtime.graph_index
    player_id = runtime.progress.player_id
    place_id = location_of(graph, player_id)
    place = runtime.graph.nodes.get(place_id or "")
    visible_names = [
        entry["name"]
        for entry in [
            *_visible_character_payloads(runtime, place_id, exclude_id=player_id),
            *_visible_item_payloads(runtime, place_id),
            *_exit_payloads(runtime, place_id),
        ][:5]
    ]
    return {
        "location": _node_ref(runtime, place),
        "visible_names": visible_names,
    }


def _target_view(
    runtime: GameRuntimeState,
    node: GraphNode | None,
    *,
    player_input: str | None = None,
) -> dict[str, Any] | None:
    if node is None:
        return None
    payload = _node_ref(runtime, node)
    payload["type"] = node.type
    role = node_value(runtime.content, node, "role")
    if isinstance(role, str) and role:
        payload["known_role"] = role
    tone_hint = node_text(runtime.content, node, "tone_hint")
    if tone_hint:
        payload["tone_hint"] = tone_hint
    _add_character_style_fields(runtime, node, payload)
    faction = _faction_payload(runtime, node)
    if faction:
        payload["faction"] = faction
    dialogue_style = _dialogue_style_payload(runtime, node)
    if dialogue_style:
        payload["dialogue_style"] = dialogue_style
    mbti = _mbti_payload(runtime, node)
    if mbti:
        payload["mbti"] = mbti
    public_knowledge = _public_knowledge_payloads(runtime, node)
    if public_knowledge:
        payload["public_knowledge"] = public_knowledge
    available_items = _mentioned_inventory_payloads(runtime, node, player_input)
    if available_items:
        payload["available_items"] = available_items
    return payload


def _mentioned_inventory_payloads(
    runtime: GameRuntimeState,
    node: GraphNode,
    player_input: str | None,
) -> list[dict[str, Any]]:
    if node.type != "character" or not player_input:
        return []
    out: list[dict[str, Any]] = []
    for item_id in inventory_of(runtime.graph_index, node.id):
        item = runtime.graph.nodes.get(item_id)
        if item is None or item.type != "item":
            continue
        if not _item_mentioned(
            player_input, node_label(runtime.content, item), item.id
        ):
            continue
        payload: dict[str, Any] = _item_payload(runtime, item)
        price = node_value(runtime.content, item, "price")
        if isinstance(price, int | float):
            payload["price"] = price
        out.append(payload)
    return out


def _item_mentioned(player_input: str, item_name: str, item_id: str) -> bool:
    normalized_input = _normalize_for_match(player_input)
    normalized_name = _normalize_for_match(item_name)
    if normalized_name and normalized_name in normalized_input:
        return True
    normalized_id = _normalize_for_match(item_id)
    if normalized_id and normalized_id in normalized_input:
        return True
    name_tokens = [
        _normalize_for_match(token)
        for token in re.split(r"\s+", item_name)
        if len(_normalize_for_match(token)) >= 2
    ]
    return sum(1 for token in name_tokens if token in normalized_input) >= 2


def _normalize_for_match(text: str) -> str:
    hangul_range = f"{chr(0xAC00)}-{chr(0xD7A3)}"
    return re.sub(rf"[^0-9A-Za-z{hangul_range}]+", "", text).lower()


def _string_list_value(
    runtime: GameRuntimeState,
    node: GraphNode,
    key: str,
) -> list[str]:
    value = node_value(runtime.content, node, key)
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str) and item]


def _add_text_field(
    runtime: GameRuntimeState,
    node: GraphNode,
    payload: dict[str, Any],
    key: str,
) -> None:
    value = node_text(runtime.content, node, key)
    if value:
        payload[key] = value


def _add_list_field(
    runtime: GameRuntimeState,
    node: GraphNode,
    payload: dict[str, Any],
    key: str,
) -> None:
    values = _string_list_value(runtime, node, key)
    if values:
        payload[key] = values


def _add_character_style_fields(
    runtime: GameRuntimeState,
    node: GraphNode,
    payload: dict[str, Any],
) -> None:
    for key in ("personality", "traits"):
        _add_list_field(runtime, node, payload, key)
    for key in ("background", "appearance", "personal_boundary"):
        _add_text_field(runtime, node, payload, key)


def _faction_payload(
    runtime: GameRuntimeState,
    node: GraphNode,
) -> dict[str, Any] | None:
    if node.type != "character":
        return None
    for edge in edges_from(runtime.graph_index, node.id, "member_of_faction"):
        faction = runtime.graph.nodes.get(edge.to_node_id)
        if faction is None or faction.type != "faction":
            continue
        payload: dict[str, Any] = {
            "id": faction.id,
            "name": node_label(runtime.content, faction),
        }
        description = node_text(runtime.content, faction, "description")
        if description:
            payload["description"] = description
        _add_list_field(runtime, faction, payload, "traits")
        return payload
    return None


def _dialogue_style_payload(
    runtime: GameRuntimeState,
    node: GraphNode,
) -> dict[str, Any] | None:
    if node.type != "character":
        return None
    for edge in edges_from(runtime.graph_index, node.id, "uses_dialogue_style"):
        style = runtime.graph.nodes.get(edge.to_node_id)
        if style is None or style.type != "dialogue_style":
            continue
        payload: dict[str, Any] = {
            "id": style.id,
            "name": node_label(runtime.content, style),
        }
        for key in ("speech_style", "humor_style"):
            _add_text_field(runtime, style, payload, key)
        _add_list_field(runtime, style, payload, "traits")
        return payload
    return None


def _mbti_payload(
    runtime: GameRuntimeState,
    node: GraphNode,
) -> dict[str, Any] | None:
    if node.type != "character":
        return None
    for edge in edges_from(runtime.graph_index, node.id, "has_mbti"):
        mbti = runtime.graph.nodes.get(edge.to_node_id)
        if mbti is None or mbti.type != "mbti":
            continue
        payload: dict[str, Any] = {"id": mbti.id}
        for key in (
            "attitude",
            "speech_style",
            "personality",
            "boundary_style",
            "humor_style",
            "decision_style",
            "stress_response",
            "trust_response",
            "conflict_style",
        ):
            _add_text_field(runtime, mbti, payload, key)
        for key in ("roleplay_cues", "avoid"):
            _add_list_field(runtime, mbti, payload, key)
        return payload
    return None


def _public_knowledge_payloads(
    runtime: GameRuntimeState,
    node: GraphNode,
) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for edge in edges_from(runtime.graph_index, node.id, "has_knowledge"):
        knowledge = runtime.graph.nodes.get(edge.to_node_id)
        if knowledge is None or knowledge.type != "knowledge":
            continue
        visibility = node_value(runtime.content, knowledge, "visibility")
        if visibility != "public":
            continue
        payload: dict[str, str] = {"id": knowledge.id}
        title = node_value(runtime.content, knowledge, "title")
        if isinstance(title, str) and title:
            payload["title"] = title
        summary = node_value(runtime.content, knowledge, "summary")
        if isinstance(summary, str) and summary:
            payload["summary"] = summary
        if len(payload) > 1:
            out.append(payload)
    return out


def _input_current_event(
    runtime: GameRuntimeState,
    action: Action,
    dialogue_target: GraphNode | None,
) -> dict[str, Any]:
    event: dict[str, Any] = {
        "kind": "dialogue" if dialogue_target is not None else "input",
        "target": _target_view(runtime, dialogue_target),
        "action": action.model_dump(mode="json", by_alias=True, exclude_none=True),
        "outcome": (
            "player_addresses_target"
            if dialogue_target is not None
            else "player_action_pending_narration"
        ),
    }
    if dialogue_target is not None:
        event["dialogue_expectation"] = {
            "npc_reply": "expected",
            "direct_speech": "prefer_one_short_utterance",
        }
    return event


def _quest_trigger_payload(action: Action, kind: str) -> dict[str, str] | None:
    if kind == "move":
        target = _single(action.to) or _single(action.what)
        if target is not None:
            return {"type": "location_enter", "target": target}
    return None


def _result_cards(card_texts: list[str]) -> list[dict[str, str]]:
    return [{"text": text} for text in card_texts if text]


def _roll_result_card(roll_entry: RollLogEntry, outcome: str, locale: str) -> str:
    key = (
        "runtime.roll.result.success"
        if outcome == "success"
        else "runtime.roll.result.failure"
    )
    return render(key, locale, check=roll_entry.check)


def _recent_narration_payload(
    runtime: GameRuntimeState,
    *,
    limit: int = 3,
    max_chars: int = 160,
    exclude_texts: list[str] | None = None,
) -> list[dict[str, Any]]:
    excluded = {text.strip() for text in (exclude_texts or []) if text.strip()}
    entries = [
        entry
        for entry in runtime.log_entries
        if entry.kind == "gm"
        and entry.text.strip()
        and entry.text.strip() not in excluded
    ][-limit:]
    return [
        {
            "text": entry.text.strip()[:max_chars],
            "outcome": entry.outcome,
        }
        for entry in entries
    ]


def _narrate_budget(runtime: GameRuntimeState) -> dict[str, int]:
    place_id = location_of(runtime.graph_index, runtime.progress.player_id)
    visible_count = (
        len(
            _visible_character_payloads(
                runtime, place_id, exclude_id=runtime.progress.player_id
            )
        )
        + len(_visible_item_payloads(runtime, place_id))
        + len(_exit_payloads(runtime, place_id))
    )
    return {
        "visible_names_omitted": max(0, visible_count - 5),
        "related_memory_omitted": 0,
        "recent_dialogue_omitted": max(0, len(runtime.recent_dialogue) - 5),
        "result_cards_omitted": 0,
    }


def _action_target(runtime: GameRuntimeState, action: Action) -> GraphNode | None:
    target = _single(action.what) or _single(action.to)
    return runtime.graph.nodes.get(target or "")


def _single(value: object) -> str | None:
    if isinstance(value, str):
        return value
    if isinstance(value, list) and value and isinstance(value[0], str):
        return value[0]
    return None
