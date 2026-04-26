from collections import Counter
from datetime import datetime

from ..domain.entities import (
    EQUIPMENT_SLOTS,
    Character,
    Location,
    Quest,
)
from ..pipeline.dc import tier_to_int
from ..state.models import GameState


# --- Hero ------------------------------------------------------------------


def _race_name(state: GameState, race_id: str) -> str:
    race = state.races.get(race_id)
    return race.name if race else race_id


def _equipment(state: GameState, char: Character) -> dict:
    out: dict[str, dict | None] = {}
    for slot in EQUIPMENT_SLOTS:
        item_id = getattr(char.equipment, slot)
        if item_id and item_id in state.items:
            out[slot] = {"name": state.items[item_id].name}
        else:
            out[slot] = None
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
    race_name = _race_name(state, c.race_id)
    inner = f"{race_name} {c.job}".strip() if c.job else race_name
    return f"{c.name} ({inner})"


def to_hero(state: GameState) -> dict:
    p = state.characters[state.player_id]
    skills = [s.name for s in p.racial_skills] + [s.name for s in p.learned_skills]
    return {
        "name": p.name,
        "race": _race_name(state, p.race_id),
        "job": p.job,
        "level": p.level,
        "exp": 0,           # P3 — xp/level 곡선
        "expMax": 0,
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
        "race": _race_name(state, s.race_id),
        "job": s.job,
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


def _korean_date(world_time: str) -> str:
    dt = datetime.fromisoformat(world_time)
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
        "date": _korean_date(state.world_time),
        "hour": dt.hour,
        "period": _period(dt.hour),
        "weather": list(loc.weather),
        "features": list(loc.tags),
        "surroundings": surroundings,
    }


# --- Log -------------------------------------------------------------------


def to_log_entry(entry) -> dict:
    return entry.model_dump()


def to_log(state: GameState) -> list[dict]:
    return [to_log_entry(e) for e in state.log_entries]


# --- FrontState ------------------------------------------------------------


def to_front_state(state: GameState) -> dict:
    return {
        "hero": to_hero(state),
        "subject": to_subject(state),
        "quest": to_quest(state),
        "place": to_place(state),
        "log": to_log(state),
    }
