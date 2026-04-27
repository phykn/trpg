"""Active subject tracking — keep `state.active_subject_id` in sync with the
NPC the player is currently engaging with.

The seed pins an initial subject (e.g., the quest-giver in the opening scene),
but once gameplay starts the panel should follow the player's focus: combat
target, roll target, trade partner, or recent dialogue NPC. Without this,
the seed value sticks forever and the frontend shows the wrong character.
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
from ..context.surroundings import recent_npc_id
from ..domain.state import GameState


def _is_active_npc(state: GameState, cid: str) -> bool:
    if cid == state.player_id:
        return False
    ch = state.characters.get(cid)
    return ch is not None and ch.alive


def refresh_active_subject(state: GameState, result) -> None:
    """Update active_subject_id to whoever the player is engaging this turn.

    Explicit-target actions (combat/roll/buy/sell) take precedence; for
    narrate-path actions (pass/reject) we fall back to recent_npc, which
    captures whoever the previous narrate turn was about.
    """
    candidate: str | None = None

    if isinstance(result, (CombatAction, RollAction, PassAction)):
        for tid in result.targets:
            if _is_active_npc(state, tid):
                candidate = tid
                break
    elif isinstance(result, (BuyAction, SellAction)):
        if _is_active_npc(state, result.npc_id):
            candidate = result.npc_id
    elif isinstance(result, SummonCombatAction):
        # active_subject will be set when the summoned character is registered.
        return
    elif isinstance(result, ChainAction):
        # Walk parts in reverse; first NPC-engaging part wins.
        for part in reversed(result.parts):
            if isinstance(part, PassAction):
                for tid in part.targets:
                    if _is_active_npc(state, tid):
                        candidate = tid
                        break
                if candidate is not None:
                    break
            elif isinstance(part, (BuyAction, SellAction)):
                if _is_active_npc(state, part.npc_id):
                    candidate = part.npc_id
                    break

    if candidate is None:
        candidate = recent_npc_id(state, state.player_id)

    if candidate is not None and candidate != state.active_subject_id:
        state.active_subject_id = candidate
