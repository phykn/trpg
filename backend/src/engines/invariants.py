"""Game-rule invariants — one place, one entry point per scope.

Every check.X function returns list[str] — empty means OK, otherwise each
entry is a one-line violation message. The format is meant to be fed back
to the LLM verbatim as self-correction feedback:

    [<entity_kind>/<id>] <field>: <expected> vs <got>

Public API (everything else is private):
    check.stats(stats)              -> list[str]
    check.character(c)              -> list[str]
    check.item(item)                -> list[str]
    check.inventory(c, items_pool)  -> list[str]
    check.skills(c)                 -> list[str]
    check.scenario(scenario)        -> list[str]
    check.state(state)              -> list[str]
    check.quest_graph(scenario)     -> list[str]

    Scenario (dataclass)
    Scenario.from_dir(path)
    Scenario.from_state(state)

    InvariantViolation (ValueError subclass)
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from ..domain.entities import (
    ArmorEffect,
    Chapter,
    Character,
    ConsumableEffect,
    Item,
    Location,
    Quest,
    Race,
    Stats,
    WeaponEffect,
    slot_kind,
)
from ..rules import RULES
from .growth import calc_max_hp, calc_max_mp


class InvariantViolation(ValueError):
    """Single error type. Callers wanting raise semantics:

        violations = check.character(c)
        if violations:
            raise InvariantViolation('\\n'.join(violations))
    """


_DICE_RE = re.compile(r"^\s*\d+d\d+\s*([+-]\s*\d+)?\s*$")
_STAT_KEYS = ("STR", "DEX", "CON", "INT", "WIS", "CHA")


# --- Scenario container ----------------------------------------------------


@dataclass
class Scenario:
    """Seed bundle (or runtime state projection) — every entity dict + meta.

    runtime=True relaxes seed-only rules (hp == max_hp, NPC level >= 1, etc.)
    so check.state can reuse the same machinery.
    """

    races: dict[str, Race] = field(default_factory=dict)
    locations: dict[str, Location] = field(default_factory=dict)
    items: dict[str, Item] = field(default_factory=dict)
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
            characters=dict(state.characters),
            quests=dict(state.quests),
            chapters=dict(state.chapters),
            start={
                "start_location_id": player.location_id if player else None,
                "active_subject_id": state.active_subject_id,
                "active_quest_id": state.active_quest_id,
                "world_time": state.world_time,
            },
            player_template={},
            runtime=True,
        )


# --- helpers ---------------------------------------------------------------


def _v(out: list[str], where: str, msg: str) -> None:
    out.append(f"[{where}] {msg}")


# --- check.stats -----------------------------------------------------------


def _check_stats(stats: Stats) -> list[str]:
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


# --- check.character (stateless) -------------------------------------------


def _check_character(c: Character) -> list[str]:
    """Stateless rules — no items pool / scenario context needed."""
    where = f"characters/{c.id}"
    out: list[str] = []

    for v in _check_stats(c.stats):
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
    for s in (*c.racial_skills, *c.learned_skills):
        if s.id in seen_skill_ids:
            _v(out, where, f"skill id={s.id!r} duplicated within character")
        seen_skill_ids.add(s.id)
        if s.level > c.level:
            _v(
                out,
                where,
                f"skill {s.id!r}.level={s.level} > character.level={c.level}",
            )

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


# --- check.skills (skill ↔ type ↔ duration) --------------------------------


def _check_skills(c: Character) -> list[str]:
    where = f"characters/{c.id}"
    out: list[str] = []
    for s in (*c.racial_skills, *c.learned_skills):
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


# --- check.item ------------------------------------------------------------


def _check_item(item: Item) -> list[str]:
    where = f"items/{item.id}"
    out: list[str] = []
    if item.weight < 0:
        _v(out, where, f"weight={item.weight} (must be ≥ 0)")
    if item.price < 0:
        _v(out, where, f"price={item.price} (must be ≥ 0)")
    eff = item.effects
    if isinstance(eff, WeaponEffect):
        if not _DICE_RE.match(eff.weapon_dice):
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


# --- check.inventory (character ↔ items pool) ------------------------------


def _check_inventory(c: Character, items: dict[str, Item]) -> list[str]:
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
        eff = item.effects
        kind = slot_kind(slot)
        if isinstance(eff, WeaponEffect):
            if kind != "hand":
                _v(
                    out,
                    where,
                    f"equipment.{slot}={item_id!r} is weapon, must be in leftHand or rightHand",
                )
        elif isinstance(eff, ArmorEffect):
            if kind != "armor":
                _v(
                    out,
                    where,
                    f"equipment.{slot}={item_id!r} is armor, must be in head/top/bottom/feet",
                )
        elif isinstance(eff, ConsumableEffect):
            _v(
                out,
                where,
                f"equipment.{slot}={item_id!r} is consumable, cannot be equipped",
            )
        elif eff is None and kind != "acc":
            _v(
                out,
                where,
                f"equipment.{slot}={item_id!r} is decorative (no effect), must be in acc1/acc2",
            )

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

    lh = c.equipment.leftHand
    rh = c.equipment.rightHand
    for slot_id in (lh, rh):
        if slot_id is None or slot_id not in items:
            continue
        eff = items[slot_id].effects
        if isinstance(eff, WeaponEffect) and eff.two_handed and lh != rh:
            _v(
                out,
                where,
                f"equipment: two-handed weapon {slot_id!r} requires leftHand=rightHand, got leftHand={lh!r} rightHand={rh!r}",
            )
            break

    cap = RULES.carry.weight_per_strength * c.stats.STR
    total = sum(items[i].weight for i in c.inventory_ids if i in items)
    if total > cap:
        _v(
            out,
            where,
            f"inventory weight {total:.1f} > carry capacity {cap:.1f} (STR×{RULES.carry.weight_per_strength})",
        )

    return out


# --- seed-only character extras --------------------------------------------


def _check_seed_character_extras(c: Character, items: dict[str, Item]) -> list[str]:
    """Extra rules at seed time only — relaxed for runtime state."""
    where = f"characters/{c.id}"
    out: list[str] = []

    if c.hp != c.max_hp:
        _v(out, where, f"seed hp={c.hp} ≠ max_hp={c.max_hp} (must start at full)")
    if c.mp != c.max_mp:
        _v(out, where, f"seed mp={c.mp} ≠ max_mp={c.max_mp} (must start at full)")

    if not c.is_player:
        if c.level < 1:
            _v(out, where, f"NPC level={c.level} (must be ≥ 1)")
        skill_count = len(c.racial_skills) + len(c.learned_skills)
        if skill_count == 0:
            _v(out, where, "NPC has no skills (racial_skills + learned_skills empty)")
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

    return out


# --- check.quest_graph -----------------------------------------------------


_TRIGGER_POOL_NAME = {
    "character_death": "characters",
    "location_enter": "locations",
    "item_use": "items",
}


def _check_quest_graph(s: Scenario) -> list[str]:
    out: list[str] = []

    for qid, q in s.quests.items():
        where = f"quests/{qid}"
        if q.status == "active":
            for pid in q.prerequisite_ids:
                if pid in s.quests and s.quests[pid].status != "completed":
                    _v(
                        out,
                        where,
                        f"status='active' but prerequisite {pid!r} status='{s.quests[pid].status}' (must be 'completed')",
                    )

    visited: set[str] = set()
    on_stack: set[str] = set()
    cycle_path: list[str] = []

    def _dfs(qid: str, path: list[str]) -> bool:
        if qid in on_stack:
            cycle_path.extend(path[path.index(qid):] + [qid])
            return True
        if qid in visited:
            return False
        visited.add(qid)
        on_stack.add(qid)
        path.append(qid)
        q = s.quests.get(qid)
        if q is not None:
            for pid in q.prerequisite_ids:
                if _dfs(pid, path):
                    return True
        on_stack.remove(qid)
        path.pop()
        return False

    for qid in s.quests:
        if qid in visited:
            continue
        if _dfs(qid, []):
            _v(
                out,
                "scenario",
                f"quest prerequisite cycle: {' → '.join(cycle_path)}",
            )
            break

    return out


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
    return out


# --- start.json + player_template (seed-only) ------------------------------


def _check_start_json(s: Scenario) -> list[str]:
    where = "scenario/start"
    out: list[str] = []
    sl = s.start.get("start_location_id")
    ss = s.start.get("active_subject_id")
    sq = s.start.get("active_quest_id")
    wt = s.start.get("world_time")

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

    if isinstance(wt, str):
        try:
            datetime.fromisoformat(wt)
        except ValueError:
            _v(out, where, f"world_time={wt!r} not a valid ISO 8601 datetime")

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
        if item_id not in s.items:
            _v(out, where, f"equipment.{slot}={item_id!r} not in items")
            continue
        eff = s.items[item_id].effects
        kind = slot_kind(slot)
        if kind is None:
            _v(out, where, f"equipment.{slot}: unknown slot")
            continue
        if isinstance(eff, WeaponEffect) and kind != "hand":
            _v(
                out,
                where,
                f"equipment.{slot}={item_id!r} is weapon, must be in leftHand/rightHand",
            )
        elif isinstance(eff, ArmorEffect) and kind != "armor":
            _v(
                out,
                where,
                f"equipment.{slot}={item_id!r} is armor, must be in head/top/bottom/feet",
            )
        elif isinstance(eff, ConsumableEffect):
            _v(out, where, f"equipment.{slot}={item_id!r} is consumable, cannot be equipped")
        elif eff is None and kind != "acc":
            _v(out, where, f"equipment.{slot}={item_id!r} is decorative, must be in acc1/acc2")
        if item_id not in pt_inv:
            _v(out, where, f"equipment.{slot}={item_id!r} not in inventory_ids")
    return out


# --- check.scenario / check.state ------------------------------------------


def _check_scenario(s: Scenario) -> list[str]:
    out: list[str] = []

    for item in s.items.values():
        out.extend(_check_item(item))

    for c in s.characters.values():
        out.extend(_check_character(c))
        out.extend(_check_inventory(c, s.items))
        out.extend(_check_skills(c))
        out.extend(_check_character_cross_ref(c, s))
        if not s.runtime:
            out.extend(_check_seed_character_extras(c, s.items))

    for loc in s.locations.values():
        out.extend(_check_location_cross_ref(loc, s))

    for q in s.quests.values():
        out.extend(_check_quest_cross_ref(q, s))

    for ch in s.chapters.values():
        out.extend(_check_chapter_cross_ref(ch, s))

    out.extend(_check_quest_graph(s))

    if not s.runtime:
        out.extend(_check_start_json(s))
        out.extend(_check_player_template(s))

    return out


def _check_state(state: Any) -> list[str]:
    return _check_scenario(Scenario.from_state(state))


# --- public dispatcher -----------------------------------------------------


def check(*_args: Any, **_kwargs: Any) -> list[str]:
    """Use the explicit form: check.character / check.scenario / etc."""
    raise TypeError(
        "Call check.character / check.item / check.inventory / check.skills / "
        "check.scenario / check.state / check.quest_graph / check.stats explicitly."
    )


def _check_seed_character(c: Character, items_pool: dict[str, Item]) -> list[str]:
    """Per-character bundle for the story team's incremental build step.

    character (stateless) + inventory (cross-ref to items_pool) + skills +
    seed-only extras (full HP/MP, NPC level >= 1, hostile NPC weapon, etc.)
    """
    out: list[str] = []
    out.extend(_check_character(c))
    out.extend(_check_inventory(c, items_pool))
    out.extend(_check_skills(c))
    out.extend(_check_seed_character_extras(c, items_pool))
    return out


check.stats = _check_stats              # type: ignore[attr-defined]
check.character = _check_character      # type: ignore[attr-defined]
check.seed_character = _check_seed_character  # type: ignore[attr-defined]
check.item = _check_item                # type: ignore[attr-defined]
check.inventory = _check_inventory      # type: ignore[attr-defined]
check.skills = _check_skills            # type: ignore[attr-defined]
check.scenario = _check_scenario        # type: ignore[attr-defined]
check.state = _check_state              # type: ignore[attr-defined]
check.quest_graph = _check_quest_graph  # type: ignore[attr-defined]
