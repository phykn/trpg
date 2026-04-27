"""/turn — single entry that logs the input, then dispatches to combat or
non-combat handlers based on `state.combat_state`."""
import random
from collections.abc import AsyncIterator

from ..agents.dc_judge.schema import (
    BuyAction,
    ClarifyAction,
    CombatAction,
    EquipAction,
    FleeAction,
    LearnSkillAction,
    LevelUpAction,
    PassAction,
    RejectAction,
    RestAction,
    RollAction,
    SellAction,
    UnequipAction,
    UseAction,
)
from ..domain.errors import JudgeMalformed, PendingCheckActive
from ..domain.memory import PlayerLogEntry
from ..domain.state import GameState
from ..engines import combat as combat_engine
from ..llm.client import LLMClient
from .actions import (
    emit_equip,
    emit_learn_skill,
    emit_level_up,
    emit_roll_pending,
    emit_skill_cast,
    emit_trade,
    emit_unequip,
    emit_use,
)
from .combat_phase import (
    run_combat_npc_phase,
    run_combat_player_turn,
    start_combat_and_run_npc_phase,
)
from .dirty import (
    Dirty,
    ToFrontFn,
    advance_time,
    finalize,
    next_log_id,
    push_act,
    push_log_entry,
)
from .judge import run_judge
from .narrate import consume_narrate, run_narrate
from .rest import run_rest


async def run_turn(
    client: LLMClient,
    state: GameState,
    profile_dir: str,
    saves_dir: str,
    player_input: str,
    *,
    to_front_fn: ToFrontFn | None = None,
    rng: random.Random | None = None,
) -> AsyncIterator[dict]:
    if state.pending_check is not None:
        raise PendingCheckActive(
            "a pending_check is already active; call /roll instead"
        )

    dirty = Dirty()

    player_log = PlayerLogEntry(
        id=next_log_id(state), kind="player", text=player_input
    )
    push_log_entry(state, player_log, dirty)
    yield {"type": "log_entry", "data": player_log.model_dump()}

    if state.combat_state is not None:
        async for ev in run_combat_player_turn(
            client, state, profile_dir, saves_dir, player_input, dirty, rng, to_front_fn
        ):
            yield ev
        return

    try:
        result = await run_judge(client, state, player_input)
    except JudgeMalformed as e:
        yield {"type": "error", "data": {"message": str(e), "code": "JudgeMalformed"}}
        return

    yield {"type": "judge", "data": result.model_dump()}

    async for ev in _dispatch(
        client, state, profile_dir, saves_dir, player_input, dirty, rng, to_front_fn, result
    ):
        yield ev


# --- non-combat dispatch ---------------------------------------------------


async def _bump_and_finalize(
    state: GameState,
    saves_dir: str,
    dirty: Dirty,
    to_front_fn: ToFrontFn | None,
) -> AsyncIterator[dict]:
    """Common tail for one-step actions that consume a turn (use/equip/level_up/etc)."""
    advance_time(state)
    async for ev in finalize(state, saves_dir, dirty, to_front_fn):
        yield ev


