"""장비 / 인벤토리 / 거래 (P3 §2.5).

equip/unequip 은 슬롯 검증과 Item.required Stats 충족을 확인하고,
inventory 무게는 STR × weight_per_strength 캡, 거래는 affinity 게이트와
흥정 가격 (affinity_price_per_point × affinity, cap 0.5) 을 적용한다.
"""
from __future__ import annotations

from typing import Literal

from ..domain.entities import (
    EQUIPMENT_SLOTS,
    ArmorEffect,
    Character,
    ConsumableEffect,
    Item,
    WeaponEffect,
)
from ..errors import InventoryInvalid
from ..rules import RULES

Slot = Literal[
    "head", "top", "bottom", "feet", "leftHand", "rightHand", "acc1", "acc2"
]

_HAND_SLOTS = ("leftHand", "rightHand")
_ARMOR_SLOTS = ("head", "top", "bottom", "feet")
_ACC_SLOTS = ("acc1", "acc2")


# --- carry ----------------------------------------------------------------


def carry_capacity(actor: Character) -> float:
    return RULES.carry.weight_per_strength * actor.stats.STR


def current_weight(actor: Character, items: dict[str, Item]) -> float:
    return sum(items[i].weight for i in actor.inventory_ids if i in items)


def check_can_carry(actor: Character, items: dict[str, Item], extra_id: str) -> None:
    if extra_id not in items:
        raise InventoryInvalid(f"unknown item: {extra_id}")
    new_weight = current_weight(actor, items) + items[extra_id].weight
    cap = carry_capacity(actor)
    if new_weight > cap:
        raise InventoryInvalid(
            f"carry capacity exceeded: {new_weight:.1f} > {cap:.1f}"
        )


# --- equipment ------------------------------------------------------------


def _slot_kind(slot: Slot) -> str:
    if slot in _HAND_SLOTS:
        return "hand"
    if slot in _ARMOR_SLOTS:
        return "armor"
    return "acc"


def _required_stats_met(actor: Character, item: Item) -> bool:
    if item.required is None:
        return True
    for k in ("STR", "DEX", "CON", "INT", "WIS", "CHA"):
        need = getattr(item.required, k)
        have = getattr(actor.stats, k)
        if have < need:
            return False
    return True


def _validate_slot_for_item(slot: Slot, item: Item) -> None:
    if slot not in EQUIPMENT_SLOTS:
        raise InventoryInvalid(f"unknown slot: {slot}")
    eff = item.effects
    kind = _slot_kind(slot)
    if isinstance(eff, WeaponEffect):
        if kind != "hand":
            raise InventoryInvalid(f"weapon must go in leftHand or rightHand, got {slot}")
    elif isinstance(eff, ArmorEffect):
        if kind != "armor":
            raise InventoryInvalid(f"armor must go in head/top/bottom/feet, got {slot}")
    elif isinstance(eff, ConsumableEffect):
        raise InventoryInvalid(f"consumable items can't be equipped")
    # effects=None (예: 액세서리·장식) → acc 슬롯만 허용.
    elif kind == "acc":
        pass
    else:
        raise InventoryInvalid(f"item {item.id} has no equippable effect for slot {slot}")


