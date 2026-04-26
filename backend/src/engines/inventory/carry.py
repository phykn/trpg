"""Carry capacity (STR × weight_per_strength) gating."""
from ...domain.entities import Character, Item
from ...domain.errors import InventoryInvalid
from ...rules import RULES


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
