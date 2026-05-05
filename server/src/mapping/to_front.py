"""FrontState builder — `to_front_state(state)` returns the flat dict the
client renders. Korean dates, durations, composed strings, and conditional
labels are all built here. Story graph projection lives in
`story_graph.py`; shared label helpers live in `labels.py`."""

from ..domain.clock import day_phase
from ..domain.entities import Location
from ..domain.memory import PendingCheck
from ..domain.state import GameState
from ..locale import render
from ..ontology.graph import GameGraph
from ..ontology.queries import connections_of, inhabitants_of
from .labels import (
    gender_label,
    race_job_label,
    risk_payload,
    stat_label,
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


def to_hero(state: GameState, graph: GameGraph | None = None) -> dict:
    """Wire shape comes from `_build_hero_payload`; this just unwraps to a
    plain dict for state-payload embedding."""
    from ..wire.emit import _build_hero_payload  # local import avoids layer cycle
    if graph is None:
        graph = state.graph()
    return _build_hero_payload(state, graph).model_dump()


def to_subject(state: GameState, graph: GameGraph | None = None) -> dict | None:
    """Wire shape comes from `_build_subject_payload`; this just unwraps to
    a plain dict (or None) for state-payload embedding."""
    from ..wire.emit import _build_subject_payload  # local import avoids layer cycle
    if graph is None:
        graph = state.graph()
    payload = _build_subject_payload(state, graph)
    return payload.model_dump() if payload else None


def to_quest(state: GameState, graph: GameGraph | None = None) -> dict | None:
    """Wire shape comes from `_build_quest_payload`; this just unwraps to a
    plain dict (or None) for state-payload embedding."""
    from ..wire.emit import _build_quest_payload  # local import avoids layer cycle
    if graph is None:
        graph = state.graph()
    payload = _build_quest_payload(state, graph)
    return payload.model_dump() if payload else None


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
