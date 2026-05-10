from __future__ import annotations

from src.game.domain.graph import Graph, GraphNode
from src.game.domain.graph_query import equipment_of, inventory_of, known_skills_of
from src.locale.labels import gender_label
from src.wire.graph_payload_helpers import int_prop_default, node_name, optional_str
from src.wire.models import (
    EquipSlot,
    GraphEquipmentPayload,
    GraphInventoryItemPayload,
    GraphNamedPayload,
)


def character_stats(node: GraphNode) -> dict[str, int]:
    raw = node.properties.get("stats", {})
    if not isinstance(raw, dict):
        return {}
    return {
        key: value
        for key, value in sorted(raw.items())
        if isinstance(key, str) and isinstance(value, int)
    }


def character_status(node: GraphNode) -> list[str]:
    raw = node.properties.get("status", [])
    if not isinstance(raw, list):
        return []
    return [item for item in raw if isinstance(item, str)]


def character_skills(graph: Graph, character_id: str) -> list[str]:
    skills: list[str] = []
    for edge in known_skills_of(graph, character_id):
        skill = graph.nodes.get(edge.to_node_id)
        if skill is not None and skill.type == "skill":
            skills.append(node_name(skill))
    return skills


def character_equipment(graph: Graph, character_id: str) -> GraphEquipmentPayload:
    slots: dict[str, GraphNamedPayload | None] = {
        "weapon": None,
        "armor": None,
        "accessory": None,
    }
    for edge in equipment_of(graph, character_id):
        slot = edge.properties.get("slot")
        if slot not in slots:
            continue
        item = graph.nodes.get(edge.to_node_id)
        if item is None or item.type != "item":
            continue
        slots[slot] = GraphNamedPayload(id=item.id, name=node_name(item))
    return GraphEquipmentPayload.model_validate(slots)


def character_inventory(graph: Graph, character_id: str) -> list[GraphInventoryItemPayload]:
    items: list[GraphInventoryItemPayload] = []
    for item_id in inventory_of(graph, character_id):
        item = graph.nodes.get(item_id)
        if item is None or item.type != "item":
            continue
        items.append(
            GraphInventoryItemPayload(
                id=item.id,
                name=node_name(item),
                qty=int_prop_default(item, "qty", 1),
                can_use=_can_use_item(item),
                equip_slots=_equip_slots(item),
            )
        )
    return items


def character_gender(node: GraphNode, locale: str = "ko") -> str:
    return gender_label(optional_str(node.properties.get("gender")), locale)


def character_race_job(node: GraphNode) -> str:
    return optional_str(node.properties.get("job")) or ""


def _can_use_item(item: GraphNode) -> bool:
    effects = item.properties.get("effects")
    if isinstance(effects, dict):
        return effects.get("type") == "consumable" and effects.get("effect") in {
            "heal",
            "mp_restore",
            "buff",
        }
    return optional_str(item.properties.get("on_use")) is not None


def _equip_slots(item: GraphNode) -> list[EquipSlot]:
    explicit = _explicit_equip_slots(item)
    if explicit:
        return explicit

    effects = item.properties.get("effects")
    if not isinstance(effects, dict):
        return []
    effect_type = effects.get("type")
    if effect_type == "weapon":
        return ["weapon"]
    if effect_type == "armor":
        return ["armor", "accessory"]
    return []


def _explicit_equip_slots(item: GraphNode) -> list[EquipSlot]:
    raw_slots = item.properties.get("equip_slots")
    if isinstance(raw_slots, list):
        slots = [_equip_slot(slot) for slot in raw_slots]
        return [slot for slot in slots if slot is not None]

    raw_slot = item.properties.get("equip_slot")
    slot = _equip_slot(raw_slot)
    return [slot] if slot is not None else []


def _equip_slot(value: object) -> EquipSlot | None:
    if value in ("weapon", "armor", "accessory"):
        return value
    return None
