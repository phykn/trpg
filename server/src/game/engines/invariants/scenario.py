"""Scenario-level invariant checks (quests, chapters, cross-refs, start/template)."""

from __future__ import annotations

from ...domain.entities import (
    EQUIPMENT_SLOTS,
    Chapter,
    Location,
    Quest,
    allowed_slots,
)
from .base import Scenario, _v, _slot_mismatch_hint


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
            cycle_path.extend(path[path.index(iid) :] + [iid])
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
    return _check_prereq_status(s.quests, "quests") + _check_prereq_cycles(
        s.quests, "quest"
    )


def check_chapter_graph(s: Scenario) -> list[str]:
    return _check_prereq_status(s.chapters, "chapters") + _check_prereq_cycles(
        s.chapters, "chapter"
    )


def _check_character_cross_ref(c, s: Scenario) -> list[str]:
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
            _v(
                out,
                where,
                f"equipment.{slot}={item_id!r} is {_slot_mismatch_hint(allowed)}",
            )
        if item_id not in pt_inv:
            _v(out, where, f"equipment.{slot}={item_id!r} not in inventory_ids")
    return out


def check_scenario(s: Scenario) -> list[str]:
    from .character import check_character, check_skills, check_seed_only_rules
    from .item import check_item, check_inventory

    out: list[str] = []

    for item in s.items.values():
        out.extend(check_item(item))

    for c in s.characters.values():
        out.extend(check_character(c))
        out.extend(check_inventory(c, s.items))
        out.extend(check_skills(c, s.skills))
        out.extend(_check_character_cross_ref(c, s))
        if not s.runtime:
            out.extend(check_seed_only_rules(c))

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
