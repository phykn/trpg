from collections import Counter
from datetime import datetime

from ..domain.entities import (
    EQUIPMENT_SLOTS,
    Character,
    Location,
    Quest,
)
from ..domain.memory import PendingCheck
from ..domain.types import tier_to_int
from ..engines.growth import can_afford_level_up, xp_for_next_level
from ..domain.state import GameState


# --- Hero ------------------------------------------------------------------


def _race_name(state: GameState, race_id: str) -> str:
    race = state.races.get(race_id)
    return race.name if race else race_id


def _race_job_label(state: GameState, char: Character) -> str:
    """`<race> <job>` if the character has a job, otherwise just `<race>`."""
    race = _race_name(state, char.race_id)
    return f"{race} {char.job}" if char.job else race


def _equipment(state: GameState, char: Character) -> dict:
    out: dict[str, dict | None] = {slot: None for slot in EQUIPMENT_SLOTS}
    for slot, item_id in char.equipment.equipped_items():
        if item_id in state.items:
            out[slot] = {"name": state.items[item_id].name}
    return out


def _inventory(state: GameState, ids: list[str]) -> list[dict]:
    return [
        {"name": state.items[item_id].name, "qty": qty}
        for item_id, qty in Counter(ids).items()
        if item_id in state.items
    ]


def _companion_label(state: GameState, char_id: str) -> str:
    if char_id not in state.characters:
        return char_id
    c = state.characters[char_id]
    return f"{c.name} ({_race_job_label(state, c)})"


def to_hero(state: GameState) -> dict:
    p = state.characters[state.player_id]
    skill_ids = (*p.racial_skill_ids, *p.learned_skill_ids)
    skills = [
        state.skills[sid].name for sid in skill_ids if sid in state.skills
    ]
    return {
        "name": p.name,
        "raceJob": _race_job_label(state, p),
        "level": p.level,
        "exp": p.xp_pool,
        "expMax": xp_for_next_level(p.level),
        "canLevelUp": can_afford_level_up(p),
        "hp": p.hp,
        "hpMax": p.max_hp,
        "mp": p.mp,
        "mpMax": p.max_mp,
        "stats": p.stats.model_dump(),
        "equipment": _equipment(state, p),
        "inventory": _inventory(state, p.inventory_ids),
        "status": list(p.status),
        "skills": skills,
        "companions": [_companion_label(state, cid) for cid in p.companions],
    }


# --- Subject ---------------------------------------------------------------


def to_subject(state: GameState) -> dict | None:
    if state.active_subject_id is None:
        return None
    sid = state.active_subject_id
    if sid not in state.characters:
        return None
    s = state.characters[sid]
    player = state.characters[state.player_id]
    known = [s.appearance] if s.appearance else []
    known += [m.content for m in player.memories if m.target_id == sid]
    return {
        "name": s.name,
        "role": s.role,
        "raceJob": _race_job_label(state, s),
        "trust": s.relations.get(state.player_id, 0),
        "known": known,
        "level": s.level,
        "hp": s.hp,
        "hpMax": s.max_hp,
        "stats": s.stats.model_dump(),
        "inventory": _inventory(state, s.inventory_ids),
    }


# --- Quest -----------------------------------------------------------------


def to_quest(state: GameState) -> dict | None:
    if state.active_quest_id is None:
        return None
    qid = state.active_quest_id
    if qid not in state.quests:
        return None
    q: Quest = state.quests[qid]
    giver = state.characters.get(q.giver_id)
    return {
        "title": q.title,
        "summary": q.summary,
        "giver": giver.name if giver else q.giver_id,
        "difficulty": {
            "value": tier_to_int(q.difficulty),
            "max": 7,
            "label": q.difficulty,
        },
        "goals": [t.name for t in q.triggers],
        "conditions": list(q.conditions),
        "rewards": {"gold": q.rewards.gold, "exp": q.rewards.exp},
    }


# --- Place -----------------------------------------------------------------


def _korean_date(dt: datetime) -> str:
    return f"{dt.year}년 {dt.month}월 {dt.day}일"


def _period(hour: int) -> str:
    if 5 <= hour < 7:
        return "새벽"
    if 7 <= hour < 12:
        return "오전"
    if 12 <= hour < 18:
        return "오후"
    if 18 <= hour < 21:
        return "저녁"
    return "밤"


def to_place(state: GameState) -> dict | None:
    p = state.characters[state.player_id]
    if p.location_id is None or p.location_id not in state.locations:
        return None
    loc: Location = state.locations[p.location_id]
    dt = datetime.fromisoformat(state.world_time)
    surroundings = [
        state.locations[c.target_id].name
        for c in loc.connections
        if c.target_id in state.locations
    ]
    return {
        "name": loc.name,
        "date": _korean_date(dt),
        "hour": dt.hour,
        "period": _period(dt.hour),
        "weather": list(loc.weather),
        "features": list(loc.tags),
        "surroundings": surroundings,
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


# --- Log -------------------------------------------------------------------


def to_log(state: GameState) -> list[dict]:
    return [e.model_dump() for e in state.log_entries]


# --- PendingCheck ----------------------------------------------------------


def pending_check_to_front(pending: PendingCheck) -> dict:
    return {
        "kind": pending.kind,
        "dc": pending.dc,
        "stat": pending.stat,
        "mod": pending.mod,
        "required_roll": pending.required_roll,
        "tier": {
            "value": tier_to_int(pending.tier),
            "max": 7,
            "label": pending.tier,
        },
        "target": pending.target,
    }


def to_pending_check(state: GameState) -> dict | None:
    if state.pending_check is None:
        return None
    return pending_check_to_front(state.pending_check)


# --- Composed Korean strings (flow pushes these as GM lines) ---------------


def rest_completed_text(actor_name: str, hours: int) -> str:
    return (
        f"{actor_name}은(는) 자리를 잡고 잠을 청한다. "
        f"{hours}시간 후 푹 쉬고 일어나, HP/MP 가 모두 회복됐다."
    )


def rest_ambush_text(actor_name: str) -> str:
    return f"{actor_name}이(가) 잠들기 직전 적의 습격을 받는다."


# --- FrontState ------------------------------------------------------------


def to_front_state(state: GameState) -> dict:
    return {
        "hero": to_hero(state),
        "subject": to_subject(state),
        "quest": to_quest(state),
        "place": to_place(state),
        "combat": to_combat(state),
        "log": to_log(state),
        "pendingCheck": to_pending_check(state),
    }
