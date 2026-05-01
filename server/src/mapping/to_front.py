from collections import Counter

from ..domain.clock import day_phase
from ..domain.entities import (
    EQUIPMENT_SLOTS,
    Character,
    Location,
    Quest,
    Stats,
)
from ..domain.memory import PendingCheck
from ..domain.types import tier_to_int
from ..engines.growth import can_afford_level_up, xp_for_next_level
from ..domain.state import GameState
from ..ontology.graph import GameGraph, build_graph
from .josa import eun_neun


# --- Hero ------------------------------------------------------------------


_STAT_LABELS: tuple[tuple[str, str], ...] = (
    ("STR", "근력"),
    ("DEX", "민첩"),
    ("CON", "건강"),
    ("INT", "지능"),
    ("WIS", "지혜"),
    ("CHA", "매력"),
)
_STAT_LABEL_BY_KEY: dict[str, str] = dict(_STAT_LABELS)


def stat_label(stat: str) -> str:
    return _STAT_LABEL_BY_KEY.get(stat, stat)


def _stats(stats: Stats) -> list[dict]:
    return [{"label": label, "value": getattr(stats, key)} for key, label in _STAT_LABELS]


def _race_label(state: GameState, graph: GameGraph, char_id: str) -> str:
    """Race name resolved via the `belongs_to_race` edge — falls back to the
    raw race id when the relation points at a missing race entity."""
    for edge in graph.get_edges(char_id, "belongs_to_race"):
        race = state.races.get(edge.to_id)
        if race is not None:
            return race.name
        return edge.to_id
    return ""


def _race_job_label(state: GameState, graph: GameGraph, char: Character) -> str:
    """`<race> <job>` if the character has a job, otherwise just `<race>`."""
    race = _race_label(state, graph, char.id)
    return f"{race} · {char.job}" if char.job else race


def _gender_label(char: Character) -> str:
    """Korean label for display, empty for non-sexed entities."""
    if char.gender == "male":
        return "남성"
    if char.gender == "female":
        return "여성"
    return ""


def _equipment(state: GameState, graph: GameGraph, char_id: str) -> dict:
    out: dict[str, dict | None] = {slot: None for slot in EQUIPMENT_SLOTS}
    for edge in graph.get_edges(char_id, "equips"):
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
    counts: Counter[str] = Counter(
        e.to_id for e in graph.get_edges(char_id, "carries")
    )
    for edge in graph.get_edges(char_id, "equips"):
        item_id = edge.to_id
        counts[item_id] -= 1
        if counts[item_id] <= 0:
            del counts[item_id]
    return [
        {"name": state.items[item_id].name, "qty": qty}
        for item_id, qty in counts.items()
        if item_id in state.items
    ]


def _companion_label(
    state: GameState, graph: GameGraph, char_id: str
) -> str | None:
    """Returns the Korean label for a companion or None if the id no longer
    resolves (e.g. the companion died and was removed). Caller filters None
    so a stray technical id never reaches the UI."""
    if char_id not in state.characters:
        return None
    c = state.characters[char_id]
    return f"{c.name} ({_race_job_label(state, graph, c)})"


def _skill_names(state: GameState, graph: GameGraph, char_id: str) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for edge in graph.get_edges(char_id, "knows_skill"):
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
        graph = build_graph(state)
    p = state.characters[state.player_id]
    skills = _skill_names(state, graph, p.id)
    return {
        "name": p.name,
        "raceJob": _race_job_label(state, graph, p),
        "gender": _gender_label(p),
        "level": p.level,
        "exp": p.xp_pool,
        "expMax": xp_for_next_level(p.level),
        "canLevelUp": can_afford_level_up(p),
        "hp": p.hp,
        "hpMax": p.max_hp,
        "mp": p.mp,
        "mpMax": p.max_mp,
        "stats": _stats(p.stats),
        "equipment": _equipment(state, graph, p.id),
        "inventory": _inventory(state, graph, p.id),
        "status": list(p.status),
        "skills": skills,
        "companions": [
            label
            for edge in graph.get_edges(p.id, "has_companion")
            if (label := _companion_label(state, graph, edge.to_id)) is not None
        ],
    }


# --- Subject ---------------------------------------------------------------


def to_subject(state: GameState, graph: GameGraph | None = None) -> dict | None:
    if graph is None:
        graph = build_graph(state)
    if state.active_subject_id is None:
        return None
    sid = state.active_subject_id
    if sid not in state.characters:
        return None
    s = state.characters[sid]
    player = state.characters[state.player_id]
    if not s.alive:
        known = ["죽음"]
    else:
        known = [s.appearance] if s.appearance else []
        known += [m.content for m in player.memories if m.target_id == sid]
    skills = _skill_names(state, graph, s.id)
    return {
        "name": s.name,
        "role": s.role,
        "raceJob": _race_job_label(state, graph, s),
        "gender": _gender_label(s),
        "trust": s.relations.get(state.player_id, 0),
        "known": known,
        "level": s.level,
        "hp": s.hp,
        "hpMax": s.max_hp,
        "stats": _stats(s.stats),
        "equipment": _equipment(state, graph, s.id),
        "inventory": _inventory(state, graph, s.id),
        "skills": skills,
    }


# --- Quest -----------------------------------------------------------------


