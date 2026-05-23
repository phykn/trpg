from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from src.game.domain.content import node_label, node_value
from src.game.domain.graph import GraphNode
from src.game.domain.graph.character import graph_character_kind, is_visible_character
from src.game.domain.graph.query import (
    characters_at,
    edges_from,
    equipment_of,
    inventory_of,
    items_at,
    known_skills_of,
    location_of,
)
from src.game.runtime.state import GameRuntimeState


@dataclass(frozen=True)
class ClassifyContextLimits:
    recent_scene: int = 3
    # Recent player input + narrator reply pairs used for pronoun/context resolution.
    recent_exchanges: int = 3


def build_classify_context_view(
    runtime: GameRuntimeState,
    player_input: str,
    *,
    limits: ClassifyContextLimits | None = None,
) -> dict[str, Any]:
    limits = limits or ClassifyContextLimits()
    graph = runtime.graph_index
    player_id = runtime.progress.player_id
    location_id = location_of(graph, player_id)
    location = graph.nodes.get(location_id or "")
    visible_targets = _visible_targets(runtime, location_id)
    exits = _exits(runtime, location_id)
    inventory = _inventory(runtime, player_id)
    skills = _skills(runtime, player_id)
    location_items = _location_items(runtime, location_id)
    corpses = _corpses(runtime, location_id)

    active_quest = _active_quest(runtime)
    available_quests = _available_quests(runtime, visible_targets, active_quest)

    return {
        "mode": (
            "combat"
            if runtime.progress.graph_combat_state is not None
            else "exploration"
        ),
        "identity": {
            "player": _node_ref(runtime, runtime.graph.nodes.get(player_id)),
            "location": _node_ref(runtime, location),
            "active_quest": active_quest,
            "available_quests": available_quests,
            "visible_targets": visible_targets,
            "exits": exits,
            "inventory": inventory,
            "equipment": _equipment(runtime, player_id),
            "skills": skills,
            "location_items": location_items,
            "merchants": _merchants(runtime, visible_targets),
            "corpses": corpses,
        },
        "affordances": {
            "can_speak_to": [
                target["id"]
                for target in visible_targets
                if target["type"] in {"npc", "enemy"}
            ],
            "can_attack": _attackable_ids(visible_targets),
            "can_move_to": [exit_["id"] for exit_ in exits],
            "can_use": [item["id"] for item in inventory],
            "can_pick_up": [item["id"] for item in location_items],
            "can_accept_or_abandon_quest": _quest_ids(runtime, available_quests),
            "can_decide": _quest_choice_ids(runtime),
        },
        "references": {
            "recent_scene": _recent_scene(runtime, limits),
            "recent_exchanges": _recent_exchanges(runtime, limits),
            "last_npc": _last_entity_ref(runtime, entity_types={"character"}),
            "last_target": _last_entity_ref(runtime),
            "last_item": _last_entity_ref(runtime, entity_types={"item"}),
        },
    }


def classify_context_to_grounding_view(context: dict[str, Any]) -> dict[str, Any]:
    identity = (
        context.get("identity") if isinstance(context.get("identity"), dict) else {}
    )
    references = (
        context.get("references") if isinstance(context.get("references"), dict) else {}
    )
    player = (
        identity.get("player") if isinstance(identity.get("player"), dict) else None
    )
    active_quest = (
        identity.get("active_quest")
        if isinstance(identity.get("active_quest"), dict)
        else None
    )
    available_quests = _dicts(identity.get("available_quests"))
    visible_targets = _dicts(identity.get("visible_targets"))
    exits = _dicts(identity.get("exits"))

    grounding_targets = [
        {
            **target,
            "type": target["type"] if target.get("type") in {"npc", "enemy"} else "npc",
        }
        for target in visible_targets
        if isinstance(target.get("id"), str) and isinstance(target.get("name"), str)
    ]

    return {
        "in_combat": context.get("mode") == "combat",
        "location": identity.get("location") or {},
        "entities": [
            *(
                [{"id": player["id"], "name": player["name"], "type": "player"}]
                if isinstance(player, dict)
                and isinstance(player.get("id"), str)
                and isinstance(player.get("name"), str)
                else []
            ),
            *grounding_targets,
            *[
                {"id": exit_["id"], "name": exit_["name"], "type": "connection"}
                for exit_ in exits
                if isinstance(exit_.get("id"), str)
                and isinstance(exit_.get("name"), str)
            ],
        ],
        "inventory": _dicts(identity.get("inventory")),
        "equipment": identity.get("equipment") or {},
        "skills": _dicts(identity.get("skills")),
        "location_items": _dicts(identity.get("location_items")),
        "merchants": _dicts(identity.get("merchants")),
        "corpses": _dicts(identity.get("corpses")),
        "quests": [
            *([active_quest] if active_quest is not None else []),
            *available_quests,
        ],
        "recent_npc": references.get("last_npc"),
    }


