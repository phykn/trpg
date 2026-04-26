"""Item activation — heal/damage/mp_restore/buff consumables and on_use
trigger pass-through. The quest-hook variant evaluates `item_use` and
`character_death` triggers after the effect lands."""
from ...domain.entities import ActiveBuff, Character, ConsumableEffect, Item
from ...domain.errors import InventoryInvalid


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
    elif eff.effect == "heal":
        new_hp = min(recipient.max_hp, recipient.hp + eff.amount)
        result["kind"] = "heal"
        result["amount"] = new_hp - recipient.hp
        recipient.hp = new_hp
    elif eff.effect == "damage":
        if target is None:
            raise InventoryInvalid(f"damage item requires target: {item_id}")
        recipient.hp = max(0, recipient.hp - eff.amount)
        if recipient.hp == 0:
            recipient.alive = False
        result["kind"] = "damage"
        result["amount"] = eff.amount
        if not recipient.alive:
            result["dead"] = True
    elif eff.effect == "mp_restore":
        new_mp = min(recipient.max_mp, recipient.mp + eff.amount)
        result["kind"] = "mp_restore"
        result["amount"] = new_mp - recipient.mp
        recipient.mp = new_mp
    elif eff.effect == "buff":
        description = eff.description or item.name
        duration = eff.duration or 0
        recipient.active_buffs.append(
            ActiveBuff(description=description, duration=duration)
        )
        result["kind"] = "buff"
        result["description"] = description
        result["duration"] = duration
    else:
        raise InventoryInvalid(f"unsupported consumable effect: {eff.effect}")

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


def use_with_quest_hook(
    actor: Character,
    item_id: str,
    target: Character | None,
    items: dict[str, Item],
    state,
    *,
    dirty: set[tuple[str, str]] | None = None,
) -> dict:
    """use + quest item_use trigger evaluation, plus character_death if the
    item killed someone."""
    from ..quest import check_quests

    result = use(actor, item_id, target, items, dirty=dirty)
    if result.get("dead"):
        check_quests(state, "character_death", result["target"], dirty)
    check_quests(state, "item_use", item_id, dirty)
    return result
