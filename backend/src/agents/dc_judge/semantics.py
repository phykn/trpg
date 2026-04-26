from typing import Any

from .._runner import AgentSemanticError
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


class JudgeSemanticError(AgentSemanticError):
    pass


def collect_valid_ids(surroundings: dict[str, Any]) -> set[str]:
    ids: set[str] = set()
    loc = surroundings.get("location")
    if isinstance(loc, dict) and isinstance(loc.get("id"), str):
        ids.add(loc["id"])
    for ent in surroundings.get("entities", []) or []:
        if isinstance(ent, dict) and isinstance(ent.get("id"), str):
            ids.add(ent["id"])
    return ids


def check_semantics(output: JudgeOutput, surroundings: dict[str, Any]) -> None:
    if isinstance(output, (CombatAction, RollAction)):
        valid = collect_valid_ids(surroundings)
        bad = [t for t in output.targets if t not in valid]
        if bad:
            raise JudgeSemanticError(
                f"targets contains ids not in surroundings: {bad}. "
                f"Valid ids are: {sorted(valid)}. "
                f"If the player referenced something not present, action must be 'clarify'."
            )
    if isinstance(output, CombatAction) and output.skill_id is not None:
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
    if isinstance(output, FleeAction):
        if not surroundings.get("in_combat"):
            raise JudgeSemanticError(
                "flee only valid in combat. Outside combat, use 'pass' or 'roll' instead."
            )
    if isinstance(output, LevelUpAction):
        growth = surroundings.get("growth") or {}
        if not growth.get("can_level_up"):
            raise JudgeSemanticError(
                "level_up not currently available — xp not at threshold. Use 'pass' or 'clarify'."
            )
        # pair check (engine also enforces, but reject obvious mismatch early)
        pairs = {("STR", "CHA"), ("CHA", "STR"), ("DEX", "WIS"), ("WIS", "DEX"), ("CON", "INT"), ("INT", "CON")}
        if (output.stat_up, output.stat_down) not in pairs:
            raise JudgeSemanticError(
                f"invalid pair: {output.stat_up}↑/{output.stat_down}↓. Pairs are STR↔CHA, DEX↔WIS, CON↔INT."
            )
    if isinstance(output, LearnSkillAction):
        candidates = surroundings.get("skill_candidates") or []
        if not candidates:
            raise JudgeSemanticError(
                "no pending skill candidates. Use 'pass' or 'clarify'."
            )
        if output.index >= len(candidates):
            raise JudgeSemanticError(
                f"index {output.index} out of range; only {len(candidates)} candidates."
            )
    if isinstance(output, (BuyAction, SellAction)):
        merchants = surroundings.get("merchants") or []
        merchant = next(
            (m for m in merchants if isinstance(m, dict) and m.get("id") == output.npc_id),
            None,
        )
        if merchant is None:
            raise JudgeSemanticError(
                f"npc_id {output.npc_id!r} is not a trader here. "
                f"Merchants: {sorted(m.get('id', '') for m in merchants if isinstance(m, dict))}."
            )
        if isinstance(output, BuyAction):
            stock_ids = {i.get("id") for i in merchant.get("stock", []) if isinstance(i, dict)}
            if output.item_id not in stock_ids:
                raise JudgeSemanticError(
                    f"item {output.item_id!r} not in {output.npc_id} stock. Available: {sorted(s for s in stock_ids if s)}."
                )
        else:
            inv_ids = {i.get("id") for i in surroundings.get("inventory", []) if isinstance(i, dict)}
            if output.item_id not in inv_ids:
                raise JudgeSemanticError(
                    f"sell item {output.item_id!r} not in player inventory."
                )
    if isinstance(output, UseAction):
        inv_items = {
            i.get("id"): i.get("kind")
            for i in surroundings.get("inventory", []) or []
            if isinstance(i, dict)
        }
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
            entity_ids = collect_valid_ids(surroundings)
            if output.target_id not in entity_ids:
                raise JudgeSemanticError(
                    f"target_id {output.target_id!r} not in surroundings."
                )

    if isinstance(output, EquipAction):
        inv_items = {
            i.get("id"): i.get("kind")
            for i in surroundings.get("inventory", []) or []
            if isinstance(i, dict)
        }
        if output.item_id not in inv_items:
            raise JudgeSemanticError(
                f"equip item_id {output.item_id!r} not in inventory."
            )
        if inv_items[output.item_id] not in ("weapon", "armor"):
            raise JudgeSemanticError(
                f"item {output.item_id!r} is not equippable (weapon/armor only)."
            )

    if isinstance(output, UnequipAction):
        eq = surroundings.get("equipment") or {}
        equipped_ids: set[str] = set()
        for v in eq.values():
            if isinstance(v, dict) and isinstance(v.get("id"), str):
                equipped_ids.add(v["id"])
        if output.item_id not in equipped_ids:
            raise JudgeSemanticError(
                f"unequip item_id {output.item_id!r} not currently equipped. "
                f"Equipped: {sorted(equipped_ids)}."
            )