def _visible_targets(
    runtime: GameRuntimeState,
    location_id: str | None,
) -> list[dict[str, Any]]:
    if location_id is None:
        return []
    out: list[dict[str, Any]] = []
    for character_id in characters_at(runtime.graph_index, location_id):
        if character_id == runtime.progress.player_id:
            continue
        node = runtime.graph.nodes.get(character_id)
        if node is None or node.type != "character" or not is_visible_character(node):
            continue
        payload: dict[str, Any] = {
            "id": node.id,
            "name": node_label(runtime.content, node),
            "type": graph_character_kind(node),
        }
        if node.properties.get("protected") is True:
            payload["protected"] = True
        out.append(payload)
    return out


def _exits(runtime: GameRuntimeState, location_id: str | None) -> list[dict[str, str]]:
    if location_id is None:
        return []
    out: list[dict[str, str]] = []
    for edge in edges_from(runtime.graph_index, location_id, "connects_to"):
        node = runtime.graph.nodes.get(edge.to_node_id)
        if node is not None and node.type == "location":
            out.append({"id": node.id, "name": node_label(runtime.content, node)})
    return out


def _inventory(runtime: GameRuntimeState, player_id: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for item_id in inventory_of(runtime.graph_index, player_id):
        node = runtime.graph.nodes.get(item_id)
        if node is None or node.type != "item":
            continue
        out.append(_item_payload(runtime, node))
    return out


def _inventory_for_owner(
    runtime: GameRuntimeState,
    owner_id: str,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for item_id in inventory_of(runtime.graph_index, owner_id):
        node = runtime.graph.nodes.get(item_id)
        if node is None or node.type != "item":
            continue
        out.append(_item_payload(runtime, node))
    return out


def _equipment(
    runtime: GameRuntimeState,
    player_id: str,
) -> dict[str, dict[str, str] | None]:
    equipment: dict[str, dict[str, str] | None] = {
        "weapon": None,
        "armor": None,
        "accessory": None,
    }
    for edge in equipment_of(runtime.graph_index, player_id):
        slot = edge.properties.get("slot")
        if slot not in equipment:
            continue
        node = runtime.graph.nodes.get(edge.to_node_id)
        if node is not None and node.type == "item":
            equipment[slot] = {"id": node.id, "name": node_label(runtime.content, node)}
    return equipment


def _skills(runtime: GameRuntimeState, player_id: str) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for edge in known_skills_of(runtime.graph_index, player_id):
        node = runtime.graph.nodes.get(edge.to_node_id)
        if node is not None and node.type == "skill":
            payload = {"id": node.id, "name": node_label(runtime.content, node)}
            action = node_value(
                runtime.content,
                node,
                "action",
            )
            if isinstance(action, str) and action:
                payload["action"] = action
            out.append(payload)
    return out


def _location_items(
    runtime: GameRuntimeState,
    location_id: str | None,
) -> list[dict[str, Any]]:
    if location_id is None:
        return []
    out: list[dict[str, Any]] = []
    for item_id in items_at(runtime.graph_index, location_id):
        node = runtime.graph.nodes.get(item_id)
        if node is not None and node.type == "item":
            out.append(_item_payload(runtime, node))
    return out


def _active_quest(runtime: GameRuntimeState) -> dict[str, Any] | None:
    quest_id = runtime.progress.active_quest_id
    node = runtime.graph.nodes.get(quest_id or "")
    if node is None or node.type != "quest":
        return None
    payload: dict[str, Any] = {
        "id": node.id,
        "name": node_label(runtime.content, node),
    }
    choices = _quest_choices(node) if _ready_to_decide(node) else []
    if choices:
        payload["choices"] = choices
    return payload


def _available_quests(
    runtime: GameRuntimeState,
    visible_targets: list[dict[str, Any]],
    active_quest: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    if active_quest is not None:
        return []
    visible_by_id = {
        target["id"]: target
        for target in visible_targets
        if isinstance(target.get("id"), str)
        and isinstance(target.get("name"), str)
        and target.get("type") in {"npc", "enemy"}
    }
    out: list[dict[str, Any]] = []
    for node in runtime.graph.nodes.values():
        if node.type != "quest":
            continue
        status = node.properties.get("status")
        if status not in {"pending", "abandoned"}:
            continue
        giver_id = node.properties.get("giver")
        if not isinstance(giver_id, str) or giver_id not in visible_by_id:
            continue
        giver = visible_by_id[giver_id]
        out.append(
            {
                "id": node.id,
                "name": node_label(runtime.content, node),
                "status": status,
                "giver": giver_id,
                "giver_name": giver["name"],
            }
        )
    return out


def _quest_choices(node: GraphNode) -> list[dict[str, str]]:
    choices = node.properties.get("choices")
    if not isinstance(choices, dict):
        return []
    out: list[dict[str, str]] = []
    for choice_id, choice in choices.items():  # ssot-allow: quest choice attribute map
        if not isinstance(choice_id, str) or not choice_id:
            continue
        if not isinstance(choice, dict):
            continue
        label = choice.get("label")
        out.append(
            {
                "id": choice_id,
                "label": label if isinstance(label, str) and label else choice_id,
            }
        )
    return out


def _quest_ids(
    runtime: GameRuntimeState,
    available_quests: list[dict[str, Any]] | None = None,
) -> list[str]:
    ids = [runtime.progress.active_quest_id] if runtime.progress.active_quest_id else []
    ids.extend(
        quest["id"]
        for quest in (available_quests or [])
        if isinstance(quest.get("id"), str)
    )
    return ids


def _quest_choice_ids(runtime: GameRuntimeState) -> list[str]:
    quest_id = runtime.progress.active_quest_id
    node = runtime.graph.nodes.get(quest_id or "")
    if node is None or node.type != "quest":
        return []
    if not _ready_to_decide(node):
        return []
    return [choice["id"] for choice in _quest_choices(node)]


def _ready_to_decide(node: GraphNode) -> bool:
    triggers = node.properties.get("triggers", [])
    if not isinstance(triggers, list) or not triggers:
        return True
    met = node.properties.get("triggers_met", [])
    values = met if isinstance(met, list) else []
    return len(values) >= len(triggers) and all(
        item is True for item in values[: len(triggers)]
    )


def _attackable_ids(visible_targets: list[dict[str, Any]]) -> list[str]:
    return [
        target["id"]
        for target in visible_targets
        if target["type"] in {"npc", "enemy"} and target.get("protected") is not True
    ]


def _merchants(
    runtime: GameRuntimeState,
    visible_targets: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for target in visible_targets:
        node = runtime.graph.nodes.get(target["id"])
        if node is None or node.type != "character":
            continue
        if not isinstance(node.properties.get("gold"), int):
            continue
        stock = _inventory_for_owner(runtime, node.id)
        if not stock:
            continue
        out.append({"id": node.id, "name": target["name"], "stock": stock})
    return out


def _corpses(
    runtime: GameRuntimeState,
    location_id: str | None,
) -> list[dict[str, Any]]:
    if location_id is None:
        return []
    out: list[dict[str, Any]] = []
    for character_id in characters_at(runtime.graph_index, location_id):
        if character_id == runtime.progress.player_id:
            continue
        node = runtime.graph.nodes.get(character_id)
        if node is None or node.type != "character" or is_visible_character(node):
            continue
        inventory = _inventory_for_owner(runtime, node.id)
        if inventory:
            out.append(
                {
                    "id": node.id,
                    "name": node_label(runtime.content, node),
                    "inventory": inventory,
                }
            )
    return out


def _item_payload(runtime: GameRuntimeState, node: GraphNode) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "id": node.id,
        "name": node_label(runtime.content, node),
        "kind": _kind(runtime, node),
    }
    price = node.properties.get("price")
    if isinstance(price, int):
        payload["price"] = price
    return payload


def _last_entity_ref(
    runtime: GameRuntimeState,
    *,
    entity_types: set[str] | None = None,
) -> dict[str, str] | None:
    subject_id = runtime.progress.active_subject_id
    node = runtime.graph.nodes.get(subject_id or "")
    if node is None:
        return None
    if entity_types is not None and node.type not in entity_types:
        return None
    return _node_ref(runtime, node)


def _recent_exchanges(
    runtime: GameRuntimeState,
    limits: ClassifyContextLimits,
) -> list[dict[str, Any]]:
    """Recent raw player input + narrator reply pairs, not free-form NPC memory."""
    return [
        {"turn": pair.turn, "player": pair.player, "narrator": pair.narrator}
        for pair in runtime.recent_exchanges[-limits.recent_exchanges :]
    ]


def _recent_scene(
    runtime: GameRuntimeState,
    limits: ClassifyContextLimits,
) -> list[dict[str, Any]]:
    recent_exchange_turns = {
        pair.turn for pair in runtime.recent_exchanges[-limits.recent_exchanges :]
    }
    return [
        {
            "turn": entry.turn,
            "summary": entry.summary,
            **({"target": entry.target} if entry.target else {}),
        }
        for entry in [
            entry
            for entry in runtime.turn_log
            if entry.turn not in recent_exchange_turns
        ][-limits.recent_scene :]
        if entry.summary
    ]


def _node_ref(
    runtime: GameRuntimeState,
    node: GraphNode | None,
) -> dict[str, str] | None:
    if node is None:
        return None
    return {"id": node.id, "name": node_label(runtime.content, node)}


def _kind(runtime: GameRuntimeState, node: GraphNode) -> str:
    value = node_value(runtime.content, node, "kind") or node_value(
        runtime.content,
        node,
        "type",
    )
    return value if isinstance(value, str) and value else "item"


def _dicts(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [entry for entry in value if isinstance(entry, dict)]
