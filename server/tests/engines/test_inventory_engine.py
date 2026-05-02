"""Equipment / inventory / trade — equip/unequip + carry + buy/sell + bargain price."""

import pytest

from src.domain.entities import (
    ArmorEffect,
    Character,
    ConsumableEffect,
    Item,
    Stats,
    WeaponEffect,
)
from src.domain.errors import InventoryInvalid
from src.engines import inventory as inv
from src.rules import RULES


def _player(**kw):
    p = Character(
        id="player_01",
        name="주",
        race_id="human",
        is_player=True,
        stats=Stats(),
        gold=100,
    )
    for k, v in kw.items():
        setattr(p, k, v)
    return p


def _npc(**kw):
    n = Character(
        id="npc_01",
        name="상인",
        race_id="human",
        stats=Stats(),
        gold=200,
        relations={"player_01": 0},
    )
    for k, v in kw.items():
        setattr(n, k, v)
    return n


def _items() -> dict[str, Item]:
    return {
        "sword": Item(
            id="sword",
            name="검",
            weight=3.0,
            price=50,
            effects=WeaponEffect(type="weapon", weapon_dice="1d8"),
        ),
        "greatsword": Item(
            id="greatsword",
            name="대검",
            weight=6.0,
            price=80,
            effects=WeaponEffect(type="weapon", weapon_dice="2d6"),
        ),
        "helm": Item(
            id="helm",
            name="투구",
            weight=2.0,
            price=30,
            effects=ArmorEffect(type="armor", defense=2),
        ),
        "potion": Item(
            id="potion",
            name="포션",
            weight=0.5,
            price=20,
            effects=ConsumableEffect(type="consumable", effect="heal", amount=10),
        ),
        "ring": Item(id="ring", name="반지", weight=0.1, price=40),
        "heavy": Item(id="heavy", name="무거운 짐", weight=200.0, price=10),
        "strong_sword": Item(
            id="strong_sword",
            name="요구치 검",
            weight=2.0,
            price=100,
            effects=WeaponEffect(type="weapon", weapon_dice="1d10"),
            required=Stats(STR=15),
        ),
    }


# --- carry ----------------------------------------------------------------


def test_carry_capacity_str_based():
    p = _player()
    p.stats.STR = 10
    assert inv.carry_capacity(p) == 10.0 * RULES.carry.weight_per_strength


def test_check_can_carry_rejects_overweight():
    p = _player()
    items = _items()
    p.stats.STR = 10  # cap = 100
    p.inventory_ids = ["sword", "sword", "sword"]  # 9.0
    with pytest.raises(InventoryInvalid, match="capacity"):
        inv.check_can_carry(p, items, "heavy")


# --- equip ----------------------------------------------------------------


def test_equip_weapon_in_weapon_slot():
    p = _player(inventory_ids=["sword"])
    items = _items()
    inv.equip(p, "sword", "weapon", items)
    assert p.equipment.weapon == "sword"
    assert p.equipment.armor is None


def test_equip_weapon_in_armor_slot_rejected():
    p = _player(inventory_ids=["sword"])
    with pytest.raises(InventoryInvalid, match="weapon must"):
        inv.equip(p, "sword", "armor", _items())


def test_equip_armor_in_armor_slot():
    p = _player(inventory_ids=["helm"])
    inv.equip(p, "helm", "armor", _items())
    assert p.equipment.armor == "helm"


def test_equip_armor_in_accessory_slot_allowed():
    p = _player(inventory_ids=["helm"])
    inv.equip(p, "helm", "accessory", _items())
    assert p.equipment.accessory == "helm"


def test_equip_armor_in_weapon_slot_rejected():
    p = _player(inventory_ids=["helm"])
    with pytest.raises(InventoryInvalid, match="defense item"):
        inv.equip(p, "helm", "weapon", _items())


def test_equip_consumable_rejected():
    p = _player(inventory_ids=["potion"])
    with pytest.raises(InventoryInvalid, match="consumable"):
        inv.equip(p, "potion", "weapon", _items())


def test_equip_required_stats_check():
    p = _player(inventory_ids=["strong_sword"])
    p.stats.STR = 10  # below the required STR=15
    with pytest.raises(InventoryInvalid, match="required"):
        inv.equip(p, "strong_sword", "weapon", _items())


def test_equip_required_stats_passes_when_met():
    p = _player(inventory_ids=["strong_sword"], stats=Stats(STR=15))
    inv.equip(p, "strong_sword", "weapon", _items())
    assert p.equipment.weapon == "strong_sword"


def test_equip_unknown_item_rejected():
    p = _player(inventory_ids=[])
    with pytest.raises(InventoryInvalid, match="not in inventory"):
        inv.equip(p, "sword", "weapon", _items())


