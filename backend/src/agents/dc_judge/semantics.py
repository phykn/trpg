from typing import Any, Callable

from ...domain.types import STAT_PAIRS
from .schema import (
    BuyAction,
    CombatAction,
    EquipAction,
    FleeAction,
    JudgeOutput,
    LearnSkillAction,
    LevelUpAction,
    RollAction,
    SellAction,
    UnequipAction,
    UseAction,
)


# --- helpers ---------------------------------------------------------------


def _inventory_kinds(surroundings: dict[str, Any]) -> dict[str, str]:
    return {
        i.get("id"): i.get("kind")
        for i in surroundings.get("inventory") or []
        if isinstance(i, dict)
    }


def _equipped_ids(surroundings: dict[str, Any]) -> set[str]:
    out: set[str] = set()
    for v in (surroundings.get("equipment") or {}).values():
        if isinstance(v, dict) and isinstance(v.get("id"), str):
            out.add(v["id"])
    return out


def _surroundings_target_ids(surroundings: dict[str, Any]) -> set[str]:
    ids: set[str] = set()
    loc = surroundings.get("location")
    if isinstance(loc, dict) and isinstance(loc.get("id"), str):
        ids.add(loc["id"])
    for ent in surroundings.get("entities", []) or []:
        if isinstance(ent, dict) and isinstance(ent.get("id"), str):
            ids.add(ent["id"])
    return ids


class JudgeSemanticError(Exception):
    pass


def _find_merchant(npc_id: str, surroundings: dict[str, Any]) -> dict:
    merchants = surroundings.get("merchants") or []
    merchant = next(
        (m for m in merchants if isinstance(m, dict) and m.get("id") == npc_id),
        None,
    )
    if merchant is None:
        raise JudgeSemanticError(
            f"npc_id {npc_id!r} is not a trader here. "
            f"Merchants: {sorted(m.get('id', '') for m in merchants if isinstance(m, dict))}."
        )
    return merchant


def _check_targets(output, surroundings: dict[str, Any]) -> None:
    valid = _surroundings_target_ids(surroundings)
    bad = [t for t in output.targets if t not in valid]
    if bad:
        raise JudgeSemanticError(
            f"targets contains ids not in surroundings: {bad}. "
            f"Valid ids are: {sorted(valid)}. "
            f"If the player referenced something not present, action must be 'clarify'."
        )


# --- per-action checks -----------------------------------------------------


def _check_combat(output: CombatAction, surroundings: dict[str, Any]) -> None:
    _check_targets(output, surroundings)
    if output.skill_id is None:
        return
    valid_skills = {
        s.get("id")
        for s in surroundings.get("skills", []) or []
        if isinstance(s, dict)
    }
    if output.skill_id not in valid_skills:
        raise JudgeSemanticError(
            f"skill_id {output.skill_id!r} not in skills. "
            f"Valid skills are: {sorted(s for s in valid_skills if s)}. "
            f"Either pick one from the list or omit skill_id for a plain attack."
        )


def _check_roll(output: RollAction, surroundings: dict[str, Any]) -> None:
    _check_targets(output, surroundings)


def _check_flee(output: FleeAction, surroundings: dict[str, Any]) -> None:
    if not surroundings.get("in_combat"):
        raise JudgeSemanticError(
            "flee only valid in combat. Outside combat, use 'pass' or 'roll' instead."
        )


def _check_level_up(output: LevelUpAction, surroundings: dict[str, Any]) -> None:
    growth = surroundings.get("growth") or {}
    if not growth.get("can_level_up"):
        raise JudgeSemanticError(
            "level_up not currently available — xp not at threshold. Use 'pass' or 'clarify'."
        )
    if STAT_PAIRS.get(output.stat_up) != output.stat_down:
        raise JudgeSemanticError(
            f"invalid pair: {output.stat_up}↑/{output.stat_down}↓. Pairs are STR↔CHA, DEX↔WIS, CON↔INT."
        )


def _check_learn_skill(output: LearnSkillAction, surroundings: dict[str, Any]) -> None:
    candidates = surroundings.get("skill_candidates") or []
    if not candidates:
        raise JudgeSemanticError("no pending skill candidates. Use 'pass' or 'clarify'.")
    if output.index >= len(candidates):
        raise JudgeSemanticError(
            f"index {output.index} out of range; only {len(candidates)} candidates."
        )


def _check_buy(output: BuyAction, surroundings: dict[str, Any]) -> None:
    merchant = _find_merchant(output.npc_id, surroundings)
    stock_ids = {i.get("id") for i in merchant.get("stock", []) if isinstance(i, dict)}
    if output.item_id not in stock_ids:
        raise JudgeSemanticError(
            f"item {output.item_id!r} not in {output.npc_id} stock. "
            f"Available: {sorted(s for s in stock_ids if s)}."
        )


def _check_sell(output: SellAction, surroundings: dict[str, Any]) -> None:
    _find_merchant(output.npc_id, surroundings)
    inv_ids = {i.get("id") for i in surroundings.get("inventory", []) if isinstance(i, dict)}
    if output.item_id not in inv_ids:
        raise JudgeSemanticError(f"sell item {output.item_id!r} not in player inventory.")


def _check_use(output: UseAction, surroundings: dict[str, Any]) -> None:
    inv_items = _inventory_kinds(surroundings)
    if output.item_id not in inv_items:
        raise JudgeSemanticError(
            f"item_id {output.item_id!r} not in inventory. "
            f"Valid items are: {sorted(i for i in inv_items if i)}. "
            f"If the player referenced something they don't carry, action must be 'clarify'."
        )
    kind = inv_items[output.item_id]
    if kind in ("weapon", "armor"):
        raise JudgeSemanticError(
            f"item {output.item_id!r} is a {kind} — use action='equip', not 'use'."
        )
    if output.target_id is not None:
        entity_ids = _surroundings_target_ids(surroundings)
        if output.target_id not in entity_ids:
            raise JudgeSemanticError(f"target_id {output.target_id!r} not in surroundings.")


def _check_equip(output: EquipAction, surroundings: dict[str, Any]) -> None:
    inv_items = _inventory_kinds(surroundings)
    if output.item_id not in inv_items:
        raise JudgeSemanticError(f"equip item_id {output.item_id!r} not in inventory.")
    if inv_items[output.item_id] not in ("weapon", "armor"):
        raise JudgeSemanticError(
            f"item {output.item_id!r} is not equippable (weapon/armor only)."
        )


def _check_unequip(output: UnequipAction, surroundings: dict[str, Any]) -> None:
    equipped_ids = _equipped_ids(surroundings)
    if output.item_id not in equipped_ids:
        raise JudgeSemanticError(
            f"unequip item_id {output.item_id!r} not currently equipped. "
            f"Equipped: {sorted(equipped_ids)}."
        )


# --- dispatch --------------------------------------------------------------


_CHECKS: dict[type, Callable[[Any, dict[str, Any]], None]] = {
    CombatAction: _check_combat,
    RollAction: _check_roll,
    FleeAction: _check_flee,
    LevelUpAction: _check_level_up,
    LearnSkillAction: _check_learn_skill,
    BuyAction: _check_buy,
    SellAction: _check_sell,
    UseAction: _check_use,
    EquipAction: _check_equip,
    UnequipAction: _check_unequip,
}


def check_semantics(output: JudgeOutput, surroundings: dict[str, Any]) -> None:
    check = _CHECKS.get(type(output))
    if check is not None:
        check(output, surroundings)
