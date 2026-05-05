"""/roll — resolve the pending stat check, narrate the outcome, and
re-enter the auto-combat loop if a fight was paused for an environment roll."""

import random
from collections.abc import AsyncIterator

from ..domain.errors import PendingCheckExpected
from ..locale import render
from ..domain.memory import BonusItem, RollLogEntry
from ..domain.state import GameState
from ..engines.apply import apply_changes
from ..engines.combat import stat_modifier
from ..engines.growth import grant_roll_xp
from ..llm.client import LLMClient, set_llm_session_if_unset
from ..llm_calls.classify.schema import Verb
from ..mapping.to_front import stat_label
from ..persistence.repo import SaveRepo, ScenarioRepo
from ..rules.dc import compute_grade
from .buff_tick import tick_turn_buffs
from .combat_auto import PlayerAction, run_auto_combat
from .combat_phase import emit_combat_cinematic_and_end
from .companion import handle_recruit_roll_result
from ..wire.emit import emit_log_entry
from .dirty import (
    Dirty,
    ToFrontFn,
    finalize,
    next_log_id,
    push_log_entry,
)
from .format import front_grade
from .narrate import consume_narrate, run_narrate, stream_narrate_tail


_MOVE_GRADES = ("critical_success", "success", "partial_success")


def _apply_movement_roll_outcome(
    state: GameState, pending, grade: str, dirty: Dirty
) -> None:
    """Frictional-movement roll: judge sent `targets=[connection_id]` and a passing grade means the player reaches it. Prop rolls (`targets=[current_loc_id]`) skip this — destination equals origin."""
    if grade not in _MOVE_GRADES or not pending.targets:
        return
    dest = pending.targets[0]
    if dest not in state.locations:
        return
    player = state.characters[state.player_id]
    if player.location_id == dest:
        return
    apply_changes(
        state,
        [{"type": "move", "target": state.player_id, "destination": dest}],
        dirty,
    )
    state.invalidate_graph()


async def _resume_auto_combat(
    client: LLMClient,
    state: GameState,
    scenario_repo: ScenarioRepo,
    dirty: Dirty,
    rng: random.Random | None,
) -> AsyncIterator[dict]:
    """An environment roll inside combat costs the player their action for
    this fight. Drive an auto-cycle (player passes, NPCs continue) until the
    fight terminates."""
    result = run_auto_combat(
        state,
        dirty,
        player_action=PlayerAction(kind="pass"),
        rng=rng,
    )
    async for ev in emit_combat_cinematic_and_end(
        client,
        state,
        scenario_repo,
        dirty,
        player_input=render("log.roll.synthetic_environment", "ko"),
        result=result,
    ):
        yield ev


async def run_roll(
    client: LLMClient,
    state: GameState,
    scenario_repo: ScenarioRepo,
    save_repo: SaveRepo,
    *,
    to_front_fn: ToFrontFn | None = None,
    rng: random.Random | None = None,
) -> AsyncIterator[dict]:
    set_llm_session_if_unset(state.game_id)
    if state.pending_check is None:
        raise PendingCheckExpected("no pending_check; call /turn first")

    dirty = Dirty()
    pending = state.pending_check
    state.turn_count += 1

    rng_obj = rng or random
    dice = rng_obj.randint(1, 20)

    total = dice + pending.mod
    grade = compute_grade(dice, total, pending.required_roll)

    actor = state.characters[state.player_id]
    stat_value = getattr(actor.stats, pending.stat)
    stat_mod = stat_modifier(stat_value)
    breakdown = [
        BonusItem(label=render("ui.roll.dice_label", "ko"), value=dice),
        BonusItem(label=stat_label(pending.stat), value=stat_mod),
    ]
    if pending.mod != 0:
        breakdown.append(BonusItem(label=render("ui.roll.affinity_label", "ko"), value=pending.mod))

    roll_log = RollLogEntry(
        id=next_log_id(state),
        kind="roll",
        check=stat_label(pending.stat),
        roll=dice,
        margin=total - pending.required_roll,
        result=front_grade(grade),
        bonus_breakdown=breakdown,
    )
    push_log_entry(state, roll_log, dirty)
    yield emit_log_entry(roll_log)

    # Recruit rolls don't grant XP — they're social judgment calls, not growth events. Skip the XP/narrate stat-roll path entirely.
    if pending.kind == "recruit":
        async for ev in handle_recruit_roll_result(state, pending, grade, dirty):
            yield ev
        state.pending_check = None
        tick_turn_buffs(state, dirty)
        if client is not None:
            graph = state.graph()
            signal = state.previous_phase_signal
            state.previous_phase_signal = None
            async for ev in stream_narrate_tail(
                client,
                state,
                scenario_repo,
                pending.player_input,
                dirty,
                to_front_fn,
                Verb(name="wait"),
                graph=graph,
                previous_phase_signal=signal,
            ):
                yield ev
        async for ev in finalize(state, save_repo, dirty, to_front_fn):
            yield ev
        return

    grant_roll_xp(state, grade, dirty=dirty.entities)

    judge_result = {
        "action": "roll",
        "tier": pending.tier,
        "stat": pending.stat,
        "targets": pending.targets,
    }
    graph = state.graph()
    stream = run_narrate(
        client,
        state,
        scenario_repo,
        pending.player_input,
        judge_result=judge_result,
        graph=graph,
        grade=grade,
        target_id=pending.target,
    )
    async for ev in consume_narrate(
        state,
        dirty,
        stream,
        target_for_log=pending.target,
        dialogue_input=pending.player_input,
        graph=graph,
    ):
        yield ev

    state.pending_check = None
    _apply_movement_roll_outcome(state, pending, grade, dirty)
    tick_turn_buffs(state, dirty)

    if state.combat_state is not None:
        async for ev in _resume_auto_combat(client, state, scenario_repo, dirty, rng):
            yield ev

    async for ev in finalize(state, save_repo, dirty, to_front_fn):
        yield ev
