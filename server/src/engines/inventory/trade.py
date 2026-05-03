"""Buy / sell with affinity-based pricing + free transfer (gift / loot)."""

from ...domain.entities import Character, EQUIPMENT_SLOTS, Item
from ...domain.errors import InventoryInvalid
from ...rules import RULES
from .carry import check_can_carry


def _affinity_modifier(npc: Character, player: Character) -> float:
    """Price modifier in [-cap, +cap]. Always reads NPC's relation toward
    the player, both for buy and sell — keeps haggling symmetric."""
    aff = npc.relations.get(player.id, 0)
    raw = RULES.trade.affinity_price_per_point * aff
    cap = RULES.trade.affinity_price_cap
    return max(-cap, min(cap, raw))


def buy_price(item: Item, npc: Character, player: Character) -> int:
    """NPC selling to player. Friendlier NPC → cheaper."""
    return max(0, round(item.price * (1 - _affinity_modifier(npc, player))))


def sell_price(item: Item, player: Character, npc: Character) -> int:
    """Player selling to NPC. base × sell_ratio, friendlier NPC pays more."""
    base = item.price * RULES.trade.sell_ratio
    return max(0, round(base * (1 + _affinity_modifier(npc, player))))


def _check_trade_allowed(npc: Character, player: Character) -> None:
    aff = npc.relations.get(player.id, 0)
    if aff < RULES.social.trade_threshold:
        raise InventoryInvalid(
            f"affinity too low to trade: {aff} < {RULES.social.trade_threshold}"
        )


def buy(
    player: Character,
    npc: Character,
    item_id: str,
    items: dict[str, Item],
    *,
    price_override: int | None = None,
) -> int:
    """Player buys item from NPC. Transfers gold + inventory, returns price.
    `price_override` (when set) substitutes the engine formula — used for
    judge-classified player-stated prices (e.g. '단검을 2골드에 산다')."""
    _check_trade_allowed(npc, player)
    if item_id not in items:
        raise InventoryInvalid(f"unknown item: {item_id}")
    if item_id not in npc.inventory_ids:
        raise InventoryInvalid(f"npc has no such item: {item_id}")
    price = (
        price_override
        if price_override is not None
        else buy_price(items[item_id], npc, player)
    )
    if price < 0:
        raise InventoryInvalid(f"negative price not allowed: {price}")
    if player.gold < price:
        raise InventoryInvalid(f"not enough gold: {player.gold} < {price}")
    check_can_carry(player, items, item_id)

    npc.inventory_ids.remove(item_id)
    player.inventory_ids.append(item_id)
    player.gold -= price
    npc.gold += price
    return price


def sell(
    player: Character,
    npc: Character,
    item_id: str,
    items: dict[str, Item],
    *,
    price_override: int | None = None,
) -> int:
    """Player sells item to NPC. Equipped items must be removed first.
    `price_override` substitutes the engine formula when judge captured a
    player-stated price."""
    _check_trade_allowed(npc, player)
    if item_id not in items:
        raise InventoryInvalid(f"unknown item: {item_id}")
    if item_id not in player.inventory_ids:
        raise InventoryInvalid(f"player has no such item: {item_id}")
    for _, eq_id in player.equipment.equipped_items():
        if eq_id == item_id:
            raise InventoryInvalid(f"can't sell equipped item: {item_id}")
    price = (
        price_override
        if price_override is not None
        else sell_price(items[item_id], player, npc)
    )
    if price < 0:
        raise InventoryInvalid(f"negative price not allowed: {price}")
    if npc.gold < price:
        raise InventoryInvalid(f"npc has not enough gold: {npc.gold} < {price}")

    player.inventory_ids.remove(item_id)
    npc.inventory_ids.append(item_id)
    player.gold += price
    npc.gold -= price
    return price


def transfer(
    src: Character, dst: Character, item_id: str, items: dict[str, Item]
) -> None:
    """Free item transfer (gift / lend / corpse loot). Live src→player path checks affinity. Auto-unequips if src had it equipped."""
    if item_id not in items:
        raise InventoryInvalid(f"unknown item: {item_id}")
    if not dst.alive:
        raise InventoryInvalid(f"can't transfer to a dead recipient: {dst.id}")
    if item_id not in src.inventory_ids:
        raise InventoryInvalid(f"{src.id} has no such item: {item_id}")
    if src.alive and not src.is_player and dst.is_player:
        aff = src.relations.get(dst.id, 0)
        if aff < RULES.social.trade_threshold:
            raise InventoryInvalid(
                f"affinity too low to gift: {aff} < {RULES.social.trade_threshold}"
            )
    check_can_carry(dst, items, item_id)

    src.inventory_ids.remove(item_id)
    dst.inventory_ids.append(item_id)
    for slot in EQUIPMENT_SLOTS:
        if getattr(src.equipment, slot) == item_id:
            setattr(src.equipment, slot, None)
