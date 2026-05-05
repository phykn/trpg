from typing import Any, Callable

from .schema import JudgeOutput, Verb, VerbName


class JudgeSemanticError(Exception):
    pass


# ─── Helpers ──────────────────────────────────────────────────────────────────

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


def _surroundings_target_ids(
    surroundings: dict[str, Any], *, include_corpses: bool = False
) -> set[str]:
    ids: set[str] = set()
    loc = surroundings.get("location")
    if isinstance(loc, dict) and isinstance(loc.get("id"), str):
        ids.add(loc["id"])
    for ent in surroundings.get("entities", []) or []:
        if isinstance(ent, dict) and isinstance(ent.get("id"), str):
            ids.add(ent["id"])
    if include_corpses:
        for corpse in surroundings.get("corpses", []) or []:
            if isinstance(corpse, dict) and isinstance(corpse.get("id"), str):
                ids.add(corpse["id"])
    return ids


def _entities_by_id(surroundings: dict[str, Any]) -> dict[str, dict]:
    return {
        e["id"]: e
        for e in surroundings.get("entities") or []
        if isinstance(e, dict) and isinstance(e.get("id"), str)
    }


def _is_friendly(entity: dict) -> bool:
    return bool(entity.get("friendly"))


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


# ─── Per-verb checks ──────────────────────────────────────────────────────────

def _check_attack(verb: Verb, surroundings: dict[str, Any]) -> None:
    valid_target_ids = _surroundings_target_ids(surroundings)
    bad = [t for t in verb.target_ids if t not in valid_target_ids]
    if bad:
        raise JudgeSemanticError(
            f"attack target ids not in surroundings: {bad}. "
            f"Valid ids: {sorted(valid_target_ids)}."
        )
    by_id = _entities_by_id(surroundings)
    hostile_npcs = sorted(
        eid for eid, e in by_id.items()
        if e.get("type") == "npc" and not _is_friendly(e)
    )
    for tid in verb.target_ids:
        ent = by_id.get(tid)
        if ent is None:
            raise JudgeSemanticError(
                f"attack target {tid!r} is not an NPC entity. "
                f"Hostile/neutral NPCs here: {hostile_npcs}."
            )
        ent_type = ent.get("type")
        if ent_type != "npc":
            raise JudgeSemanticError(
                f"attack target {tid!r} has type={ent_type!r}; only NPCs valid."
            )
        if _is_friendly(ent):
            raise JudgeSemanticError(
                f"attack target {tid!r} is friendly. Use speak(intent=hostile) instead."
            )
    skill_id = verb.modifiers.get("skill_id")
    if skill_id is not None:
        valid_skills = {
            s.get("id") for s in surroundings.get("skills", []) or [] if isinstance(s, dict)
        }
        if skill_id not in valid_skills:
            raise JudgeSemanticError(
                f"skill_id {skill_id!r} not in skills. Valid: {sorted(s for s in valid_skills if s)}."
            )


def _check_cast(verb: Verb, surroundings: dict[str, Any]) -> None:
    skill_id = verb.modifiers.get("skill_id")
    valid_skills = {
        s.get("id") for s in surroundings.get("skills", []) or [] if isinstance(s, dict)
    }
    if skill_id not in valid_skills:
        raise JudgeSemanticError(
            f"cast skill_id {skill_id!r} not in skills. Valid: {sorted(s for s in valid_skills if s)}."
        )


def _check_speak(verb: Verb, surroundings: dict[str, Any]) -> None:
    intent = verb.modifiers.get("intent")
    target = verb.modifiers.get("target")
    if intent == "recruit":
        _check_recruit_inner(target, surroundings)
    elif intent == "part":
        _check_dismiss_inner(target, surroundings)
    # Other intents (friendly/hostile/deceptive/negotiate/ask/command/pray)
    # have no surroundings-dependent check — schema validator covers the intent itself.