async def _dispatch(
    client: LLMClient,
    state: GameState,
    profile_dir: str,
    saves_dir: str,
    player_input: str,
    dirty: Dirty,
    rng: random.Random | None,
    to_front_fn: ToFrontFn | None,
    result,
) -> AsyncIterator[dict]:
    if not isinstance(result, ClarifyAction):
        state.clarify_streak = 0

    if isinstance(result, CombatAction):
        actor_loc = state.characters[state.player_id].location_id
        invalid_targets = [
            t for t in result.targets
            if t == state.player_id
            or t not in state.characters
            or not state.characters[t].alive
            or state.characters[t].location_id != actor_loc
        ]
        if invalid_targets:
            yield push_act(state, dirty, "공격할 수 있는 대상이 없다.")
            async for ev in finalize(state, saves_dir, dirty, to_front_fn):
                yield ev
            return
        state.turn_count += 1
        async for ev in start_combat_and_run_npc_phase(
            state, list(result.targets), dirty, rng
        ):
            yield ev
        # If the input matched a skill, spend the player's first turn on cast.
        if result.skill_id and state.combat_state is not None:
            async for ev in emit_skill_cast(
                state, state.player_id, result.skill_id, list(result.targets), dirty, rng=rng
            ):
                yield ev
            combat_engine.advance_turn(state)
            async for ev in run_combat_npc_phase(state, dirty, rng):
                yield ev
        async for ev in _bump_and_finalize(state, saves_dir, dirty, to_front_fn):
            yield ev
        return

    if isinstance(result, ClarifyAction):
        state.clarify_streak += 1
        if state.clarify_streak >= 3:
            yield push_act(
                state,
                dirty,
                "이번 시도는 어떤 행동인지 잡히지 않아 흐릿하게 지나간다. 한 가지 행동을 구체적으로 정해 다시 시도하라.",
            )
            state.clarify_streak = 0
            state.turn_count += 1
            async for ev in _bump_and_finalize(state, saves_dir, dirty, to_front_fn):
                yield ev
            return
        yield push_act(state, dirty, result.question)
        async for ev in finalize(state, saves_dir, dirty, to_front_fn):
            yield ev
        return

    if isinstance(result, RollAction):
        async for ev in emit_roll_pending(state, saves_dir, player_input, result, dirty):
            yield ev
        return  # /roll resumes the flow.

    if isinstance(result, RestAction):
        async for ev in run_rest(
            state, profile_dir, saves_dir, dirty, rng, to_front_fn, client=client
        ):
            yield ev
        return

    if isinstance(result, UseAction):
        state.turn_count += 1
        async for ev in emit_use(
            state, state.player_id, result.item_id, result.target_id, dirty
        ):
            yield ev
        async for ev in _bump_and_finalize(state, saves_dir, dirty, to_front_fn):
            yield ev
        return

    if isinstance(result, EquipAction):
        state.turn_count += 1
        async for ev in emit_equip(state, state.player_id, result.item_id, dirty):
            yield ev
        async for ev in _bump_and_finalize(state, saves_dir, dirty, to_front_fn):
            yield ev
        return

    if isinstance(result, UnequipAction):
        state.turn_count += 1
        async for ev in emit_unequip(state, state.player_id, result.item_id, dirty):
            yield ev
        async for ev in _bump_and_finalize(state, saves_dir, dirty, to_front_fn):
            yield ev
        return

    if isinstance(result, FleeAction):
        # Out-of-combat flee — short message, no turn bump.
        yield push_act(state, dirty, "지금은 도망쳐 달아날 전투가 없다.")
        async for ev in finalize(state, saves_dir, dirty, to_front_fn):
            yield ev
        return

    if isinstance(result, LevelUpAction):
        state.turn_count += 1
        async for ev in emit_level_up(
            state, state.player_id, result.stat_up, result.stat_down, client, dirty
        ):
            yield ev
        async for ev in _bump_and_finalize(state, saves_dir, dirty, to_front_fn):
            yield ev
        return

    if isinstance(result, LearnSkillAction):
        state.turn_count += 1
        async for ev in emit_learn_skill(state, state.player_id, result.index, dirty):
            yield ev
        async for ev in _bump_and_finalize(state, saves_dir, dirty, to_front_fn):
            yield ev
        return

    if isinstance(result, BuyAction):
        state.turn_count += 1
        async for ev in emit_trade(
            state, state.player_id, result.npc_id, result.item_id, dirty, direction="buy"
        ):
            yield ev
        async for ev in _bump_and_finalize(state, saves_dir, dirty, to_front_fn):
            yield ev
        return

    if isinstance(result, SellAction):
        state.turn_count += 1
        async for ev in emit_trade(
            state, state.player_id, result.npc_id, result.item_id, dirty, direction="sell"
        ):
            yield ev
        async for ev in _bump_and_finalize(state, saves_dir, dirty, to_front_fn):
            yield ev
        return

    # action == pass / reject — narrator path.
    assert isinstance(result, (PassAction, RejectAction))
    state.turn_count += 1
    targets_for_log = getattr(result, "targets", None)
    target_for_log = targets_for_log[0] if targets_for_log else None

    stream = run_narrate(
        client,
        state,
        profile_dir,
        player_input,
        judge_result=result.model_dump(),
        grade=None,
    )
    async for ev in consume_narrate(
        state,
        dirty,
        stream,
        target_for_log=target_for_log,
        dialogue_input=player_input,
    ):
        yield ev

    async for ev in _bump_and_finalize(state, saves_dir, dirty, to_front_fn):
        yield ev
