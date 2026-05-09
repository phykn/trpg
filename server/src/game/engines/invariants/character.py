"""Character and stats invariant checks."""

from __future__ import annotations

from ...domain.entities import Character, Item, Skill
from ...rules import RULES
from ..growth import calc_max_hp, calc_max_mp
from .base import _v


def check_stats(stats) -> list[str]:
    """Pair-trade: STR+CHA = DEX+WIS = CON+INT = 20."""
    out: list[str] = []
    p1 = stats.STR + stats.CHA
    p2 = stats.DEX + stats.WIS
    p3 = stats.CON + stats.INT
    if p1 != 20:
        out.append(f"stats.STR+CHA: expected 20, got {p1}")
    if p2 != 20:
        out.append(f"stats.DEX+WIS: expected 20, got {p2}")
    if p3 != 20:
        out.append(f"stats.CON+INT: expected 20, got {p3}")
    return out


def check_character(c: Character) -> list[str]:
    """Stateless rules — no items pool / scenario context needed."""
    where = f"characters/{c.id}"
    out: list[str] = []

    for v in check_stats(c.stats):
        _v(out, where, v)

    expected_hp = calc_max_hp(c.level, c.stats.CON)
    expected_mp = calc_max_mp(c.level, c.stats.INT)
    if c.max_hp != expected_hp:
        _v(
            out,
            where,
            f"max_hp: formula(level={c.level}, CON={c.stats.CON})={expected_hp}, got {c.max_hp}",
        )
    if c.max_mp != expected_mp:
        _v(
            out,
            where,
            f"max_mp: formula(level={c.level}, INT={c.stats.INT})={expected_mp}, got {c.max_mp}",
        )

    if c.hp > c.max_hp:
        _v(out, where, f"hp={c.hp} > max_hp={c.max_hp}")
    if c.mp > c.max_mp:
        _v(out, where, f"mp={c.mp} > max_mp={c.max_mp}")

    if c.alive and c.hp <= 0:
        _v(out, where, f"alive=True but hp={c.hp} (must be > 0)")
    if not c.alive and c.hp > 0:
        _v(out, where, f"alive=False but hp={c.hp} (must be 0)")

    seen_skill_ids: set[str] = set()
    for sid in c.known_skill_ids:
        if sid in seen_skill_ids:
            _v(out, where, f"skill id={sid!r} duplicated within character")
        seen_skill_ids.add(sid)

    seen_inv: set[str] = set()
    for iid in c.inventory_ids:
        if iid in seen_inv:
            _v(out, where, f"inventory_ids: {iid!r} duplicated")
        seen_inv.add(iid)

    for slot, item_id in c.equipment.equipped_items():
        if item_id not in c.inventory_ids:
            _v(out, where, f"equipment.{slot}={item_id!r} not in inventory_ids")

    if c.gold < 0:
        _v(out, where, f"gold={c.gold} (must be ≥ 0)")
    if c.xp_pool < 0:
        _v(out, where, f"xp_pool={c.xp_pool} (must be ≥ 0)")
    if c.revive_coins < 0:
        _v(out, where, f"revive_coins={c.revive_coins} (must be ≥ 0)")

    return out


def check_skills(c: Character, skills_pool: dict[str, Skill]) -> list[str]:
    where = f"characters/{c.id}"
    out: list[str] = []
    for sid in c.known_skill_ids:
        s = skills_pool.get(sid)
        if s is None:
            _v(out, where, f"skill_id={sid!r} not in skills pool")
            continue
        if s.level > c.level:
            _v(
                out,
                where,
                f"skill {s.id!r}.level={s.level} > character.level={c.level}",
            )
        if s.type in ("attack", "heal") and s.duration != 0:
            _v(
                out,
                where,
                f"skill {s.id!r}: type={s.type!r} requires duration=0, got {s.duration}",
            )
        if s.type in ("buff", "debuff") and s.duration <= 0:
            _v(
                out,
                where,
                f"skill {s.id!r}: type={s.type!r} requires duration>0, got {s.duration}",
            )
    return out


def check_seed_only_rules(c: Character) -> list[str]:
    """Extra rules at seed time only — relaxed for runtime state."""
    where = f"characters/{c.id}"
    out: list[str] = []

    # Full-pool start applies only to living NPCs. Seed corpses (alive=False —
    # quest backstory like "found dead in the cave") legitimately seed with
    # hp/mp=0; the alive↔hp consistency rule above (`check_character`) already
    # forces those zeros, so this line would otherwise contradict it.
    if c.alive:
        if c.hp != c.max_hp:
            _v(out, where, f"seed hp={c.hp} ≠ max_hp={c.max_hp} (must start at full)")
        if c.mp != c.max_mp:
            _v(out, where, f"seed mp={c.mp} ≠ max_mp={c.max_mp} (must start at full)")

    if not c.is_player:
        if c.level < 1:
            _v(out, where, f"NPC level={c.level} (must be ≥ 1)")
        skill_count = len(c.racial_skill_ids) + len(c.learned_skill_ids)
        if skill_count == 0:
            _v(
                out,
                where,
                "NPC has no skills (racial_skill_ids + learned_skill_ids empty)",
            )
        threshold = RULES.social.hostile_aggressive_threshold
        if c.combat_behavior is not None and c.disposition.aggressive < threshold:
            _v(
                out,
                where,
                f"combat_behavior set but disposition.aggressive={c.disposition.aggressive} < {threshold}",
            )
        if c.combat_behavior is None and c.disposition.aggressive >= threshold:
            _v(
                out,
                where,
                f"disposition.aggressive={c.disposition.aggressive} ≥ {threshold} but combat_behavior is None",
            )
        if c.combat_behavior is not None and c.xp_reward <= 0:
            _v(
                out,
                where,
                f"hostile NPC xp_reward={c.xp_reward} (must be > 0 — killing a hostile must reward xp)",
            )

    return out


def check_seed_character(
    c: Character,
    items_pool: dict[str, Item],
    skills_pool: dict[str, Skill],
) -> list[str]:
    """Per-character bundle for the story team's incremental build step.

    character (stateless) + inventory (cross-ref to items_pool) + skills
    (cross-ref to skills_pool) + seed-only extras (full HP/MP, NPC level >= 1,
    hostile NPC weapon, etc.)
    """
    from .item import check_inventory

    out: list[str] = []
    out.extend(check_character(c))
    out.extend(check_inventory(c, items_pool))
    out.extend(check_skills(c, skills_pool))
    out.extend(check_seed_only_rules(c))
    return out
