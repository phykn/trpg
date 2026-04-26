"""/roll — resolve the pending check, narrate the outcome, and resume any
in-flight combat."""
import random
from collections.abc import AsyncIterator

from ..agents.narrate import NarrativeDelta, NarrativeFinal
from ..domain.errors import PendingCheckExpected
from ..domain.memory import GMLogEntry, RollLogEntry
from ..domain.state import GameState
from ..engines import combat as combat_engine
from ..engines.apply import apply_changes
from ..llm.client import LLMClient
from ..rules.dc import compute_grade
from .combat_phase import run_combat_npc_phase
from .dirty import (
    Dirty,
    ToFrontFn,
    advance_time,
    finalize,
    next_log_id,
    push_dialogue,
    push_log_entry,
    push_turn_log,
)
from .format import front_grade, label_for_target
from .memory_writer import write_memories
from .narrate import run_narrate


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

    target_name = label_for_target(state, pending.target)
    check_label = f"{pending.stat} · {pending.reason} (→ {target_name})"
    roll_log = RollLogEntry(
        id=next_log_id(state),
        kind="roll",
        check=check_label,
        dc=pending.dc,
        roll=dice,
        mod=pending.mod,
        result=front_grade(grade),
    )
    push_log_entry(state, roll_log, dirty)
    yield {"type": "log_entry", "data": roll_log.model_dump()}

    judge_result = {
        "action": "roll",
        "tier": pending.tier,
        "stat": pending.stat,
        "targets": pending.targets,
    }
    body = ""
    final: NarrativeFinal | None = None
    async for item in run_narrate(
        client,
        state,
        profile_dir,
        pending.player_input,
        judge_result=judge_result,
        grade=grade,
        target_id=pending.target,
    ):
        if isinstance(item, NarrativeDelta):
            yield {"type": "narrative_delta", "data": {"text": item.text}}
            body += item.text
        else:
            final = item
    assert final is not None

    apply_changes(state, final.output.state_changes, dirty.entities)
    push_turn_log(state, pending.target, final.output.turn_summary, dirty)
    push_dialogue(state, pending.player_input, body, dirty)
    write_memories(state, final.output, turn=state.turn_count, dirty=dirty.entities)
    gm_log = GMLogEntry(id=next_log_id(state), kind="gm", text=body)
    push_log_entry(state, gm_log, dirty)

    state.pending_check = None
    advance_time(state)

    if state.combat_state is not None:
        # Environment rolls cost the player one combat turn — NPC phase resumes.
        combat_engine.advance_turn(state)
        async for ev in run_combat_npc_phase(state, dirty, rng):
            yield ev

    async for ev in finalize(state, saves_dir, dirty, to_front_fn):
        yield ev
