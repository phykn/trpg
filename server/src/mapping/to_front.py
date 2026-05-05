"""FrontState builder — `to_front_state(state)` returns the flat dict the
client renders. Korean dates, durations, composed strings, and conditional
labels are all built here. Story graph projection lives in
`story_graph.py`; shared label helpers live in `labels.py`."""

from collections import Counter

from ..domain.clock import day_phase
from ..domain.entities import EQUIPMENT_SLOTS, Location, Quest
from ..domain.memory import PendingCheck
from ..domain.state import GameState
from ..locale import render
from ..engines.growth import can_afford_level_up, xp_for_next_level
from ..ontology.graph import GameGraph
from ..ontology.queries import (
    companions_of,
    connections_of,
    equipment_of,
    inhabitants_of,
    inventory_of,
    known_skills_of,
)
from ..rules import RULES
from .labels import (
    difficulty_badge,
    gender_label,
    giver_with_location_label,
    race_job_label,
    risk_payload,
    stat_label,
    stats_payload,
)
from .story_graph import to_story_graph


__all__ = [
    "stat_label",
    "to_hero",
    "to_subject",
    "to_quest",
    "to_place",
    "to_combat",
    "pending_check_to_front",
    "to_front_state",
]


def _equipment(state: GameState, graph: GameGraph, char_id: str) -> dict:
    out: dict[str, dict | None] = {slot: None for slot in EQUIPMENT_SLOTS}
    for edge in equipment_of(graph, char_id):
        slot = (edge.attrs or {}).get("slot")
        if slot is None or slot not in out:
            continue
        item = state.items.get(edge.to_id)
        if item is None:
            continue
        out[slot] = {"name": item.name}
    return out


def _inventory(state: GameState, graph: GameGraph, char_id: str) -> list[dict]:
    """Inventory shown to the player, with currently-equipped items subtracted.
    Invariant: each equipped item_id is also present in inventory_ids — so we
    decrement once per equipped slot to avoid duplicate display."""
    counts: Counter[str] = Counter(inventory_of(graph, char_id))
    for edge in equipment_of(graph, char_id):
        item_id = edge.to_id
        counts[item_id] -= 1
        if counts[item_id] <= 0:
            del counts[item_id]
    return [
        {"name": state.items[item_id].name, "qty": qty}
        for item_id, qty in counts.items()
        if item_id in state.items
    ]


def _companion_label(state: GameState, graph: GameGraph, char_id: str) -> str | None:
    """Returns the Korean label for a companion or None if the id no longer
    resolves (e.g. the companion died and was removed). Caller filters None
    so a stray technical id never reaches the UI."""
    if char_id not in state.characters:
        return None
    c = state.characters[char_id]
    return f"{c.name} ({race_job_label(state, graph, c)})"


def _skill_names(state: GameState, graph: GameGraph, char_id: str) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for edge in known_skills_of(graph, char_id):
        sid = edge.to_id
        if sid in seen:
            continue
        skill = state.skills.get(sid)
        if skill is None:
            continue
        seen.add(sid)
        out.append(skill.name)
    return out


def to_hero(state: GameState, graph: GameGraph | None = None) -> dict:
    if graph is None:
        graph = state.graph()
    p = state.characters[state.player_id]
    skills = _skill_names(state, graph, p.id)
    inventory = _inventory(state, graph, p.id)
    inventory = [{"name": f"금화({p.gold})", "qty": 1}, *inventory]
    return {
        "name": p.name,
        "alive": p.alive,
        "raceJob": race_job_label(state, graph, p),
        "gender": gender_label(p),
        "level": p.level,
        "exp": p.xp_pool,
        "expMax": xp_for_next_level(p.level),
        "canLevelUp": can_afford_level_up(p),
        "hp": p.hp,
        "hpMax": p.max_hp,
        "mp": p.mp,
        "mpMax": p.max_mp,
        "reviveCoins": p.revive_coins,
        "reviveCoinsMax": RULES.death.revive_coins,
        "gold": p.gold,
        "stats": stats_payload(p.stats),
        "equipment": _equipment(state, graph, p.id),
        "inventory": inventory,
        "status": list(p.status),
        "skills": skills,
        "companions": [
            label
            for cid in companions_of(graph, p.id)
            if (label := _companion_label(state, graph, cid)) is not None
        ],
    }


def to_subject(state: GameState, graph: GameGraph | None = None) -> dict | None:
    if graph is None:
        graph = state.graph()
    if state.active_subject_id is None:
        return None
    sid = state.active_subject_id
    if sid not in state.characters:
        return None
    s = state.characters[sid]
    player = state.characters[state.player_id]
    known = [s.appearance] if s.appearance and s.alive else []
    known += list(s.hints)
    known += [m.content for m in player.memories if m.target_id == sid]
    skills = _skill_names(state, graph, s.id)
    inventory = _inventory(state, graph, s.id)
    inventory = [{"name": f"금화({s.gold})", "qty": 1}, *inventory]
    return {
        "name": s.name,
        "alive": s.alive,
        "role": s.role,
        "raceJob": race_job_label(state, graph, s),
        "gender": gender_label(s),
        "trust": s.relations.get(state.player_id, 0),
        "known": known,
        "level": s.level,
        "hp": s.hp,
        "hpMax": s.max_hp,
        "stats": stats_payload(s.stats),
        "equipment": _equipment(state, graph, s.id),
        "inventory": inventory,
        "skills": skills,
    }


