"""Item and inventory invariant checks."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, get_args

if TYPE_CHECKING:
    from ...domain.state import GameState

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
from .base import _v, _slot_mismatch_hint


_STAT_KEYS: tuple[str, ...] = get_args(StatKey)
_DICE_RE = re.compile(r"^\s*\d+d\d+\s*([+-]\s*\d+)?\s*$")


def _carry_capacity(c: Character) -> float:
    return RULES.carry.weight_per_strength * c.stats.STR


def _current_weight(c: Character, items: dict[str, Item]) -> float:
    return sum(items[i].weight for i in c.inventory_ids if i in items)


def check_item(item: Item) -> list[str]:
    where = f"items/{item.id}"
    out: list[str] = []
    if item.weight < 0:
        _v(out, where, f"weight={item.weight} (must be ≥ 0)")
    if item.price < 0:
        _v(out, where, f"price={item.price} (must be ≥ 0)")
    eff = item.effects
    if isinstance(eff, WeaponEffect):
        if not _DICE_RE.match(eff.weapon_dice):
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

    cap = _carry_capacity(c)
    total = _current_weight(c, items)
    if total > cap:
        _v(
            out,
            where,
            f"inventory weight {total:.1f} > carry capacity {cap:.1f} (STR×{RULES.carry.weight_per_strength})",
        )

    return out


# ----- Runtime item-locality guard (defense against LLM-emitted state_change errors) -----


# (sort_key, kind, container_id, slot_or_none)
Occurrence = tuple[str, str, str, str | None]


def _collect_item_occurrences(state: "GameState") -> dict[str, list[Occurrence]]:
    """Walk every character's inventory + equipment and every location's
    item_ids, returning a per-item-id map of where the item shows up. An
    item equipped by its own carrier is NOT a separate occurrence — already
    counted via the inventory walk."""
    from ...domain.entities import EQUIPMENT_SLOTS

    occurrences: dict[str, list[Occurrence]] = {}
    for char_id in sorted(state.characters):
        char = state.characters[char_id]
        for item_id in char.inventory_ids:
            occurrences.setdefault(item_id, []).append(
                (char_id, "char_inventory", char_id, None)
            )
        for slot in EQUIPMENT_SLOTS:
            eq_id = getattr(char.equipment, slot)
            if eq_id is None or eq_id in char.inventory_ids:
                continue
            occurrences.setdefault(eq_id, []).append(
                (char_id, "char_equipment", char_id, slot)
            )

    for loc_id in sorted(state.locations):
        loc = state.locations[loc_id]
        for item_id in loc.item_ids:
            occurrences.setdefault(item_id, []).append(
                (loc_id, "location_items", loc_id, None)
            )
    return occurrences


def _occurrence_label(o: Occurrence) -> str:
    _, kind, container_id, slot = o
    if kind == "char_inventory":
        return f"characters/{container_id}/inventory"
    if kind == "char_equipment":
        return f"characters/{container_id}/equipment.{slot}"
    return f"locations/{container_id}/items"


def check_item_locality(state: "GameState") -> list[str]:
    """Detect items appearing in 2+ locations (inventory, equipment, location items).
    Returns one violation line per duplicated item."""
    violations: list[str] = []
    for item_id, places in _collect_item_occurrences(state).items():
        if len(places) <= 1:
            continue
        item = state.items.get(item_id)
        name = item.name if item is not None else item_id
        place_labels = ", ".join(_occurrence_label(p) for p in sorted(places))
        violations.append(
            f"item {item_id!r} ({name!r}) duplicated across: {place_labels}"
        )
    return violations


def enforce_item_locality(
    state: "GameState",
    *,
    dirty: set[tuple[str, str]] | None = None,
) -> list[str]:
    """Detect duplicated items and auto-repair by keeping the alphabetically-first
    location and clearing the rest. Returns one warning string per duplication
    detected (and corrected)."""
    # Keeper precedence: any character holding (inventory or equipment) beats a location.
    # Without this, the previous alphabetical-container-id sort could pick `locations/aaa`
    # over `characters/zzz`, deleting an item out of the player's inventory after a loot.
    # Character-vs-character conflicts still fall back to alphabetical container id.
    kind_priority = {"char_equipment": 0, "char_inventory": 0, "location_items": 1}

    warnings: list[str] = []
    for item_id, places in _collect_item_occurrences(state).items():
        if len(places) <= 1:
            continue
        places_sorted = sorted(
            places, key=lambda p: (kind_priority[p[1]], p[0], p[3] or "")
        )
        keeper = places_sorted[0]
        losers = places_sorted[1:]

        item = state.items.get(item_id)
        name = item.name if item is not None else item_id
        kept_label = _occurrence_label(keeper)
        lost_labels = ", ".join(_occurrence_label(p) for p in losers)
        warnings.append(
            f"item {item_id!r} ({name!r}) was duplicated; kept {kept_label}, cleared {lost_labels}"
        )

        for loser in losers:
            _, kind, container_id, slot = loser
            if kind == "char_inventory":
                state.characters[container_id].inventory_ids.remove(item_id)
                if dirty is not None:
                    dirty.add(("characters", container_id))
            elif kind == "char_equipment":
                assert slot is not None
                setattr(state.characters[container_id].equipment, slot, None)
                if dirty is not None:
                    dirty.add(("characters", container_id))
            elif kind == "location_items":
                state.locations[container_id].item_ids.remove(item_id)
                if dirty is not None:
                    dirty.add(("locations", container_id))

    return warnings
