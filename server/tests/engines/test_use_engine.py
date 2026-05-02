"""Item use — heal/damage/mp_restore/buff + on_use + consumable decrement."""

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
from src.domain.state import GameState
from src.engines import inventory as inv


def _state(*characters: Character, items: dict | None = None) -> GameState:
    s = GameState(
        game_id="t",
        profile="default",
        player_id=characters[0].id if characters else "player_01",
    )
    for c in characters:
        s.characters[c.id] = c
    if items:
        s.items.update(items)
    return s


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
    s = _state(p, items={"potion_heal": _heal_potion()})
    res = inv.use(p, "potion_heal", None, s)
    assert p.hp == 18
    assert res["kind"] == "heal"
    assert res["amount"] == 8
    assert res["consumed"] is True
    assert "potion_heal" not in p.inventory_ids


def test_use_heal_caps_at_max_hp():
    p = _player(inventory_ids=["potion_heal", "potion_heal"])
    p.hp = 18
    s = _state(p, items={"potion_heal": _heal_potion()})
    res = inv.use(p, "potion_heal", None, s)
    assert p.hp == 20
    assert res["amount"] == 2


# --- damage ---------------------------------------------------------------


def test_use_damage_requires_target():
    p = _player(inventory_ids=["bomb"])
    s = _state(p, items={"bomb": _damage_potion()})
    with pytest.raises(InventoryInvalid, match="target"):
        inv.use(p, "bomb", None, s)


def test_use_damage_applies_to_target():
    p = _player(inventory_ids=["bomb"])
    enemy = _other(id="goblin_01", hp=15, max_hp=15)
    s = _state(p, enemy, items={"bomb": _damage_potion()})
    res = inv.use(p, "bomb", enemy, s)
    assert enemy.hp == 3
    assert res["amount"] == 12


def test_use_damage_kills_target_when_hp_zeroes():
    p = _player(inventory_ids=["bomb"])
    enemy = _other(hp=5)
    s = _state(p, enemy, items={"bomb": _damage_potion()})
    res = inv.use(p, "bomb", enemy, s)
    assert enemy.hp == 0
    assert not enemy.alive
    assert res.get("dead") is True


def test_use_damage_on_player_arms_death_save_instead_of_killing():
    # Regression for F-eng-07: a damage item that drops the player to 0 HP
    # should arm death_saves (or burn a revive_coin), not flip alive=False
    # the way melee damage routed through apply_attack_to_defender does.
    attacker = _other(id="enemy_01", inventory_ids=["bomb"])
    victim = _player(hp=5, revive_coins=0)
    s = _state(victim, attacker, items={"bomb": _damage_potion()})
    res = inv.use(attacker, "bomb", victim, s)
    assert victim.hp == 0
    assert victim.alive  # still alive — in death-save state
    assert victim.death_saves is not None
    assert res.get("dying") is True


def test_use_damage_on_player_consumes_revive_coin():
    attacker = _other(id="enemy_01", inventory_ids=["bomb"])
    victim = _player(hp=5, max_hp=20, revive_coins=1)
    s = _state(victim, attacker, items={"bomb": _damage_potion()})
    res = inv.use(attacker, "bomb", victim, s)
    assert victim.alive
    assert victim.revive_coins == 0
    assert victim.death_saves is None
    assert victim.hp == 1  # revived to auto_revive_hp
    assert res.get("revived") is True


# --- mp_restore -----------------------------------------------------------


def test_use_mp_potion_increases_mp():
    p = _player(inventory_ids=["mana_potion"])
    s = _state(p, items={"mana_potion": _mp_potion()})
    res = inv.use(p, "mana_potion", None, s)
    assert p.mp == 10
    assert res["kind"] == "mp_restore"


def test_use_mp_caps_at_max_mp():
    p = _player(inventory_ids=["mana_potion"])
    p.mp = 14
    s = _state(p, items={"mana_potion": _mp_potion()})
    res = inv.use(p, "mana_potion", None, s)
    assert p.mp == 15
    assert res["amount"] == 1


# --- buff -----------------------------------------------------------------


def test_use_buff_scroll_appends_active_buff():
    p = _player(inventory_ids=["strength_scroll"])
    s = _state(p, items={"strength_scroll": _buff_scroll()})
    res = inv.use(p, "strength_scroll", None, s)
    assert len(p.active_buffs) == 1
    b = p.active_buffs[0]
    assert b.description == "근력 일시 강화"
    assert b.duration == 5
    assert res["kind"] == "buff"


# --- on_use trigger -------------------------------------------------------


def test_use_quest_key_includes_on_use_in_result():
    p = _player(inventory_ids=["quest_key"])
    s = _state(p, items={"quest_key": _key()})
    res = inv.use(p, "quest_key", None, s)
    assert res["kind"] == "trigger"
    assert res["on_use"] == "open_ancient_door"
    assert res.get("consumed") is None  # consumable=False
    assert "quest_key" in p.inventory_ids  # still in inventory


# --- Validation -----------------------------------------------------------


def test_use_rejects_weapon():
    p = _player(inventory_ids=["sword"])
    s = _state(p, items={"sword": _weapon()})
    with pytest.raises(InventoryInvalid, match="not consumable"):
        inv.use(p, "sword", None, s)


def test_use_rejects_unknown_item():
    p = _player()
    s = _state(p)
    with pytest.raises(InventoryInvalid):
        inv.use(p, "missing", None, s)


def test_use_rejects_item_not_in_inventory():
    p = _player()
    s = _state(p, items={"potion_heal": _heal_potion()})
    with pytest.raises(InventoryInvalid, match="not in inventory"):
        inv.use(p, "potion_heal", None, s)


def test_use_dirty_set_includes_actor_and_target():
    p = _player(inventory_ids=["bomb"])
    enemy = _other()
    s = _state(p, enemy, items={"bomb": _damage_potion()})
    dirty: set[tuple[str, str]] = set()
    inv.use(p, "bomb", enemy, s, dirty=dirty)
    assert ("characters", "player_01") in dirty
    assert ("characters", "ally_01") in dirty


def test_use_self_target_does_not_double_dirty_self():
    p = _player(inventory_ids=["potion_heal"])
    s = _state(p, items={"potion_heal": _heal_potion()})
    dirty: set[tuple[str, str]] = set()
    inv.use(p, "potion_heal", None, s, dirty=dirty)
    assert dirty == {("characters", "player_01")}
