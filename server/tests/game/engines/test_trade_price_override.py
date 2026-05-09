"""price_override path on inventory.buy/sell — judge-extracted agreed_price."""

import pytest

from src.game.domain.entities import Character, Item, Stats, WeaponEffect
from src.game.domain.errors import InventoryInvalid
from src.game.engines import inventory as inv


def _player(**kw) -> Character:
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


def _npc(**kw) -> Character:
    n = Character(
        id="npc_01",
        name="상인",
        race_id="human",
        stats=Stats(),
        gold=25,
        relations={"player_01": 0},
    )
    for k, v in kw.items():
        setattr(n, k, v)
    return n


def _items() -> dict[str, Item]:
    return {
        "dagger": Item(
            id="dagger",
            name="단검",
            weight=1.0,
            price=50,
            effects=WeaponEffect(type="weapon", weapon_dice="1d4"),
        ),
        "sword": Item(
            id="sword",
            name="검",
            weight=3.0,
            price=100,
            effects=WeaponEffect(type="weapon", weapon_dice="1d8"),
        ),
    }


def test_buy_uses_price_override():
    items = _items()
    p = _player(gold=50)
    n = _npc(inventory_ids=["dagger"])
    paid = inv.buy(p, n, "dagger", items, price_override=2)
    assert paid == 2
    assert p.gold == 48
    assert n.gold == 27
    assert "dagger" in p.inventory_ids
    assert "dagger" not in n.inventory_ids


def test_sell_uses_price_override():
    items = _items()
    p = _player(gold=10, inventory_ids=["sword"])
    n = _npc(gold=25)
    paid = inv.sell(p, n, "sword", items, price_override=2)
    assert paid == 2
    assert p.gold == 12
    assert n.gold == 23
    assert "sword" in n.inventory_ids
    assert "sword" not in p.inventory_ids


def test_buy_negative_price_rejected():
    items = _items()
    p = _player()
    n = _npc(inventory_ids=["dagger"])
    with pytest.raises(InventoryInvalid, match="negative price"):
        inv.buy(p, n, "dagger", items, price_override=-1)


def test_sell_negative_price_rejected():
    items = _items()
    p = _player(inventory_ids=["sword"])
    n = _npc()
    with pytest.raises(InventoryInvalid, match="negative price"):
        inv.sell(p, n, "sword", items, price_override=-1)


def test_buy_no_override_uses_engine_formula():
    items = _items()
    p = _player(gold=100)
    n = _npc(inventory_ids=["dagger"])
    paid = inv.buy(p, n, "dagger", items)
    assert paid == 50
    assert p.gold == 50
    assert n.gold == 75


def test_sell_no_override_uses_engine_formula():
    items = _items()
    p = _player(inventory_ids=["sword"])
    n = _npc(gold=100)
    paid = inv.sell(p, n, "sword", items)
    # base 100 × sell_ratio (0.5) at 0 affinity
    assert paid == 50
    assert p.gold == 150
    assert n.gold == 50


def test_buy_override_zero_is_free():
    items = _items()
    p = _player(gold=0)
    n = _npc(inventory_ids=["dagger"])
    paid = inv.buy(p, n, "dagger", items, price_override=0)
    assert paid == 0
    assert p.gold == 0
    assert n.gold == 25
    assert "dagger" in p.inventory_ids


def test_buy_override_still_checks_player_gold():
    items = _items()
    p = _player(gold=1)
    n = _npc(inventory_ids=["dagger"])
    with pytest.raises(InventoryInvalid, match="not enough gold"):
        inv.buy(p, n, "dagger", items, price_override=2)


def test_sell_override_still_checks_npc_gold():
    items = _items()
    p = _player(inventory_ids=["sword"])
    n = _npc(gold=1)
    with pytest.raises(InventoryInvalid, match="npc has not enough gold"):
        inv.sell(p, n, "sword", items, price_override=2)
