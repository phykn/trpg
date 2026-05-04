"""Recruit / dismiss companion flow — explicit add/remove of the companion list
with system card + previous_phase_signal hand-off to narrate. The companion list
stays forbidden in narrate's set permission; flow mutates directly."""

from collections.abc import AsyncIterator
from datetime import UTC, datetime

from ..domain.errors import PersistenceFailed
from ..domain.memory import PendingCheck
from ..domain.state import GameState
from ..mapping.to_front import pending_check_to_front
from ..persistence.repo import SaveRepo
from ..rules import RULES
from ..rules.dc import compute_required_roll
from .dirty import Dirty, ToFrontFn, finalize, flush, push_act
from .error_phrases import humanize_runtime_error
from .format import (
    format_dismiss_log,
    format_dismiss_turn_log,
    format_recruit_critical_failure_log,
    format_recruit_failure_log,
    format_recruit_success_log,
)


def _clamp(v: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, v))


def _recruit_dc(state: GameState, target_id: str) -> int:
    target = state.characters.get(target_id)
    rel = target.relations.get(state.player_id, 0) if target else 0
    base = RULES.companions.recruit_base_dc  # ssot-allow: RULES config attribute, not entity.companions list
    return base - _clamp(rel // 10, -5, 5)


async def run_recruit(
    state: GameState,
    save_repo: SaveRepo,
    player_input: str,
    target_id: str,
    dirty: Dirty,
    to_front_fn: ToFrontFn | None,
) -> AsyncIterator[dict]:
    """Set a recruit-kind pending_check and emit pending_check SSE.
    The /roll endpoint resolves the result via flow/companion.handle_recruit_roll_result."""
    actor = state.characters[state.player_id]

    if target_id not in state.characters:
        async for ev in finalize(state, save_repo, dirty, to_front_fn):
            yield ev
        return
    if target_id in actor.companions:  # ssot-allow: write path guard
        async for ev in finalize(state, save_repo, dirty, to_front_fn):
            yield ev
        return

    dc = _recruit_dc(state, target_id)
    stat_value = actor.stats.CHA
    required_roll = compute_required_roll(dc, stat_value)

    state.pending_check = PendingCheck(
        player_input=player_input,
        kind="recruit",
        tier="보통",
        stat="CHA",
        target=target_id,
        targets=[target_id],
        dc=dc,
        mod=0,
        required_roll=required_roll,
        reason="동료 영입",
        created_at=datetime.now(UTC).isoformat(),
    )
    try:
        await flush(state, save_repo, dirty)
    except PersistenceFailed as e:
        yield {
            "type": "error",
            "data": {
                "message": humanize_runtime_error(e),
                "code": "PersistenceFailed",
            },
        }
        return
    yield {
        "type": "pending_check",
        "data": pending_check_to_front(state, state.pending_check),
    }


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


async def handle_recruit_roll_result(
    state: GameState,
    pending: PendingCheck,
    grade: str,
    dirty: Dirty,
) -> AsyncIterator[dict]:
    """Apply recruit roll outcome: companions add (success branches) or
    affinity drop (critical_failure). Pushes a system card and sets
    previous_phase_signal for the next narrate."""
    target_id = pending.target
    target = state.characters.get(target_id)
    if target is None:
        return
    target_name = target.name
    player = state.characters[state.player_id]

    rules = RULES.companions  # ssot-allow: RULES config attribute, not entity.companions list

    if grade in ("critical_success", "success", "partial_success"):
        if target_id not in player.companions:  # ssot-allow: write path guard
            player.companions.append(target_id)  # ssot-allow: write path
            state.invalidate_graph()
            dirty.entities.add(("characters", state.player_id))
        delta = (
            rules.recruit_affinity_crit_success
            if grade == "critical_success"
            else rules.recruit_affinity_success
        )
        target.relations[state.player_id] = (
            target.relations.get(state.player_id, 0) + delta
        )
        dirty.entities.add(("characters", target_id))
        yield push_act(
            state,
            dirty,
            format_recruit_success_log(target_name),
            turn_summary=f"{target_name} 동료 합류",
        )
        state.previous_phase_signal = f"companion_joined:{target_name}"
        return

    if grade == "critical_failure":
        target.relations[state.player_id] = (
            target.relations.get(state.player_id, 0) + rules.recruit_affinity_crit_failure
        )
        dirty.entities.add(("characters", target_id))
        yield push_act(
            state,
            dirty,
            format_recruit_critical_failure_log(target_name),
            turn_summary=f"{target_name} 동료 영입 실패",
        )
    else:
        yield push_act(
            state,
            dirty,
            format_recruit_failure_log(target_name),
            turn_summary=f"{target_name} 동료 영입 실패",
        )
    state.previous_phase_signal = f"companion_refused:{target_name}"
