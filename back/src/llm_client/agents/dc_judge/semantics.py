from typing import Any

from .schema import CombatAction, JudgeOutput, RollAction


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