def equip(actor: Character, item_id: str, slot: Slot, items: dict[str, Item]) -> None:
    """item_id 를 slot 에 장착. 슬롯 충돌·요구치 미충족·소비 아이템 등 거부.

    two_handed 무기는 두 손 슬롯을 모두 차지 — 어느 손 슬롯을 명시하든 양쪽에 같은 id 박힘.
    기존 장착 아이템은 자동 unequip (인벤토리 안에 그대로 남음).
    """
    if item_id not in items:
        raise InventoryInvalid(f"unknown item: {item_id}")
    if item_id not in actor.inventory_ids:
        raise InventoryInvalid(f"item not in inventory: {item_id}")
    item = items[item_id]
    _validate_slot_for_item(slot, item)
    if not _required_stats_met(actor, item):
        raise InventoryInvalid(f"required stats not met for {item_id}")

    eff = item.effects
    two_handed = isinstance(eff, WeaponEffect) and eff.two_handed

    if two_handed:
        # 양손 무기 — 두 손 슬롯에 같은 id 박음.
        actor.equipment.leftHand = item_id
        actor.equipment.rightHand = item_id
        return

    # 단일 슬롯. 다른 손에 양손 무기 박혀 있으면 unequip 먼저.
    if slot in _HAND_SLOTS:
        other = "rightHand" if slot == "leftHand" else "leftHand"
        other_id = getattr(actor.equipment, other)
        if other_id and other_id in items:
            other_eff = items[other_id].effects
            if isinstance(other_eff, WeaponEffect) and other_eff.two_handed:
                setattr(actor.equipment, other, None)
    setattr(actor.equipment, slot, item_id)


def unequip(actor: Character, slot: Slot, items: dict[str, Item]) -> None:
    """slot 의 아이템 해제. 양손 무기였으면 두 손 슬롯 모두 비움."""
    if slot not in EQUIPMENT_SLOTS:
        raise InventoryInvalid(f"unknown slot: {slot}")
    item_id = getattr(actor.equipment, slot)
    if item_id is None:
        return  # idempotent
    item = items.get(item_id)
    if item is not None:
        eff = item.effects
        if isinstance(eff, WeaponEffect) and eff.two_handed:
            actor.equipment.leftHand = None
            actor.equipment.rightHand = None
            return
    setattr(actor.equipment, slot, None)


# --- trade ----------------------------------------------------------------


def _affinity_modifier(npc: Character, player: Character) -> float:
    """가격 보정 (-cap..+cap). NPC 의 player 에 대한 affinity 가 양쪽 거래의 기준."""
    aff = npc.relations.get(player.id, 0)
    raw = RULES.trade.affinity_price_per_point * aff
    cap = RULES.trade.affinity_price_cap
    if raw > cap:
        return cap
    if raw < -cap:
        return -cap
    return raw


def buy_price(item: Item, npc: Character, player: Character) -> int:
    """NPC 가 player 에게 파는 가격. NPC 가 player 를 좋아하면 할인."""
    mod = _affinity_modifier(npc, player)
    return max(0, round(item.price * (1 - mod)))


def sell_price(item: Item, player: Character, npc: Character) -> int:
    """player 가 NPC 에게 파는 가격. base × sell_ratio, NPC 가 player 좋아하면 비싸게 사줌."""
    mod = _affinity_modifier(npc, player)
    base = item.price * RULES.trade.sell_ratio
    return max(0, round(base * (1 + mod)))


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
) -> int:
    """player 가 npc 에게서 item 구매. 검증 통과 시 골드/인벤 이전, 가격 반환."""
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
    player: Character,
    npc: Character,
    item_id: str,
    items: dict[str, Item],
) -> int:
    """player 가 npc 에게 item 판매. 검증 통과 시 골드/인벤 이전, 가격 반환."""
    _check_trade_allowed(npc, player)
    if item_id not in items:
        raise InventoryInvalid(f"unknown item: {item_id}")
    if item_id not in player.inventory_ids:
        raise InventoryInvalid(f"player has no such item: {item_id}")
    # 장착 중인 아이템은 거래 안 됨 — 먼저 unequip 하라.
    for s in EQUIPMENT_SLOTS:
        if getattr(player.equipment, s) == item_id:
            raise InventoryInvalid(f"can't sell equipped item: {item_id}")
    price = sell_price(items[item_id], player, npc)
    if npc.gold < price:
        raise InventoryInvalid(f"npc has not enough gold: {npc.gold} < {price}")

    player.inventory_ids.remove(item_id)
    npc.inventory_ids.append(item_id)
    player.gold += price
    npc.gold -= price
    return price
