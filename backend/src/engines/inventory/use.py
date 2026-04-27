"""Item activation — heal/damage/mp_restore/buff consumables and on_use
trigger pass-through. The quest-hook variant evaluates `item_use` and
`character_death` triggers after the effect lands."""
from ...domain.entities import ActiveBuff, Character, ConsumableEffect, Item
from ...domain.errors import InventoryInvalid


# --- per-effect handlers ---------------------------------------------------


def _heal(item_id, item, eff, target, recipient, result) -> None:
    if recipient.hp >= recipient.max_hp:
        raise InventoryInvalid(f"hp already full: cannot use heal item {item_id}")
    new_hp = min(recipient.max_hp, recipient.hp + eff.amount)
    result["kind"] = "heal"
    result["amount"] = new_hp - recipient.hp
    recipient.hp = new_hp


def _damage(item_id, item, eff, target, recipient, result) -> None:
    if target is None:
        raise InventoryInvalid(f"damage item requires target: {item_id}")
    recipient.hp = max(0, recipient.hp - eff.amount)
    if recipient.hp == 0:
        recipient.alive = False
    result["kind"] = "damage"
    result["amount"] = eff.amount
    if not recipient.alive:
        result["dead"] = True


def _mp_restore(item_id, item, eff, target, recipient, result) -> None:
    if recipient.mp >= recipient.max_mp:
        raise InventoryInvalid(f"mp already full: cannot use mp item {item_id}")
    new_mp = min(recipient.max_mp, recipient.mp + eff.amount)
    result["kind"] = "mp_restore"
    result["amount"] = new_mp - recipient.mp
    recipient.mp = new_mp


def _buff(item_id, item, eff, target, recipient, result) -> None:
    description = eff.description or item.name
    duration = eff.duration or 0
    recipient.active_buffs.append(ActiveBuff(description=description, duration=duration))
    result["kind"] = "buff"
    result["description"] = description
    result["duration"] = duration


_EFFECT_HANDLERS = {
    "heal": _heal,
    "damage": _damage,
    "mp_restore": _mp_restore,
    "buff": _buff,
}


# --- entry points ----------------------------------------------------------


def use(
    actor: Character,
    item_id: str,
    target: Character | None,
    items: dict[str, Item],
    *,
    dirty: set[tuple[str, str]] | None = None,
) -> dict:
    """Apply ConsumableEffect. target=None means actor self.

    consumable=True items are removed from inventory after one use.
    Weapon/armor items are not valid `use` targets — those go through equip.
    `on_use` (free text or trigger id) rides along on the result; quest
    evaluation happens in engines.quest.check_quests.
    """
    if item_id not in items:
        raise InventoryInvalid(f"unknown item: {item_id}")
    if item_id not in actor.inventory_ids:
        raise InventoryInvalid(f"item not in inventory: {item_id}")
    item = items[item_id]
    eff = item.effects
    if eff is not None and not isinstance(eff, ConsumableEffect):
        raise InventoryInvalid(f"item {item_id} is not consumable")

    recipient = target or actor
    result: dict = {"item_id": item_id, "actor": actor.id, "target": recipient.id}

    if eff is None:
        # Trigger-only item (e.g. ancient key) — no numeric effect.
        result["kind"] = "trigger"
    else:
        handler = _EFFECT_HANDLERS.get(eff.effect)
        if handler is None:
            raise InventoryInvalid(f"unsupported consumable effect: {eff.effect}")
        handler(item_id, item, eff, target, recipient, result)

    if item.on_use:
        result["on_use"] = item.on_use

    if item.consumable:
        actor.inventory_ids.remove(item_id)
        result["consumed"] = True

    if dirty is not None:
        dirty.add(("characters", actor.id))
        if recipient.id != actor.id:
            dirty.add(("characters", recipient.id))

    return result