def test_equip_acc_slot_accepts_plain_item():
    p = _player(inventory_ids=["ring"])
    inv.equip(p, "ring", "accessory", _items())
    assert p.equipment.accessory == "ring"


def test_equip_plain_accessory_in_armor_slot_rejected():
    p = _player(inventory_ids=["ring"])
    with pytest.raises(InventoryInvalid, match="decorative"):
        inv.equip(p, "ring", "armor", _items())


# --- unequip --------------------------------------------------------------


def test_unequip_clears_slot():
    p = _player(inventory_ids=["sword"])
    items = _items()
    inv.equip(p, "sword", "weapon", items)
    inv.unequip(p, "weapon")
    assert p.equipment.weapon is None
    # still in inventory
    assert "sword" in p.inventory_ids


def test_unequip_idempotent_on_empty_slot():
    p = _player()
    inv.unequip(p, "armor")  # does not raise


# --- trade pricing --------------------------------------------------------


def test_buy_price_at_zero_affinity_is_base():
    items = _items()
    p = _player()
    n = _npc(relations={"player_01": 0})
    assert inv.buy_price(items["sword"], n, p) == 50


def test_buy_price_with_positive_affinity_discount():
    items = _items()
    p = _player()
    n = _npc(relations={"player_01": 30})  # discount = 0.3 (below the 0.5 cap)
    assert inv.buy_price(items["sword"], n, p) == round(50 * 0.7)


def test_buy_price_capped_at_max_discount():
    items = _items()
    p = _player()
    n = _npc(relations={"player_01": 100})  # discount = 1.0 → cap 0.5
    assert inv.buy_price(items["sword"], n, p) == round(50 * 0.5)


def test_buy_price_negative_affinity_premium():
    items = _items()
    p = _player()
    n = _npc(relations={"player_01": -50})  # premium = 0.5
    assert inv.buy_price(items["sword"], n, p) == round(50 * 1.5)


def test_sell_price_at_zero_affinity_uses_sell_ratio():
    items = _items()
    p = _player()
    n = _npc(relations={"player_01": 0})
    # base × sell_ratio (0.5) × (1+0)
    assert inv.sell_price(items["sword"], p, n) == round(50 * RULES.trade.sell_ratio)


def test_sell_price_with_positive_affinity_bonus():
    items = _items()
    p = _player()
    n = _npc(relations={"player_01": 30})
    assert inv.sell_price(items["sword"], p, n) == round(
        50 * RULES.trade.sell_ratio * 1.3
    )


# --- buy / sell flow ------------------------------------------------------


def test_buy_transfers_item_and_gold():
    items = _items()
    p = _player(gold=100)
    n = _npc(relations={"player_01": 0}, inventory_ids=["sword"])
    price = inv.buy(p, n, "sword", items)
    assert price == 50
    assert "sword" in p.inventory_ids
    assert "sword" not in n.inventory_ids
    assert p.gold == 50
    assert n.gold == 250


def test_buy_blocked_by_low_affinity():
    items = _items()
    p = _player()
    n = _npc(relations={"player_01": -1}, inventory_ids=["sword"])
    with pytest.raises(InventoryInvalid, match="affinity"):
        inv.buy(p, n, "sword", items)


def test_buy_blocked_by_insufficient_gold():
    items = _items()
    p = _player(gold=10)
    n = _npc(relations={"player_01": 0}, inventory_ids=["sword"])
    with pytest.raises(InventoryInvalid, match="gold"):
        inv.buy(p, n, "sword", items)


def test_buy_blocked_by_carry_capacity():
    items = _items()
    p = _player(gold=999, stats=Stats(STR=1))
    p.inventory_ids = ["heavy"]  # 200kg
    n = _npc(relations={"player_01": 0}, inventory_ids=["sword"])
    with pytest.raises(InventoryInvalid, match="capacity"):
        inv.buy(p, n, "sword", items)


def test_sell_transfers_item_and_gold():
    items = _items()
    p = _player(gold=10, inventory_ids=["sword"])
    n = _npc(relations={"player_01": 0})
    price = inv.sell(p, n, "sword", items)
    assert price == 25  # 50 × 0.5
    assert "sword" in n.inventory_ids
    assert "sword" not in p.inventory_ids
    assert p.gold == 35
    assert n.gold == 175


def test_sell_blocked_by_insufficient_npc_gold():
    items = _items()
    p = _player(inventory_ids=["sword"])
    n = _npc(relations={"player_01": 0}, gold=10)
    with pytest.raises(InventoryInvalid, match="npc has not enough gold"):
        inv.sell(p, n, "sword", items)


def test_sell_rejects_equipped_item():
    items = _items()
    p = _player(inventory_ids=["sword"])
    n = _npc(relations={"player_01": 0})
    inv.equip(p, "sword", "weapon", items)
    with pytest.raises(InventoryInvalid, match="equipped"):
        inv.sell(p, n, "sword", items)