def to_quest(state: GameState, graph: GameGraph | None = None) -> dict | None:
    if graph is None:
        graph = build_graph(state)
    if state.active_quest_id is None:
        return None
    qid = state.active_quest_id
    if qid not in state.quests:
        return None
    q: Quest = state.quests[qid]
    giver_name = qid  # fallback to id
    for edge in graph.get_in_edges(qid, "gives_quest"):
        giver = state.characters.get(edge.from_id)
        if giver is not None:
            giver_name = giver.name
        else:
            giver_name = edge.from_id
        break
    # quest.triggers' display name is a per-trigger label — that's an
    # entity attribute on the trigger object (no relational scan), so read
    # the goals straight from the trigger names.
    goals = [t.name for t in q.triggers]
    return {
        "title": q.title,
        "summary": q.summary,
        "giver": giver_name,
        "difficulty": q.difficulty,
        "goals": goals,
        "conditions": list(q.conditions),
        "rewards": {"gold": q.rewards.gold, "exp": q.rewards.exp},
    }


# --- Place -----------------------------------------------------------------


_RISK_PAYLOAD: dict[str, dict] = {
    "safe": {"label": "안전", "tone": "good"},
    "risky": {"label": "주의", "tone": "neutral"},
    "dangerous": {"label": "위험", "tone": "bad"},
}


def to_place(state: GameState, graph: GameGraph | None = None) -> dict | None:
    if graph is None:
        graph = build_graph(state)
    p = state.characters[state.player_id]
    player_loc_id = p.location_id
    if player_loc_id is None or player_loc_id not in state.locations:
        return None
    loc: Location = state.locations[player_loc_id]
    surroundings = []
    for edge in graph.get_edges(player_loc_id, "connects_to"):
        target_id = edge.to_id
        target = state.locations.get(target_id)
        if target is None:
            continue
        attrs = edge.attrs or {}
        surroundings.append({
            "name": target.name,
            "blurb": target.description,
            "difficulty": attrs.get("difficulty"),
            "risk": _RISK_PAYLOAD[target.sleep_risk],
        })
    targets = []
    for edge in graph.get_in_edges(player_loc_id, "located_at"):
        cid = edge.from_id
        if cid == state.player_id:
            continue
        c = state.characters.get(cid)
        if c is None:
            continue
        blurb = "죽음" if not c.alive else (c.appearance or c.description)
        targets.append({
            "name": c.name,
            "level": c.level,
            "raceJob": _race_job_label(state, graph, c),
            "gender": _gender_label(c),
            "blurb": blurb,
            "trust": c.relations.get(state.player_id, 0),
        })
    return {
        "name": loc.name,
        "description": loc.description,
        "dayPhase": day_phase(state.turn_count),
        "weather": list(loc.weather),
        "features": list(loc.tags),
        "surroundings": surroundings,
        "targets": targets,
        "risk": _RISK_PAYLOAD[loc.sleep_risk],
    }


# --- Combat ----------------------------------------------------------------


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
        enemies.append({"name": e.name, "hp": e.hp, "hpMax": e.max_hp, "alive": e.alive})
    return {
        "round": cs.round,
        "turnLabel": turn_label,
        "enemies": enemies,
    }


# --- PendingCheck ----------------------------------------------------------


def pending_check_to_front(state: GameState, pending: PendingCheck) -> dict:
    """`stat_label` is the Korean stat name (built here so the client doesn't
    re-derive it). `stat_value` is the player's current score on that stat.
    `reason` is shown verbatim above the dice strip."""
    actor = state.characters[state.player_id]
    return {
        "kind": pending.kind,
        "dc": pending.dc,
        "stat": pending.stat,
        "stat_label": stat_label(pending.stat),
        "stat_value": getattr(actor.stats, pending.stat),
        "mod": pending.mod,
        "required_roll": pending.required_roll,
        "tier": {
            "value": tier_to_int(pending.tier),
            "max": 7,
            "label": pending.tier,
        },
        "target": pending.target,
        "reason": pending.reason,
    }


# --- Composed Korean strings (flow pushes these as GM lines) ---------------


def rest_completed_text(actor_name: str) -> str:
    return (
        f"{actor_name}{eun_neun(actor_name)} 자리를 잡고 잠을 청했습니다. "
        f"새벽이 밝아오자 푹 쉬고 일어났습니다. HP/MP가 모두 회복됐습니다."
    )


def rest_ambush_text(actor_name: str) -> str:
    return f"{actor_name}{eun_neun(actor_name)} 잠들기 직전 적의 습격을 받았습니다."


# --- FrontState ------------------------------------------------------------


def to_front_state(state: GameState, graph: GameGraph | None = None) -> dict:
    """Assemble the full client-side state payload. `graph` is the relational
    SSOT — flow finalize passes the turn-end graph; tests/api glue can omit
    and we'll build internally."""
    if graph is None:
        graph = build_graph(state)
    pending = state.pending_check
    return {
        "hero": to_hero(state, graph),
        "subject": to_subject(state, graph),
        "quest": to_quest(state, graph),
        "place": to_place(state, graph),
        "combat": to_combat(state),
        "log": [e.model_dump() for e in state.log_entries],
        "pendingCheck": pending_check_to_front(state, pending) if pending else None,
    }
