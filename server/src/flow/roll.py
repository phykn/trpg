"""/roll — resolve the pending stat check, narrate the outcome, and
re-enter the auto-combat loop if a fight was paused for an environment roll."""
import random
from collections.abc import AsyncIterator

from ..agents.combat_narrate import stream_combat_narrate
from ..domain.errors import PendingCheckExpected
from ..domain.memory import RollLogEntry
from ..domain.state import GameState
from ..engines.growth import grant_roll_xp
from ..llm.client import LLMClient, set_llm_session_if_unset
from ..rules.dc import compute_grade
from .clock import tick_turn_buffs
from .combat_auto import (
    PlayerAction,
    build_narrate_input,
    format_outcome_summary,
    run_auto_combat,
)
from .dirty import (
    Dirty,
    ToFrontFn,
    finalize,
    next_log_id,
    push_act,
    push_gm,
    push_log_entry,
)
from .format import (
    format_combat_end_text,
    front_grade,
)
from .narrate import consume_narrate, run_narrate
from ..mapping.to_front import stat_label


async def _resume_auto_combat(
    client: LLMClient,
    state: GameState,
    profile_dir: str,
    dirty: Dirty,
    rng: random.Random | None,
) -> AsyncIterator[dict]:
    """An environment roll inside combat costs the player their action for
    this fight. Drive an auto-cycle (player passes, NPCs continue) until the
    fight terminates."""
    result = run_auto_combat(
        state, dirty,
        player_action=PlayerAction(kind="pass"),
        rng=rng,
    )
    if client is not None:
        narrate_input = build_narrate_input(
            state, profile_dir,
            player_input="환경 굴림 후 한 박자 쉬며 적의 움직임을 살핍니다",
            result=result,
        )
        body_chunks: list[str] = []
        async for chunk in stream_combat_narrate(client, narrate_input):
            body_chunks.append(chunk)
            yield {"type": "narrative_delta", "data": {"text": chunk}}
        body = "".join(body_chunks).strip()
        if body:
            yield push_gm(state, dirty, body)

    summary = format_outcome_summary(result)
    if summary:
        yield push_act(state, dirty, summary)

    end_label = "defeat" if result.outcome == "downed" else result.outcome
    yield push_act(state, dirty, format_combat_end_text(end_label))
    yield {"type": "combat_end", "data": {"outcome": result.outcome}}


async def run_roll(
    client: LLMClient,
    state: GameState,
    profile_dir: str,
    saves_dir: str,
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

    roll_log = RollLogEntry(
        id=next_log_id(state),
        kind="roll",
        check=stat_label(pending.stat),
        roll=dice,
        margin=total - pending.required_roll,
        result=front_grade(grade),
    )
    push_log_entry(state, roll_log, dirty)
    yield {"type": "log_entry", "data": roll_log.model_dump()}

    grant_roll_xp(state, grade, dirty=dirty.entities)

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
    tick_turn_buffs(state, dirty)

    if state.combat_state is not None:
        async for ev in _resume_auto_combat(client, state, profile_dir, dirty, rng):
            yield ev

    async for ev in finalize(state, saves_dir, dirty, to_front_fn):
        yield ev
