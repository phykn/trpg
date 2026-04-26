"""Equip / unequip (P3 §2.5). Slot validation, two-handed rules, and a small
auto-slot heuristic for the natural-language equip path."""
from typing import Literal

from ...domain.entities import (
    ARMOR_SLOTS,
    EQUIPMENT_SLOTS,
    HAND_SLOTS,
    ArmorEffect,
    Character,
    ConsumableEffect,
    Item,
    WeaponEffect,
    slot_kind,
)
from ...domain.errors import InventoryInvalid

Slot = Literal[
    "head", "top", "bottom", "feet", "leftHand", "rightHand", "acc1", "acc2"
]


def _required_stats_met(actor: Character, item: Item) -> bool:
    if item.required is None:
        return True
    for k in ("STR", "DEX", "CON", "INT", "WIS", "CHA"):
        if getattr(actor.stats, k) < getattr(item.required, k):
            return False
    return True


def _validate_slot_for_item(slot: Slot, item: Item) -> None:
    if slot not in EQUIPMENT_SLOTS:
        raise InventoryInvalid(f"unknown slot: {slot}")
    eff = item.effects
    kind = slot_kind(slot)
    if isinstance(eff, WeaponEffect):
        if kind != "hand":
            raise InventoryInvalid(f"weapon must go in leftHand or rightHand, got {slot}")
    elif isinstance(eff, ArmorEffect):
        if kind != "armor":
            raise InventoryInvalid(f"armor must go in head/top/bottom/feet, got {slot}")
    elif isinstance(eff, ConsumableEffect):
        raise InventoryInvalid("consumable items can't be equipped")
    elif kind == "acc":
        # Decorative items (effects=None) only fit in accessory slots.
        pass
    else:
        raise InventoryInvalid(f"item {item.id} has no equippable effect for slot {slot}")


def equip(actor: Character, item_id: str, slot: Slot, items: dict[str, Item]) -> None:
    """Place item_id into slot. Two-handed weapons claim both hand slots
    regardless of which hand is asked. Auto-unequips whatever was already
    there (the previous item stays in inventory)."""
    if item_id not in items:
        raise InventoryInvalid(f"unknown item: {item_id}")
    if item_id not in actor.inventory_ids:
        raise InventoryInvalid(f"item not in inventory: {item_id}")
    item = items[item_id]
    _validate_slot_for_item(slot, item)
    if not _required_stats_met(actor, item):
        raise InventoryInvalid(f"required stats not met for {item_id}")

    eff = item.effects
    two_handed = isinstance(eff, WeaponEffect) and eff.two_handed

    if two_handed:
        actor.equipment.leftHand = item_id
        actor.equipment.rightHand = item_id
        return

    # If the other hand holds a two-handed weapon, drop it first.
    if slot in HAND_SLOTS:
        other = "rightHand" if slot == "leftHand" else "leftHand"
        other_id = getattr(actor.equipment, other)
        if other_id and other_id in items:
            other_eff = items[other_id].effects
            if isinstance(other_eff, WeaponEffect) and other_eff.two_handed:
                setattr(actor.equipment, other, None)
    setattr(actor.equipment, slot, item_id)


def auto_equip_slot(actor: Character, item: Item) -> Slot:
    """Engine picks a slot when the judge omits one.

    weapon: prefer empty leftHand/rightHand, otherwise overwrite the dominant hand.
    armor: first empty head/top/bottom/feet (seed item decides which it really fits).
    accessory (effects=None): acc1 then acc2.
    """
    eff = item.effects
    if isinstance(eff, WeaponEffect):
        if actor.equipment.leftHand is None:
            return "leftHand"
        if actor.equipment.rightHand is None:
            return "rightHand"
        return "rightHand" if actor.dominant_hand == "right" else "leftHand"
    if isinstance(eff, ArmorEffect):
        for slot in ARMOR_SLOTS:
            if getattr(actor.equipment, slot) is None:
                return slot  # type: ignore[return-value]
        return "head"
    if eff is None:
        if actor.equipment.acc1 is None:
            return "acc1"
        return "acc2"
    raise InventoryInvalid(f"item {item.id} has no equippable effect")


def equip_auto(actor: Character, item_id: str, items: dict[str, Item]) -> Slot:
    if item_id not in items:
        raise InventoryInvalid(f"unknown item: {item_id}")
    slot = auto_equip_slot(actor, items[item_id])
    equip(actor, item_id, slot, items)
    return slot


def unequip(actor: Character, slot: Slot, items: dict[str, Item]) -> None:
    """Empty a slot. Two-handed weapons clear both hand slots."""
    if slot not in EQUIPMENT_SLOTS:
        raise InventoryInvalid(f"unknown slot: {slot}")
    item_id = getattr(actor.equipment, slot)
    if item_id is None:
        return  # idempotent
    item = items.get(item_id)
    if item is not None:
        eff = item.effects
        if isinstance(eff, WeaponEffect) and eff.two_handed:
            actor.equipment.leftHand = None
            actor.equipment.rightHand = None
            return
    setattr(actor.equipment, slot, None)


def unequip_by_item(
    actor: Character, item_id: str, items: dict[str, Item]
) -> Slot | None:
    """Find which slot holds item_id and unequip it. None if nowhere."""
    for slot, eq_id in actor.equipment.equipped_items():
        if eq_id == item_id:
            unequip(actor, slot, items)  # type: ignore[arg-type]
            return slot  # type: ignore[return-value]
    return None
