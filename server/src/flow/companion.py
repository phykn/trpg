"""Recruit / dismiss companion flow — explicit add/remove of the companion list
with system card + previous_phase_signal hand-off to narrate. The companion list
stays forbidden in narrate's set permission; flow mutates directly."""

from collections.abc import AsyncIterator

from ..domain.state import GameState
from ..persistence.repo import SaveRepo
from .dirty import Dirty, ToFrontFn, finalize, push_act
from .format import format_dismiss_log, format_dismiss_turn_log


async def run_dismiss(
    state: GameState,
    save_repo: SaveRepo,
    target_id: str,
    dirty: Dirty,
    to_front_fn: ToFrontFn | None,
) -> AsyncIterator[dict]:
    """Remove target_id from the player's companion list. No roll. No affinity change.
    Pushes a system card + sets previous_phase_signal so next narrate frames
    the parting in prose."""
    player = state.characters[state.player_id]
    if target_id not in player.companions:  # ssot-allow: write path guard, not a relation scan
        async for ev in finalize(state, save_repo, dirty, to_front_fn):
            yield ev
        return

    target = state.characters.get(target_id)
    target_name = target.name if target else target_id

    player.companions.remove(target_id)  # ssot-allow: write path mutation
    state.invalidate_graph()
    dirty.entities.add(("characters", state.player_id))

    yield push_act(
        state,
        dirty,
        format_dismiss_log(target_name),
        turn_summary=format_dismiss_turn_log(target_name),
    )
    state.previous_phase_signal = f"companion_dismissed:{target_name}"

    state.turn_count += 1

    async for ev in finalize(state, save_repo, dirty, to_front_fn):
        yield ev
