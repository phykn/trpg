"""Equip / unequip (P3 §2.5). Slot validation and a small auto-slot
heuristic for the natural-language equip path."""
from typing import get_args

from ...domain.entities import (
    ArmorEffect,
    Character,
    EquipSlot,
    Item,
    allowed_slots,
)
from ...domain.errors import InventoryInvalid
from ...domain.types import StatKey

Slot = EquipSlot


def _required_stats_met(actor: Character, item: Item) -> bool:
    if item.required is None:
        return True
    for k in get_args(StatKey):
        if getattr(actor.stats, k) < getattr(item.required, k):
            return False
    return True


def _validate_slot_for_item(slot: Slot, item: Item) -> None:
    allowed = allowed_slots(item)
    if not allowed:
        raise InventoryInvalid("consumable items can't be equipped")
    if slot not in allowed:
        if allowed == ("weapon",):
            raise InventoryInvalid(f"weapon must go in the weapon slot, got {slot}")
        if "armor" in allowed and "accessory" in allowed:
            raise InventoryInvalid(f"defense item must go in armor or accessory slot, got {slot}")
        raise InventoryInvalid(f"decorative item must go in the accessory slot, got {slot}")


def equip(actor: Character, item_id: str, slot: Slot, items: dict[str, Item]) -> None:
    """Place item_id into slot. Auto-unequips whatever was there (the
    previous item stays in inventory)."""
    if item_id not in items:
        raise InventoryInvalid(f"unknown item: {item_id}")
    if item_id not in actor.inventory_ids:
        raise InventoryInvalid(f"item not in inventory: {item_id}")
    item = items[item_id]
    _validate_slot_for_item(slot, item)
    if not _required_stats_met(actor, item):
        raise InventoryInvalid(f"required stats not met for {item_id}")
    setattr(actor.equipment, slot, item_id)


def auto_equip_slot(actor: Character, item: Item) -> Slot:
    """Engine picks a slot when the judge omits one.

    weapon: weapon slot.
    armor (ArmorEffect): armor slot first, accessory if armor is full —
        a shield with no other armor on still gets the defense in.
    decorative (effects=None): accessory slot.
    """
    allowed = allowed_slots(item)
    if not allowed:
        raise InventoryInvalid(f"item {item.id} has no equippable effect")
    if allowed == ("weapon",):
        return "weapon"
    if isinstance(item.effects, ArmorEffect):
        if actor.equipment.armor is None:
            return "armor"
        return "accessory"
    return "accessory"


def unequip(actor: Character, slot: Slot) -> None:
    """Empty a slot. Idempotent."""
    setattr(actor.equipment, slot, None)


def unequip_by_item(actor: Character, item_id: str) -> Slot | None:
    """Find which slot holds item_id and unequip it. None if nowhere."""
    for slot, eq_id in actor.equipment.equipped_items():
        if eq_id == item_id:
            unequip(actor, slot)  # type: ignore[arg-type]
            return slot  # type: ignore[return-value]
    return None
