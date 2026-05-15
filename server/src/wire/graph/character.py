from src.game.domain.content import RuntimeContent
from src.game.domain.graph import Graph, GraphNode
from src.game.domain.graph.query import equipment_of, inventory_of, known_skills_of
from src.locale.labels import gender_label
from .values import (
    int_prop_default,
    node_name,
    optional_str,
    static_value,
)
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


def character_skills(
    graph: Graph,
    character_id: str,
    content: RuntimeContent | None = None,
) -> list[str]:
    skills: list[str] = []
    for edge in known_skills_of(graph, character_id):
        skill = graph.nodes.get(edge.to_node_id)
        if skill is not None and skill.type == "skill":
            skills.append(node_name(skill, content))
    return skills


def character_equipment(
    graph: Graph,
    character_id: str,
    content: RuntimeContent | None = None,
) -> GraphEquipmentPayload:
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
        slots[slot] = GraphNamedPayload(id=item.id, name=node_name(item, content))
    return GraphEquipmentPayload.model_validate(slots)


def character_inventory(
    graph: Graph,
    character_id: str,
    content: RuntimeContent | None = None,
) -> list[GraphInventoryItemPayload]:
    items: list[GraphInventoryItemPayload] = []
    for item_id in inventory_of(graph, character_id):
        item = graph.nodes.get(item_id)
        if item is None or item.type != "item":
            continue
        items.append(
            GraphInventoryItemPayload(
                id=item.id,
                name=node_name(item, content),
                qty=int_prop_default(item, "qty", 1),
                can_use=_can_use_item(item, content),
                equip_slots=_equip_slots(item, content),
            )
        )
    return items


def character_gender(
    node: GraphNode,
    locale: str = "ko",
    content: RuntimeContent | None = None,
) -> str:
    return gender_label(optional_str(static_value(node, "gender", content)), locale)


def character_race_job(
    node: GraphNode,
    content: RuntimeContent | None = None,
) -> str:
    return optional_str(static_value(node, "job", content)) or ""


def _can_use_item(
    item: GraphNode,
    content: RuntimeContent | None = None,
) -> bool:
    effects = static_value(item, "effects", content)
    if isinstance(effects, dict):
        return effects.get("type") == "consumable" and effects.get("effect") in {
            "heal",
            "mp_restore",
            "buff",
        }
    return optional_str(static_value(item, "on_use", content)) is not None


def _equip_slots(
    item: GraphNode,
    content: RuntimeContent | None = None,
) -> list[EquipSlot]:
    explicit = _explicit_equip_slots(item, content)
    if explicit:
        return explicit

    effects = static_value(item, "effects", content)
    if not isinstance(effects, dict):
        return []
    effect_type = effects.get("type")
    if effect_type == "weapon":
        return ["weapon"]
    if effect_type == "armor":
        return ["armor", "accessory"]
    return []


def _explicit_equip_slots(
    item: GraphNode,
    content: RuntimeContent | None = None,
) -> list[EquipSlot]:
    raw_slots = static_value(item, "equip_slots", content)
    if isinstance(raw_slots, list):
        slots = [_equip_slot(slot) for slot in raw_slots]
        return [slot for slot in slots if slot is not None]

    raw_slot = static_value(item, "equip_slot", content)
    slot = _equip_slot(raw_slot)
    return [slot] if slot is not None else []


def _equip_slot(value: object) -> EquipSlot | None:
    if value in ("weapon", "armor", "accessory"):
        return value
    return None
