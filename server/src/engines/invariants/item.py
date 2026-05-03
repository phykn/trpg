"""Item and inventory invariant checks."""

from __future__ import annotations

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


# ----- Runtime item-locality guard (defense against LLM-emitted state_change errors) -----


def check_item_locality(state: "GameState") -> list[str]:
    """Detect items appearing in 2+ locations (inventory, equipment, location items).

    An item equipped by its own owner counts as ONE location (inventory + own equipment is normal).
    Returns a list of one-line violation messages, one per duplicated item.
    """
    from ...domain.entities import EQUIPMENT_SLOTS

    # Map item_id → list of (sort_key, location_label) pairs.
    locations: dict[str, list[tuple[str, str]]] = {}

    def _add(item_id: str, sort_key: str, label: str) -> None:
        locations.setdefault(item_id, []).append((sort_key, label))

    for char_id in sorted(state.characters):
        char = state.characters[char_id]
        equipped: set[str] = set()
        for slot in EQUIPMENT_SLOTS:
            eq_id = getattr(char.equipment, slot)
            if eq_id is not None:
                equipped.add(eq_id)
        for item_id in char.inventory_ids:
            label = f"characters/{char_id}/inventory"
            _add(item_id, char_id, label)
        for slot in EQUIPMENT_SLOTS:
            eq_id = getattr(char.equipment, slot)
            if eq_id is None:
                continue
            # Equipment by own owner is not a separate location — already counted via inventory above.
            if eq_id in char.inventory_ids:
                continue
            label = f"characters/{char_id}/equipment.{slot}"
            _add(eq_id, char_id, label)

    for loc_id in sorted(state.locations):
        loc = state.locations[loc_id]
        for item_id in loc.item_ids:
            label = f"locations/{loc_id}/items"
            _add(item_id, loc_id, label)

    violations: list[str] = []
    for item_id, places in locations.items():
        if len(places) <= 1:
            continue
        item = state.items.get(item_id)
        name = item.name if item is not None else item_id
        place_labels = ", ".join(p[1] for p in sorted(places))
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
    detected (and corrected).
    """
    from ...domain.entities import EQUIPMENT_SLOTS

    # Tuple shape: (sort_key, kind, container_id, slot_or_none)
    Occurrence = tuple[str, str, str, str | None]
    locations: dict[str, list[Occurrence]] = {}

    for char_id in sorted(state.characters):
        char = state.characters[char_id]
        for item_id in char.inventory_ids:
            locations.setdefault(item_id, []).append(
                (char_id, "char_inventory", char_id, None)
            )
        for slot in EQUIPMENT_SLOTS:
            eq_id = getattr(char.equipment, slot)
            if eq_id is None:
                continue
            if eq_id in char.inventory_ids:
                continue
            locations.setdefault(eq_id, []).append(
                (char_id, "char_equipment", char_id, slot)
            )

    for loc_id in sorted(state.locations):
        loc = state.locations[loc_id]
        for item_id in loc.item_ids:
            locations.setdefault(item_id, []).append(
                (loc_id, "location_items", loc_id, None)
            )

    # Keeper precedence: any character holding (inventory or equipment) beats a location.
    # Without this, the previous alphabetical-container-id sort could pick `locations/aaa`
    # over `characters/zzz`, deleting an item out of the player's inventory after a loot.
    # Character-vs-character conflicts still fall back to alphabetical container id.
    kind_priority = {"char_equipment": 0, "char_inventory": 0, "location_items": 1}

    warnings: list[str] = []
    for item_id, places in locations.items():
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


def _occurrence_label(o: tuple[str, str, str, str | None]) -> str:
    _, kind, container_id, slot = o
    if kind == "char_inventory":
        return f"characters/{container_id}/inventory"
    if kind == "char_equipment":
        return f"characters/{container_id}/equipment.{slot}"
    return f"locations/{container_id}/items"
