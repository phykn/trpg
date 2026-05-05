"""FrontState builder — `to_front_state(state)` returns the flat dict the
client renders. Korean dates, durations, composed strings, and conditional
labels are all built here. Story graph projection lives in
`story_graph.py`; shared label helpers live in `labels.py`."""

from ..game.domain.memory import PendingCheck
from ..game.domain.state import GameState
from ..game.ontology.graph import GameGraph
from .labels import stat_label
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
    """Wire shape comes from `_build_place_payload`; this just unwraps to a
    plain dict (or None) for state-payload embedding."""
    from ..wire.emit import _build_place_payload  # local import avoids layer cycle
    if graph is None:
        graph = state.graph()
    payload = _build_place_payload(state, graph)
    return payload.model_dump() if payload else None


def to_combat(state: GameState) -> dict | None:
    """Wire shape comes from `_build_combat_badge_payload`; this just unwraps
    to a plain dict (or None) for state-payload embedding."""
    from ..wire.emit import _build_combat_badge_payload  # local import avoids layer cycle
    payload = _build_combat_badge_payload(state)
    return payload.model_dump() if payload else None


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
