"""아이템 사용 (use) — heal/damage/mp_restore/buff + on_use + consumable 차감."""
import pytest

from src.domain.entities import (
    ArmorEffect,
    Character,
    ConsumableEffect,
    Item,
    Stats,
    WeaponEffect,
)
from src.errors import InventoryInvalid
from src.pipeline import inventory as inv


def _player(**kw):
    p = Character(
        id="player_01",
        name="주",
        race_id="human",
        is_player=True,
        stats=Stats(),
        hp=10,
        max_hp=20,
        mp=5,
        max_mp=15,
    )
    for k, v in kw.items():
        setattr(p, k, v)
    return p


def _other(**kw):
    n = Character(
        id="ally_01",
        name="동료",
        race_id="human",
        stats=Stats(),
        hp=8,
        max_hp=20,
    )
    for k, v in kw.items():
        setattr(n, k, v)
    return n


def _heal_potion(**kw):
    return Item(
        id="potion_heal",
        name="치유 물약",
        weight=0.5,
        price=20,
        consumable=True,
        effects=ConsumableEffect(type="consumable", effect="heal", amount=8),
        **kw,
    )


def _damage_potion(**kw):
    return Item(
        id="bomb",
        name="폭탄",
        consumable=True,
        effects=ConsumableEffect(type="consumable", effect="damage", amount=12),
        **kw,
    )


def _mp_potion(**kw):
    return Item(
        id="mana_potion",
        name="마나 물약",
        consumable=True,
        effects=ConsumableEffect(type="consumable", effect="mp_restore", amount=5),
        **kw,
    )


def _buff_scroll(**kw):
    return Item(
        id="strength_scroll",
        name="힘의 두루마리",
        consumable=True,
        effects=ConsumableEffect(
            type="consumable",
            effect="buff",
            description="근력 일시 강화",
            duration=5,
        ),
        **kw,
    )


def _key():
    return Item(id="quest_key", name="고대의 열쇠", on_use="open_ancient_door")


def _weapon():
    return Item(
        id="sword",
        name="검",
        effects=WeaponEffect(type="weapon", weapon_dice="1d8"),
    )


# --- heal -----------------------------------------------------------------


def test_use_heal_potion_increases_hp_and_consumes_item():
    p = _player(inventory_ids=["potion_heal"])
    items = {"potion_heal": _heal_potion()}
    res = inv.use(p, "potion_heal", None, items)
    assert p.hp == 18
    assert res["kind"] == "heal"
    assert res["amount"] == 8
    assert res["consumed"] is True
    assert "potion_heal" not in p.inventory_ids


def test_use_heal_caps_at_max_hp():
    p = _player(inventory_ids=["potion_heal", "potion_heal"])
    p.hp = 18
    items = {"potion_heal": _heal_potion()}
    res = inv.use(p, "potion_heal", None, items)
    assert p.hp == 20
    assert res["amount"] == 2


# --- damage ---------------------------------------------------------------


def test_use_damage_requires_target():
    p = _player(inventory_ids=["bomb"])
    items = {"bomb": _damage_potion()}
    with pytest.raises(InventoryInvalid, match="target"):
        inv.use(p, "bomb", None, items)


def test_use_damage_applies_to_target():
    p = _player(inventory_ids=["bomb"])
    enemy = _other(id="goblin_01", hp=15, max_hp=15)
    items = {"bomb": _damage_potion()}
    res = inv.use(p, "bomb", enemy, items)
    assert enemy.hp == 3
    assert res["amount"] == 12


def test_use_damage_kills_target_when_hp_zeroes():
    p = _player(inventory_ids=["bomb"])
    enemy = _other(hp=5)
    items = {"bomb": _damage_potion()}
    res = inv.use(p, "bomb", enemy, items)
    assert enemy.hp == 0
    assert not enemy.alive
    assert res.get("dead") is True


# --- mp_restore -----------------------------------------------------------


def test_use_mp_potion_increases_mp():
    p = _player(inventory_ids=["mana_potion"])
    items = {"mana_potion": _mp_potion()}
    res = inv.use(p, "mana_potion", None, items)
    assert p.mp == 10
    assert res["kind"] == "mp_restore"


def test_use_mp_caps_at_max_mp():
    p = _player(inventory_ids=["mana_potion"])
    p.mp = 14
    items = {"mana_potion": _mp_potion()}
    res = inv.use(p, "mana_potion", None, items)
    assert p.mp == 15
    assert res["amount"] == 1


# --- buff -----------------------------------------------------------------


def test_use_buff_scroll_appends_active_buff():
    p = _player(inventory_ids=["strength_scroll"])
    items = {"strength_scroll": _buff_scroll()}
    res = inv.use(p, "strength_scroll", None, items)
    assert len(p.active_buffs) == 1
    b = p.active_buffs[0]
    assert b.description == "근력 일시 강화"
    assert b.duration == 5
    assert res["kind"] == "buff"


# --- on_use trigger -------------------------------------------------------


def test_use_quest_key_includes_on_use_in_result():
    p = _player(inventory_ids=["quest_key"])
    items = {"quest_key": _key()}
    res = inv.use(p, "quest_key", None, items)
    assert res["kind"] == "trigger"
    assert res["on_use"] == "open_ancient_door"
    assert res.get("consumed") is None  # consumable=False
    assert "quest_key" in p.inventory_ids  # 그대로 남음


# --- 검증 -----------------------------------------------------------------


def test_use_rejects_weapon():
    p = _player(inventory_ids=["sword"])
    items = {"sword": _weapon()}
    with pytest.raises(InventoryInvalid, match="not consumable"):
        inv.use(p, "sword", None, items)


def test_use_rejects_unknown_item():
    p = _player()
    with pytest.raises(InventoryInvalid):
        inv.use(p, "missing", None, {})


def test_use_rejects_item_not_in_inventory():
    p = _player()
    items = {"potion_heal": _heal_potion()}
    with pytest.raises(InventoryInvalid, match="not in inventory"):
        inv.use(p, "potion_heal", None, items)


def test_use_dirty_set_includes_actor_and_target():
    p = _player(inventory_ids=["bomb"])
    enemy = _other()
    items = {"bomb": _damage_potion()}
    dirty: set[tuple[str, str]] = set()
    inv.use(p, "bomb", enemy, items, dirty=dirty)
    assert ("characters", "player_01") in dirty
    assert ("characters", "ally_01") in dirty


def test_use_self_target_does_not_double_dirty_self():
    p = _player(inventory_ids=["potion_heal"])
    items = {"potion_heal": _heal_potion()}
    dirty: set[tuple[str, str]] = set()
    inv.use(p, "potion_heal", None, items, dirty=dirty)
    assert dirty == {("characters", "player_01")}
