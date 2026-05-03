"""Item and inventory invariant checks."""

from __future__ import annotations

from typing import get_args

from ...domain.entities import (
    Character,
    Item,
    WeaponEffect,
    ArmorEffect,
    ConsumableEffect,
    allowed_slots,
)
from ...domain.types import StatKey
from ...rules import RULES
from ..combat import DICE_RE
from ..inventory.carry import carry_capacity, current_weight
from .base import _v, _slot_mismatch_hint


_STAT_KEYS: tuple[str, ...] = get_args(StatKey)


def check_item(item: Item) -> list[str]:
    where = f"items/{item.id}"
    out: list[str] = []
    if item.weight < 0:
        _v(out, where, f"weight={item.weight} (must be ≥ 0)")
    if item.price < 0:
        _v(out, where, f"price={item.price} (must be ≥ 0)")
    eff = item.effects
    if isinstance(eff, WeaponEffect):
        if not DICE_RE.match(eff.weapon_dice):
            _v(
                out,
                where,
                f"effects.weapon_dice={eff.weapon_dice!r} (must match '<int>d<int>(+/-<int>)?')",
            )
    elif isinstance(eff, ArmorEffect):
        if eff.defense < 0:
            _v(out, where, f"effects.defense={eff.defense} (must be ≥ 0)")
    elif isinstance(eff, ConsumableEffect):
        if eff.amount < 0:
            _v(out, where, f"effects.amount={eff.amount} (must be ≥ 0)")
        if eff.duration is not None and eff.duration < 0:
            _v(
                out,
                where,
                f"effects.duration={eff.duration} (must be ≥ 0 or null)",
            )
    return out


def check_inventory(c: Character, items: dict[str, Item]) -> list[str]:
    where = f"characters/{c.id}"
    out: list[str] = []

    for iid in c.inventory_ids:
        if iid not in items:
            _v(out, where, f"inventory_ids: {iid!r} not in items pool")

    for slot, item_id in c.equipment.equipped_items():
        if item_id not in items:
            _v(out, where, f"equipment.{slot}={item_id!r} not in items pool")
            continue
        item = items[item_id]
        allowed = allowed_slots(item)
        if slot not in allowed:
            _v(
                out,
                where,
                f"equipment.{slot}={item_id!r} is {_slot_mismatch_hint(allowed)}",
            )

        req = item.required
        if req is not None:
            for k in _STAT_KEYS:
                need = getattr(req, k)
                have = getattr(c.stats, k)
                if have < need:
                    _v(
                        out,
                        where,
                        f"equipment.{slot}={item_id!r} requires {k}≥{need}, character has {k}={have}",
                    )

    cap = carry_capacity(c)
    total = current_weight(c, items)
    if total > cap:
        _v(
            out,
            where,
            f"inventory weight {total:.1f} > carry capacity {cap:.1f} (STR×{RULES.carry.weight_per_strength})",
        )

    return out
