"""Active subject tracking — keep `state.active_subject_id` in sync with the
NPC the player is currently engaging with.

The seed pins an initial subject (e.g., the quest-giver in the opening scene),
but once gameplay starts the panel should follow the player's focus: combat
target, roll target, trade partner, or recent dialogue NPC. Without this,
the seed value sticks forever and the client shows the wrong character.
"""

from src.llm.calls.classify.schema import Verb
from ..domain.state import GameState
from ..ontology.graph import GameGraph
from ..ontology.queries import inhabitants_of, location_of


def _is_active_npc(state: GameState, cid: str) -> bool:
    if cid == state.player_id:
        return False
    return cid in state.characters


def _candidate_from_verb(state: GameState, verb: Verb) -> str | None:
    """Per-verb subject candidate. attack/cast/perceive use target_ids; speak/transfer
    use modifiers (target / from_id / to_id). wait/rest no-op."""
    if verb.name in ("attack", "cast", "perceive", "wait"):
        for tid in verb.target_ids:
            if _is_active_npc(state, tid):
                return tid
        return None
    if verb.name == "speak":
        target = verb.modifiers.get("target")
        if isinstance(target, str) and _is_active_npc(state, target):
            return target
        return None
    if verb.name == "transfer":
        # buy: from=npc_id (NPC is the active subject). sell: to=npc_id.
        for k in ("from_id", "to_id"):
            v = verb.modifiers.get(k)
            if isinstance(v, str) and _is_active_npc(state, v):
                return v
        return None
    if verb.name == "use":
        target_id = verb.modifiers.get("target_id")
        if isinstance(target_id, str) and _is_active_npc(state, target_id):
            return target_id
        return None
    # move, rest: no NPC engagement signal.
    return None


def refresh_active_subject(state: GameState, verbs: list[Verb]) -> None:
    """Update active_subject_id to whoever the player is engaging this turn.
    Walks `verbs` in reverse so the last-emitted verb wins on chains."""
    # Defensive: drop pin only on actual deletion. Death keeps the pin (Subject panel still shows the corpse).
    cur = state.active_subject_id
    if cur is not None and cur not in state.characters:
        state.active_subject_id = None

    candidate: str | None = None
    for verb in reversed(verbs):
        candidate = _candidate_from_verb(state, verb)
        if candidate is not None:
            break

    if candidate is None:
        candidate = state.recent_npc_id(state.player_id)

    if candidate is not None and candidate != state.active_subject_id:
        state.active_subject_id = candidate


def reconcile_subject_after_move(
    state: GameState, graph: GameGraph | None = None
) -> None:
    """Re-pick the subject after the player relocates. Called from `emit_move` once the location_id has flipped — drops a pin pointing at the old location and restores via `recent_npc_id` if the player previously addressed an NPC at the new location, else leaves the pin cleared (caller may override with context-aware logic, e.g. NPC name in player_input)."""
    cur = state.active_subject_id
    if cur is None:
        return
    subj = state.characters.get(cur)
    if graph is None:
        graph = state.graph()
    player_loc = location_of(graph, state.player_id)
    if subj is not None and location_of(graph, cur) == player_loc:
        return

    state.active_subject_id = state.recent_npc_id(state.player_id)


def pin_subject_by_input_name(
    state: GameState, player_input: str, graph: GameGraph | None = None
) -> None:
    """If `player_input` literally names an alive NPC at the player's current location, pin them. Conservative: scoped to current location and exact-name substring, so it fires for "탈크의 대장간으로 이동" but not for stray mentions of NPCs elsewhere."""
    if not player_input:
        return
    if graph is None:
        graph = state.graph()
    player_loc = location_of(graph, state.player_id)
    if player_loc is None:
        return
    for cid in inhabitants_of(graph, player_loc):
        if cid == state.player_id:
            continue
        ch = state.characters.get(cid)
        if ch is None or not ch.alive or not ch.name:
            continue
        if ch.name in player_input:
            state.active_subject_id = cid
            return
