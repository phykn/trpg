from __future__ import annotations

from typing import Any

from .coerce import str_list
from .types import SeedRecords

SUPPORT_ACTIONS = {"attack", "defend", "flee", "talk"}
EFFECT_TEMPLATES = {
    "heal",
    "mp_restore",
    "dc_down",
    "dc_up",
}


def check_action(
    kind: str,
    record_id: str,
    field: str,
    value: object,
    out: list[str],
) -> None:
    if value is None:
        return
    if value not in SUPPORT_ACTIONS:
        out.append(f"{kind} {record_id} {field}={value!r} unknown")


def check_effect(
    kind: str,
    record_id: str,
    value: object,
    effects: SeedRecords | None,
    out: list[str],
) -> None:
    if value is None:
        return
    if effects:
        if value not in effects:
            out.append(
                f"{kind} {record_id} effect={value!r} "
                "not found in effects"
            )
        return
    if value not in EFFECT_TEMPLATES:
        out.append(f"{kind} {record_id} effect={value!r} unknown")


def check_item_effect_fields(
    item_id: str,
    item: dict[str, Any],
    effects: SeedRecords | None,
    out: list[str],
) -> None:
    effect_id = item.get("effect")
    if not isinstance(effect_id, str) or not effects:
        return
    effect = effects.get(effect_id)
    if not isinstance(effect, dict):
        return
    effect_kind = effect.get("kind")
    if effect_kind in {"heal", "mp_restore"} and not isinstance(item.get("amount"), int):
        out.append(f"item {item_id} amount is required for effect={effect_id!r}")


def check_knowledge_references(
    kind: str,
    record_id: str,
    value: object,
    knowledge: SeedRecords | None,
    out: list[str],
) -> None:
    if value is None:
        return
    for knowledge_id in str_list(value):
        if not knowledge or knowledge_id not in knowledge:
            out.append(
                f"{kind} {record_id} knowledge_id={knowledge_id!r} not found"
            )


def check_trigger_target(
    quest_id: str,
    trigger: dict[str, Any],
    locations: SeedRecords,
    items: SeedRecords,
    npcs: SeedRecords,
    out: list[str],
) -> None:
    target_type = trigger.get("type")
    target = trigger.get("target")
    pools = {
        "location_enter": locations,
        "item_use": items,
        "item_obtained": items,
        "character_death": npcs,
        "character_defeat": npcs,
        "social_check": npcs,
    }
    pool = pools.get(target_type)
    if pool is None:
        out.append(f"quest {quest_id} trigger type={target_type!r} unknown")
        return
    if target not in pool:
        out.append(f"quest {quest_id} trigger target={target!r} not found")
