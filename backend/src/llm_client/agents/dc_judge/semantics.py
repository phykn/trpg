from typing import Any

from .schema import (
    CombatAction,
    EquipAction,
    JudgeOutput,
    RollAction,
    UnequipAction,
    UseAction,
)


class JudgeSemanticError(ValueError):
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
            for s in surroundings.get("learned_skills", []) or []
            if isinstance(s, dict)
        }
        if output.skill_id not in valid_skills:
            raise JudgeSemanticError(
                f"skill_id {output.skill_id!r} not in learned_skills. "
                f"Valid skills are: {sorted(s for s in valid_skills if s)}. "
                f"Either pick one from the list or omit skill_id for a plain attack."
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
