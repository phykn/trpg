"""/roll — resolve the pending check, narrate the outcome, and resume any
in-flight combat."""
import random
from collections.abc import AsyncIterator

from ..domain.errors import PendingCheckExpected
from ..domain.memory import RollLogEntry
from ..domain.state import GameState
from ..engines import combat as combat_engine
from ..engines.growth import can_afford_level_up, grant_roll_xp
from ..llm.client import LLMClient
from ..rules.dc import compute_grade
from .combat_phase import run_combat_npc_phase
from .dirty import (
    Dirty,
    ToFrontFn,
    advance_time,
    finalize,
    maybe_push_levelup_hint,
    next_log_id,
    push_log_entry,
)
from .format import front_grade
from .narrate import consume_narrate, run_narrate


async def run_roll(
    client: LLMClient,
    state: GameState,
    profile_dir: str,
    saves_dir: str,
    *,
    to_front_fn: ToFrontFn | None = None,
    rng: random.Random | None = None,
) -> AsyncIterator[dict]:
    if state.pending_check is None:
        raise PendingCheckExpected("no pending_check; call /turn first")

    dirty = Dirty()
    pending = state.pending_check
    state.turn_count += 1

    rng_obj = rng or random
    dice = rng_obj.randint(1, 20)
    total = dice + pending.mod
    grade = compute_grade(dice, total, pending.required_roll)

    roll_log = RollLogEntry(
        id=next_log_id(state),
        kind="roll",
        check=pending.stat,
        dc=pending.dc,
        roll=dice,
        mod=pending.mod,
        result=front_grade(grade),
    )
    push_log_entry(state, roll_log, dirty)
    yield {"type": "log_entry", "data": roll_log.model_dump()}

    pre_can_level = can_afford_level_up(state.characters[state.player_id])
    grant_roll_xp(state, grade, dirty=dirty.entities)
    levelup_hint = maybe_push_levelup_hint(state, dirty, was_able=pre_can_level)
    if levelup_hint:
        yield levelup_hint

    judge_result = {
        "action": "roll",
        "tier": pending.tier,
        "stat": pending.stat,
        "targets": pending.targets,
    }
    stream = run_narrate(
        client,
        state,
        profile_dir,
        pending.player_input,
        judge_result=judge_result,
        grade=grade,
        target_id=pending.target,
    )
    async for ev in consume_narrate(
        state,
        dirty,
        stream,
        target_for_log=pending.target,
        dialogue_input=pending.player_input,
    ):
        yield ev

    state.pending_check = None
    advance_time(state)

    if state.combat_state is not None:
        # Environment rolls cost the player one combat turn — NPC phase resumes.
        combat_engine.advance_turn(state)
        async for ev in run_combat_npc_phase(state, dirty, rng):
            yield ev

    async for ev in finalize(state, saves_dir, dirty, to_front_fn):
        yield ev
