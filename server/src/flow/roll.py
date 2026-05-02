"""/roll — resolve the pending stat check, narrate the outcome, and
re-enter the auto-combat loop if a fight was paused for an environment roll."""

import random
from collections.abc import AsyncIterator

from ..domain.errors import PendingCheckExpected
from ..domain.memory import RollLogEntry
from ..domain.state import GameState
from ..engines.growth import grant_roll_xp
from ..llm.client import LLMClient, set_llm_session_if_unset
from ..persistence.repo import SaveRepo, ScenarioRepo
from ..rules.dc import compute_grade
from .buff_tick import tick_turn_buffs
from .combat_auto import PlayerAction, run_auto_combat
from .combat_phase import emit_combat_cinematic_and_end
from .dirty import (
    Dirty,
    ToFrontFn,
    finalize,
    next_log_id,
    push_log_entry,
)
from .format import front_grade
from .narrate import consume_narrate, run_narrate
from ..mapping.to_front import stat_label


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
        player_input="환경 굴림 후 한 박자 쉬며 적의 움직임을 살핍니다",
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
    tick_turn_buffs(state, dirty)

    if state.combat_state is not None:
        async for ev in _resume_auto_combat(client, state, scenario_repo, dirty, rng):
            yield ev

    async for ev in finalize(state, save_repo, dirty, to_front_fn):
        yield ev
