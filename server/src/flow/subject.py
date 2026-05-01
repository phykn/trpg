"""Active subject tracking — keep `state.active_subject_id` in sync with the
NPC the player is currently engaging with.

The seed pins an initial subject (e.g., the quest-giver in the opening scene),
but once gameplay starts the panel should follow the player's focus: combat
target, roll target, trade partner, or recent dialogue NPC. Without this,
the seed value sticks forever and the client shows the wrong character.
"""
from ..agents.dc_judge.schema import (
    BuyAction,
    ChainAction,
    CombatAction,
    PassAction,
    RollAction,
    SellAction,
    SummonCombatAction,
)
from ..domain.state import GameState
from ..ontology.graph import GameGraph, build_graph


def _is_active_npc(state: GameState, cid: str) -> bool:
    if cid == state.player_id:
        return False
    return cid in state.characters


def _candidate_from_action(state: GameState, action) -> str | None:
    """Per-action subject candidate. Returns the NPC id this action engages,
    or None if the action doesn't carry an engagement signal."""
    if isinstance(action, (CombatAction, RollAction, PassAction)):
        for tid in action.targets:
            if _is_active_npc(state, tid):
                return tid
        return None
    if isinstance(action, (BuyAction, SellAction)):
        if _is_active_npc(state, action.npc_id):
            return action.npc_id
    return None


def refresh_active_subject(state: GameState, result) -> None:
    """Update active_subject_id to whoever the player is engaging this turn.

    Explicit-target actions (combat/roll/buy/sell) take precedence; for
    narrate-path actions (pass/reject) we fall back to recent_npc, which
    captures whoever the previous narrate turn was about.
    """
    # Only drop the pinned subject if the character was deleted from state
    # (shouldn't happen in current flow, but defensive). Death itself keeps
    # the pin — the Subject panel renders it as 죽음 so the player still has
    # the corpse's identity on screen.
    cur = state.active_subject_id
    if cur is not None and cur not in state.characters:
        state.active_subject_id = None

    if isinstance(result, SummonCombatAction):
        # active_subject will be set when the summoned character is registered.
        return

    candidate: str | None = None
    if isinstance(result, ChainAction):
        # Walk parts in reverse; first NPC-engaging part wins.
        for part in reversed(result.parts):
            candidate = _candidate_from_action(state, part)
            if candidate is not None:
                break
    else:
        candidate = _candidate_from_action(state, result)

    if candidate is None:
        candidate = state.recent_npc_id(state.player_id)

    if candidate is not None and candidate != state.active_subject_id:
        state.active_subject_id = candidate


def reconcile_subject_after_move(
    state: GameState, graph: GameGraph | None = None
) -> None:
    """Re-pick the subject after the player relocates.

    `refresh_active_subject` runs before `apply_intended_move`, so for travel
    turns it sees the old location and leaves the pin on the previous NPC.
    Once the player has actually moved, the pin is at the wrong location:
    drop it and prefer a same-location NPC — recent_npc_id (most recently
    addressed there) first, else the first alive resident, else clear.
    """
    cur = state.active_subject_id
    if cur is None:
        return
    subj = state.characters.get(cur)
    player = state.characters[state.player_id]
    if subj is not None and subj.location_id == player.location_id:
        return

    candidate = state.recent_npc_id(state.player_id)
    if candidate is None and player.location_id is not None:
        if graph is None:
            graph = build_graph(state)
        for edge in graph.get_in_edges(player.location_id, "located_at"):
            cid = edge.from_id
            if cid == state.player_id:
                continue
            c = state.characters.get(cid)
            if c is not None and c.alive:
                candidate = cid
                break
    state.active_subject_id = candidate
