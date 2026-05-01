"""Buy / sell with affinity-based pricing (P3 §2.5)."""

from ...domain.entities import Character, Item
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


def buy(player: Character, npc: Character, item_id: str, items: dict[str, Item]) -> int:
    """Player buys item from NPC. Transfers gold + inventory, returns price."""
    _check_trade_allowed(npc, player)
    if item_id not in items:
        raise InventoryInvalid(f"unknown item: {item_id}")
    if item_id not in npc.inventory_ids:
        raise InventoryInvalid(f"npc has no such item: {item_id}")
    price = buy_price(items[item_id], npc, player)
    if player.gold < price:
        raise InventoryInvalid(f"not enough gold: {player.gold} < {price}")
    check_can_carry(player, items, item_id)

    npc.inventory_ids.remove(item_id)
    player.inventory_ids.append(item_id)
    player.gold -= price
    npc.gold += price
    return price


def sell(
    player: Character, npc: Character, item_id: str, items: dict[str, Item]
) -> int:
    """Player sells item to NPC. Equipped items must be removed first."""
    _check_trade_allowed(npc, player)
    if item_id not in items:
        raise InventoryInvalid(f"unknown item: {item_id}")
    if item_id not in player.inventory_ids:
        raise InventoryInvalid(f"player has no such item: {item_id}")
    for _, eq_id in player.equipment.equipped_items():
        if eq_id == item_id:
            raise InventoryInvalid(f"can't sell equipped item: {item_id}")
    price = sell_price(items[item_id], player, npc)
    if npc.gold < price:
        raise InventoryInvalid(f"npc has not enough gold: {npc.gold} < {price}")

    player.inventory_ids.remove(item_id)
    npc.inventory_ids.append(item_id)
    player.gold += price
    npc.gold -= price
    return price