def _check_recruit_inner(target: str | None, surroundings: dict[str, Any]) -> None:
    if target is None:
        raise JudgeSemanticError("speak(intent=recruit) requires target modifier")
    by_id = _entities_by_id(surroundings)
    ent = by_id.get(target)
    if ent is None:
        raise JudgeSemanticError(
            f"recruit target {target!r} not in surroundings. "
            f"Valid entities: {sorted(by_id.keys())}."
        )
    if int(ent.get("relations_player") or 0) < 0:
        raise JudgeSemanticError(
            f"recruit target {target!r} is hostile (relations_player < 0)."
        )
    if bool(ent.get("protected")):
        raise JudgeSemanticError(
            f"recruit target {target!r} is protected (unfit for adventuring)."
        )
    companions = surroundings.get("companions") or []
    if target in companions:
        raise JudgeSemanticError(
            f"recruit target {target!r} is already a companion."
        )
    max_n = int(surroundings.get("companions_max", 3))
    if len(companions) >= max_n:
        raise JudgeSemanticError(
            f"companion party at capacity ({len(companions)}/{max_n})."
        )


def _check_dismiss_inner(target: str | None, surroundings: dict[str, Any]) -> None:
    if target is None:
        raise JudgeSemanticError("speak(intent=part) requires target modifier")
    companions = surroundings.get("companions") or []
    if target not in companions:
        raise JudgeSemanticError(
            f"dismiss target {target!r} is not a companion. "
            f"Current companions: {sorted(companions)}."
        )


def _check_transfer(verb: Verb, surroundings: dict[str, Any]) -> None:
    mode = verb.modifiers.get("mode")
    item_id = verb.modifiers.get("item_id")
    from_id = verb.modifiers.get("from_id")
    to_id = verb.modifiers.get("to_id")
    if mode == "trade":
        # buy: from_id=npc, to_id=player. sell: from_id=player, to_id=npc.
        npc_id = from_id if to_id == "player_01" else to_id
        merchant = _find_merchant(npc_id, surroundings)
        if from_id != "player_01":  # buy
            stock_ids = {i.get("id") for i in merchant.get("stock", []) if isinstance(i, dict)}
            if item_id not in stock_ids:
                raise JudgeSemanticError(
                    f"item {item_id!r} not in {npc_id} stock. "
                    f"Available: {sorted(s for s in stock_ids if s)}."
                )
        else:  # sell
            inv_ids = {i.get("id") for i in surroundings.get("inventory", []) if isinstance(i, dict)}
            if item_id not in inv_ids:
                raise JudgeSemanticError(f"sell item {item_id!r} not in player inventory.")


def _check_use(verb: Verb, surroundings: dict[str, Any]) -> None:
    item_id = verb.modifiers.get("item_id")
    target_id = verb.modifiers.get("target_id")
    inv_items = _inventory_kinds(surroundings)
    if item_id not in inv_items:
        raise JudgeSemanticError(
            f"item_id {item_id!r} not in inventory. "
            f"Valid: {sorted(i for i in inv_items if i)}."
        )
    kind = inv_items[item_id]
    if kind in ("weapon", "armor"):
        raise JudgeSemanticError(
            f"item {item_id!r} is a {kind} — use transfer(equip), not use."
        )
    if target_id is not None:
        if target_id not in _surroundings_target_ids(surroundings):
            raise JudgeSemanticError(f"target_id {target_id!r} not in surroundings.")


# ─── _CHECKS table ────────────────────────────────────────────────────────────

_CHECKS: dict[VerbName, Callable[[Verb, dict[str, Any]], None]] = {
    "attack": _check_attack,
    "cast": _check_cast,
    "speak": _check_speak,
    "transfer": _check_transfer,
    "use": _check_use,
    # move, rest, wait, perceive, alter: pass automatically after schema/modifier validation
}


def check_semantics(output: JudgeOutput, surroundings: dict[str, Any]) -> None:
    """Run per-verb semantic checks on each Verb in JudgeOutput.actions.
    Refuse and empty-actions paths are no-ops."""
    if output.refuse is not None or output.actions is None:
        return
    for verb in output.actions:
        check = _CHECKS.get(verb.name)
        if check is not None:
            check(verb, surroundings)
