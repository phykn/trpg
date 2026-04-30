"""Game-rule invariants — one place, one entry point per scope.

Every check_X function returns list[str] — empty means OK, otherwise each
entry is a one-line violation message. The format is meant to be fed back
to the LLM verbatim as self-correction feedback:

    [<entity_kind>/<id>] <field>: <expected> vs <got>

Public API:
    check_stats(stats)              -> list[str]
    check_character(c)              -> list[str]
    check_seed_character(c, items)  -> list[str]
    check_item(item)                -> list[str]
    check_inventory(c, items_pool)  -> list[str]
    check_skills(c, skill_pool)     -> list[str]
    check_scenario(scenario)        -> list[str]
    check_quest_graph(scenario)     -> list[str]
    check_chapter_graph(scenario)   -> list[str]

    Scenario (dataclass)
    Scenario.from_dir(path)
    Scenario.from_state(state)

    InvariantViolation (ValueError subclass)
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, get_args

from ..domain.entities import (
    EQUIPMENT_SLOTS,
    Chapter,
    Character,
    Item,
    Location,
    Quest,
    Race,
    Skill,
    Stats,
    WeaponEffect,
    ArmorEffect,
    ConsumableEffect,
    allowed_slots,
)
from ..domain.types import StatKey
from ..rules import RULES
from .combat import DICE_RE
from .growth import calc_max_hp, calc_max_mp
from .inventory.carry import carry_capacity, current_weight


class InvariantViolation(ValueError):
    """Single error type. Callers wanting raise semantics:

        violations = check_character(c)
        if violations:
            raise InvariantViolation('\\n'.join(violations))
    """


_STAT_KEYS: tuple[str, ...] = get_args(StatKey)


def _slot_mismatch_hint(allowed: tuple[str, ...]) -> str:
    if not allowed:
        return "consumable, cannot be equipped"
    if allowed == ("weapon",):
        return "weapon, must be in the weapon slot"
    if "armor" in allowed and "accessory" in allowed:
        return "defense item, must be in the armor or accessory slot"
    return "decorative, must be in the accessory slot"


# --- Scenario container ----------------------------------------------------


@dataclass
class Scenario:
    """Seed bundle (or runtime state projection) — every entity dict + meta.

    runtime=True relaxes seed-only rules (hp == max_hp, NPC level >= 1, etc.)
    so check_state can reuse the same machinery.
    """

    races: dict[str, Race] = field(default_factory=dict)
    locations: dict[str, Location] = field(default_factory=dict)
    items: dict[str, Item] = field(default_factory=dict)
    skills: dict[str, Skill] = field(default_factory=dict)
    characters: dict[str, Character] = field(default_factory=dict)
    quests: dict[str, Quest] = field(default_factory=dict)
    chapters: dict[str, Chapter] = field(default_factory=dict)
    start: dict = field(default_factory=dict)
    player_template: dict = field(default_factory=dict)
    runtime: bool = False

    @classmethod
    def from_dir(cls, scenario_dir: str | Path) -> "Scenario":
        d = Path(scenario_dir)

        def _load(sub: str, model: type) -> dict:
            sub_dir = d / sub
            if not sub_dir.is_dir():
                return {}
            out: dict[str, Any] = {}
            for f in sorted(sub_dir.glob("*.json")):
                obj = model.model_validate_json(f.read_text(encoding="utf-8"))
                out[obj.id] = obj
            return out

        def _read_json(name: str) -> dict:
            p = d / name
            if not p.is_file():
                return {}
            return json.loads(p.read_text(encoding="utf-8"))

        return cls(
            races=_load("races", Race),
            locations=_load("locations", Location),
            items=_load("items", Item),
            skills=_load("skills", Skill),
            characters=_load("characters", Character),
            quests=_load("quests", Quest),
            chapters=_load("chapters", Chapter),
            start=_read_json("start.json"),
            player_template=_read_json("player_template.json"),
            runtime=False,
        )

    @classmethod
    def from_state(cls, state: Any) -> "Scenario":
        player = state.characters.get(state.player_id)
        return cls(
            races=dict(state.races),
            locations=dict(state.locations),
            items=dict(state.items),
            skills=dict(state.skills),
            characters=dict(state.characters),
            quests=dict(state.quests),
            chapters=dict(state.chapters),
            start={
                "start_location_id": player.location_id if player else None,
                "active_subject_id": state.active_subject_id,
                "active_quest_id": state.active_quest_id,
            },
            player_template={},
            runtime=True,
        )


# --- helpers ---------------------------------------------------------------


def _v(out: list[str], where: str, msg: str) -> None:
    out.append(f"[{where}] {msg}")


# --- check_stats -----------------------------------------------------------


def check_stats(stats: Stats) -> list[str]:
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


# --- check_character (stateless) -------------------------------------------


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


# --- check_skills (skill ↔ type ↔ duration) --------------------------------


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


# --- check_item ------------------------------------------------------------


def check_item(item: Item) -> list[str]:
    where = f"items/{item.id}"
    out: list[str] = []
    if item.weight < 0:
        _v(out, where, f"weight={item.weight} (must be ≥ 0)")
    if item.price < 0:
        _v(out, where, f"price={item.price} (must be ≥ 0)")
    eff = item.effects
    if isinstance(eff, WeaponEffect):
        if not DICE_RE.match(eff.weapon_dice):
            _v(
                out,
                where,
                f"effects.weapon_dice={eff.weapon_dice!r} (must match '<int>d<int>(+/-<int>)?')",
            )
    elif isinstance(eff, ArmorEffect):
        if eff.defense < 0:
            _v(out, where, f"effects.defense={eff.defense} (must be ≥ 0)")
    elif isinstance(eff, ConsumableEffect):
        if eff.amount < 0:
            _v(out, where, f"effects.amount={eff.amount} (must be ≥ 0)")
        if eff.duration is not None and eff.duration < 0:
            _v(
                out,
                where,
                f"effects.duration={eff.duration} (must be ≥ 0 or null)",
            )
    return out


# --- check_inventory (character ↔ items pool) ------------------------------


def check_inventory(c: Character, items: dict[str, Item]) -> list[str]:
    where = f"characters/{c.id}"
    out: list[str] = []

    for iid in c.inventory_ids:
        if iid not in items:
            _v(out, where, f"inventory_ids: {iid!r} not in items pool")

    for slot, item_id in c.equipment.equipped_items():
        if item_id not in items:
            _v(out, where, f"equipment.{slot}={item_id!r} not in items pool")
            continue
        item = items[item_id]
        allowed = allowed_slots(item)
        if slot not in allowed:
            _v(out, where, f"equipment.{slot}={item_id!r} is {_slot_mismatch_hint(allowed)}")

        req = item.required
        if req is not None:
            for k in _STAT_KEYS:
                need = getattr(req, k)
                have = getattr(c.stats, k)
                if have < need:
                    _v(
                        out,
                        where,
                        f"equipment.{slot}={item_id!r} requires {k}≥{need}, character has {k}={have}",
                    )

    cap = carry_capacity(c)
    total = current_weight(c, items)
    if total > cap:
        _v(
            out,
            where,
            f"inventory weight {total:.1f} > carry capacity {cap:.1f} (STR×{RULES.carry.weight_per_strength})",
        )

    return out


# --- seed-only character extras --------------------------------------------


def _check_seed_only_rules(c: Character, items: dict[str, Item]) -> list[str]:
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
            _v(out, where, "NPC has no skills (racial_skill_ids + learned_skill_ids empty)")
        if c.combat_behavior is not None and c.disposition.aggressive < 70:
            _v(
                out,
                where,
                f"combat_behavior set but disposition.aggressive={c.disposition.aggressive} < 70",
            )
        if c.combat_behavior is None and c.disposition.aggressive >= 70:
            _v(
                out,
                where,
                f"disposition.aggressive={c.disposition.aggressive} ≥ 70 but combat_behavior is None",
            )
        if c.combat_behavior is not None and c.xp_reward <= 0:
            _v(
                out,
                where,
                f"hostile NPC xp_reward={c.xp_reward} (must be > 0 — killing a hostile must reward xp)",
            )

    return out


# --- check_quest_graph -----------------------------------------------------


_TRIGGER_POOL_NAME = {
    "character_death": "characters",
    "location_enter": "locations",
    "item_use": "items",
}


def _check_prereq_status(items: dict, where_prefix: str) -> list[str]:
    """Active items must have all prerequisites completed."""
    out: list[str] = []
    for iid, item in items.items():
        if item.status != "active":
            continue
        for pid in item.prerequisite_ids:
            if pid in items and items[pid].status != "completed":
                _v(
                    out,
                    f"{where_prefix}/{iid}",
                    f"status='active' but prerequisite {pid!r} status='{items[pid].status}' (must be 'completed')",
                )
    return out


def _check_prereq_cycles(items: dict, kind_label: str) -> list[str]:
    """Reject any cycle in the prerequisite_ids DAG."""
    visited: set[str] = set()
    on_stack: set[str] = set()
    cycle_path: list[str] = []

    def _dfs(iid: str, path: list[str]) -> bool:
        if iid in on_stack:
            cycle_path.extend(path[path.index(iid):] + [iid])
            return True
        if iid in visited:
            return False
        visited.add(iid)
        on_stack.add(iid)
        path.append(iid)
        item = items.get(iid)
        if item is not None:
            for pid in item.prerequisite_ids:
                if _dfs(pid, path):
                    return True
        on_stack.remove(iid)
        path.pop()
        return False

    out: list[str] = []
    for iid in items:
        if iid in visited:
            continue
        if _dfs(iid, []):
            _v(
                out,
                "scenario",
                f"{kind_label} prerequisite cycle: {' → '.join(cycle_path)}",
            )
            break
    return out


def check_quest_graph(s: Scenario) -> list[str]:
    return (
        _check_prereq_status(s.quests, "quests")
        + _check_prereq_cycles(s.quests, "quest")
    )


def check_chapter_graph(s: Scenario) -> list[str]:
    return (
        _check_prereq_status(s.chapters, "chapters")
        + _check_prereq_cycles(s.chapters, "chapter")
    )


# --- per-entity cross-ref helpers (used by scenario / state) ---------------


def _check_character_cross_ref(c: Character, s: Scenario) -> list[str]:
    where = f"characters/{c.id}"
    out: list[str] = []
    if c.race_id not in s.races:
        _v(out, where, f"race_id={c.race_id!r} not in races")
    if c.location_id is not None and c.location_id not in s.locations:
        _v(out, where, f"location_id={c.location_id!r} not in locations")
    return out


def _check_location_cross_ref(loc: Location, s: Scenario) -> list[str]:
    where = f"locations/{loc.id}"
    out: list[str] = []
    for conn in loc.connections:
        if conn.target_id == loc.id:
            _v(out, where, f"connections.target_id={conn.target_id!r} points to self")
        if conn.target_id not in s.locations:
            _v(
                out,
                where,
                f"connections.target_id={conn.target_id!r} not in locations",
            )
        if conn.key_item_id is not None and conn.key_item_id not in s.items:
            _v(
                out,
                where,
                f"connections.key_item_id={conn.key_item_id!r} not in items",
            )
    for conn in loc.hidden_connections:
        if conn.target_id not in s.locations:
            _v(
                out,
                where,
                f"hidden_connections.target_id={conn.target_id!r} not in locations",
            )
        if conn.key_item_id is not None and conn.key_item_id not in s.items:
            _v(
                out,
                where,
                f"hidden_connections.key_item_id={conn.key_item_id!r} not in items",
            )
    for iid in loc.item_ids:
        if iid not in s.items:
            _v(out, where, f"item_ids: {iid!r} not in items")
    for iid in loc.hidden_items:
        if iid not in s.items:
            _v(out, where, f"hidden_items: {iid!r} not in items")
    for cid in loc.sleep_encounters:
        if cid not in s.characters:
            _v(out, where, f"sleep_encounters: {cid!r} not in characters")
    return out


def _check_quest_cross_ref(q: Quest, s: Scenario) -> list[str]:
    where = f"quests/{q.id}"
    out: list[str] = []
    if q.giver_id not in s.characters:
        _v(out, where, f"giver_id={q.giver_id!r} not in characters")
    seen_trigger_ids: set[str] = set()
    pools = {
        "characters": s.characters,
        "locations": s.locations,
        "items": s.items,
    }
    for t in (*q.triggers, *q.fail_triggers):
        if t.id in seen_trigger_ids:
            _v(out, where, f"trigger id {t.id!r} duplicated within quest")
        seen_trigger_ids.add(t.id)
        pool_name = _TRIGGER_POOL_NAME.get(t.type)
        if pool_name is None:
            _v(
                out,
                where,
                f"trigger {t.id!r} type={t.type!r} unknown (allowed: character_death/location_enter/item_use)",
            )
            continue
        if t.target_id not in pools[pool_name]:
            _v(
                out,
                where,
                f"trigger {t.id!r} target_id={t.target_id!r} not in {pool_name}",
            )
    for pid in q.prerequisite_ids:
        if pid not in s.quests:
            _v(out, where, f"prerequisite_ids: {pid!r} not in quests")
    for iid in q.rewards.items:
        if iid not in s.items:
            _v(out, where, f"rewards.items: {iid!r} not in items")
    return out


def _check_chapter_cross_ref(ch: Chapter, s: Scenario) -> list[str]:
    where = f"chapters/{ch.id}"
    out: list[str] = []
    seen_qid: set[str] = set()
    for qid in ch.quest_ids:
        if qid in seen_qid:
            _v(out, where, f"quest_ids: {qid!r} duplicated")
        seen_qid.add(qid)
        if qid not in s.quests:
            _v(out, where, f"quest_ids: {qid!r} not in quests")
    seen_pid: set[str] = set()
    for pid in ch.prerequisite_ids:
        if pid == ch.id:
            _v(out, where, f"prerequisite_ids: {pid!r} points to self")
        if pid in seen_pid:
            _v(out, where, f"prerequisite_ids: {pid!r} duplicated")
        seen_pid.add(pid)
        if pid not in s.chapters:
            _v(out, where, f"prerequisite_ids: {pid!r} not in chapters")
    return out


# --- start.json + player_template (seed-only) ------------------------------


def _check_start_json(s: Scenario) -> list[str]:
    where = "scenario/start"
    out: list[str] = []
    sl = s.start.get("start_location_id")
    ss = s.start.get("active_subject_id")
    sq = s.start.get("active_quest_id")

    if sl is not None and sl not in s.locations:
        _v(out, where, f"start_location_id={sl!r} not in locations")

    if ss is not None:
        if ss not in s.characters:
            _v(out, where, f"active_subject_id={ss!r} not in characters")
        else:
            subj = s.characters[ss]
            if not subj.alive:
                _v(out, where, f"active_subject_id={ss!r} alive=False (must be alive)")
            if sl is not None and subj.location_id != sl:
                _v(
                    out,
                    where,
                    f"active_subject_id={ss!r} location_id={subj.location_id!r} ≠ start_location_id={sl!r}",
                )

    if sq is not None:
        if sq not in s.quests:
            _v(out, where, f"active_quest_id={sq!r} not in quests")
        elif s.quests[sq].status != "active":
            _v(
                out,
                where,
                f"active_quest_id={sq!r} status='{s.quests[sq].status}' (must be 'active')",
            )

    return out


def _check_player_template(s: Scenario) -> list[str]:
    where = "scenario/player_template"
    out: list[str] = []
    pt_inv = s.player_template.get("inventory_ids", []) or []
    seen: set[str] = set()
    for iid in pt_inv:
        if iid in seen:
            _v(out, where, f"inventory_ids: {iid!r} duplicated")
        seen.add(iid)
        if iid not in s.items:
            _v(out, where, f"inventory_ids: {iid!r} not in items")

    pt_eq = s.player_template.get("equipment", {}) or {}
    for slot, item_id in pt_eq.items():
        if item_id is None:
            continue
        if slot not in EQUIPMENT_SLOTS:
            _v(out, where, f"equipment.{slot}: unknown slot")
            continue
        if item_id not in s.items:
            _v(out, where, f"equipment.{slot}={item_id!r} not in items")
            continue
        item = s.items[item_id]
        allowed = allowed_slots(item)
        if slot not in allowed:
            _v(out, where, f"equipment.{slot}={item_id!r} is {_slot_mismatch_hint(allowed)}")
        if item_id not in pt_inv:
            _v(out, where, f"equipment.{slot}={item_id!r} not in inventory_ids")
    return out


# --- check_scenario --------------------------------------------------------


def check_scenario(s: Scenario) -> list[str]:
    out: list[str] = []

    for item in s.items.values():
        out.extend(check_item(item))

    for c in s.characters.values():
        out.extend(check_character(c))
        out.extend(check_inventory(c, s.items))
        out.extend(check_skills(c, s.skills))
        out.extend(_check_character_cross_ref(c, s))
        if not s.runtime:
            out.extend(_check_seed_only_rules(c, s.items))

    for r in s.races.values():
        for sid in r.racial_skill_ids:
            if sid not in s.skills:
                _v(out, f"races/{r.id}", f"racial_skill_id={sid!r} not in skills pool")

    for loc in s.locations.values():
        out.extend(_check_location_cross_ref(loc, s))

    for q in s.quests.values():
        out.extend(_check_quest_cross_ref(q, s))

    for ch in s.chapters.values():
        out.extend(_check_chapter_cross_ref(ch, s))

    out.extend(check_quest_graph(s))
    out.extend(check_chapter_graph(s))

    if not s.runtime:
        out.extend(_check_start_json(s))
        out.extend(_check_player_template(s))

    return out


# --- public namespace ------------------------------------------------------


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
    out: list[str] = []
    out.extend(check_character(c))
    out.extend(check_inventory(c, items_pool))
    out.extend(check_skills(c, skills_pool))
    out.extend(_check_seed_only_rules(c, items_pool))
    return out