def to_quest(state: GameState, graph: GameGraph | None = None) -> dict | None:
    if graph is None:
        graph = state.graph()
    if state.active_quest_id is None:
        return None
    qid = state.active_quest_id
    if qid not in state.quests:
        return None
    q: Quest = state.quests[qid]
    giver_name = giver_with_location_label(state, graph, qid) or qid
    # quest.triggers' display name is a per-trigger label — that's an
    # entity attribute on the trigger object (no relational scan), so read
    # the goals straight from the trigger names.
    goals = [t.name for t in q.triggers]
    # triggers_met is a parallel bool array; engine ensures aligned length on
    # accept. Tolerate misalignment defensively (treat missing slots as unmet).
    total = len(q.triggers)
    done = sum(1 for met in q.triggers_met[:total] if met)
    if total == 0:
        progress_label = ""
    elif done >= total:
        progress_label = "✓"
    else:
        progress_label = f"{done}/{total}"
    actions: list[str] = []
    if q.status == "pending":
        actions.append("accept")
    elif q.status == "active":
        actions.append("abandon")
    return {
        "id": qid,
        "title": q.title,
        "summary": q.summary,
        "giver": giver_name,
        "difficulty": difficulty_badge(q.difficulty),
        "goals": goals,
        "progressLabel": progress_label,
        "conditions": list(q.conditions),
        "rewards": {"gold": q.rewards.gold, "exp": q.rewards.exp},
        "status": q.status,
        "actions": actions,
    }


def to_place(state: GameState, graph: GameGraph | None = None) -> dict | None:
    if graph is None:
        graph = state.graph()
    p = state.characters[state.player_id]
    player_loc_id = p.location_id
    if player_loc_id is None or player_loc_id not in state.locations:
        return None
    loc: Location = state.locations[player_loc_id]
    surroundings = []
    for edge in connections_of(graph, player_loc_id):
        target_id = edge.to_id
        target = state.locations.get(target_id)
        if target is None:
            continue
        attrs = edge.attrs or {}
        surroundings.append(
            {
                "name": target.name,
                "blurb": target.description,
                "difficulty": render(f"tier.{d}", "ko") if (d := attrs.get("difficulty")) else None,
                "risk": risk_payload(target.sleep_risk),
            }
        )
    targets = []
    for cid in inhabitants_of(graph, player_loc_id):
        if cid == state.player_id:
            continue
        c = state.characters.get(cid)
        if c is None:
            continue
        blurb = "죽음" if not c.alive else (c.appearance or c.description)
        targets.append(
            {
                "name": c.name,
                "level": c.level,
                "raceJob": race_job_label(state, graph, c),
                "gender": gender_label(c),
                "blurb": blurb,
                "trust": c.relations.get(state.player_id, 0),
            }
        )
    return {
        "name": loc.name,
        "description": loc.description,
        "dayPhase": render(f"phase.{day_phase(state.turn_count)}", "ko"),
        "weather": list(loc.weather),
        "features": list(loc.tags),
        "surroundings": surroundings,
        "targets": targets,
        "risk": risk_payload(loc.sleep_risk),
    }


def to_combat(state: GameState) -> dict | None:
    cs = state.combat_state
    if cs is None or not cs.turn_order:
        return None
    current_id = cs.turn_order[cs.current_turn]
    current = state.characters.get(current_id)
    actor_name = current.name if current else current_id
    turn_label = "내 차례" if current_id == state.player_id else f"{actor_name} 차례"
    enemies = []
    for eid in cs.enemy_ids:
        e = state.characters.get(eid)
        if e is None:
            continue
        enemies.append(
            {"name": e.name, "hp": e.hp, "hpMax": e.max_hp, "alive": e.alive}
        )
    return {
        "round": cs.round,
        "turnLabel": turn_label,
        "enemies": enemies,
    }


def pending_check_to_front(state: GameState, pending: PendingCheck) -> dict:
    """`stat_label` is the Korean stat name (built here so the client doesn't
    re-derive it). `stat_value` is the player's current score on that stat.
    `reason` is shown verbatim above the dice strip."""
    from ..wire.emit import _build_pending_check_payload  # local import avoids cycle
    return _build_pending_check_payload(state, pending).model_dump()


def to_front_state(state: GameState, graph: GameGraph | None = None) -> dict:
    """Assemble the full client-side state payload. `graph` is the relational
    SSOT — flow finalize passes the turn-end graph; tests/api glue can omit
    and we'll build internally."""
    if graph is None:
        graph = state.graph()
    pending = state.pending_check
    return {
        "hero": to_hero(state, graph),
        "subject": to_subject(state, graph),
        "quest": to_quest(state, graph),
        "place": to_place(state, graph),
        "combat": to_combat(state),
        "log": [e.model_dump() for e in state.log_entries],
        "pendingCheck": pending_check_to_front(state, pending) if pending else None,
        "storyGraph": to_story_graph(state, graph),
    }
