"""/turn — single entry that logs the input, then dispatches to combat or
non-combat handlers based on `state.combat_state`."""
import random
from collections.abc import AsyncIterator

from ..agents.dc_judge.schema import (
    BuyAction,
    ChainAction,
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
    SummonCombatAction,
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
from .cinematic import arm_combat_roll_pending
from .combat_phase import (
    run_combat_npc_phase,
    run_combat_player_turn,
    start_combat_and_run_npc_phase,
)
from .encounter import summon_encounter
from .dirty import (
    Dirty,
    ToFrontFn,
    advance_time,
    finalize,
    next_log_id,
    push_act,
    push_gm,
    push_log_entry,
    push_turn_log,
)
from .judge import run_judge
from .narrate import consume_narrate, run_narrate
from .rest import run_rest
from .subject import refresh_active_subject


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

    if not state.characters[state.player_id].alive:
        yield push_act(
            state, dirty,
            "쓰러진 채로는 더 이상 행동할 수 없다.",
        )
        async for ev in finalize(state, saves_dir, dirty, to_front_fn):
            yield ev
        return

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

    refresh_active_subject(state, result)

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


async def _emit_chain_engine_part(
    client: LLMClient,
    state: GameState,
    dirty: Dirty,
    part,
) -> AsyncIterator[dict]:
    """Emit one engine part of a ChainAction. No turn bump or finalize —
    the chain dispatcher does those once at the end."""
    if isinstance(part, UseAction):
        async for ev in emit_use(
            state, state.player_id, part.item_id, part.target_id, dirty
        ):
            yield ev
    elif isinstance(part, EquipAction):
        async for ev in emit_equip(state, state.player_id, part.item_id, dirty):
            yield ev
    elif isinstance(part, UnequipAction):
        async for ev in emit_unequip(state, state.player_id, part.item_id, dirty):
            yield ev
    elif isinstance(part, BuyAction):
        async for ev in emit_trade(
            state, state.player_id, part.npc_id, part.item_id, dirty, direction="buy"
        ):
            yield ev
    elif isinstance(part, SellAction):
        async for ev in emit_trade(
            state, state.player_id, part.npc_id, part.item_id, dirty, direction="sell"
        ):
            yield ev
    elif isinstance(part, LevelUpAction):
        async for ev in emit_level_up(
            state, state.player_id, part.stat_up, part.stat_down, client, dirty
        ):
            yield ev
    elif isinstance(part, LearnSkillAction):
        async for ev in emit_learn_skill(state, state.player_id, part.index, dirty):
            yield ev
    if getattr(part, "tail_intent", None):
        yield push_gm(state, dirty, part.tail_intent)


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
        arm_combat_roll_pending(
            state,
            target_ids=list(result.targets),
            player_input=player_input,
            skill_id=result.skill_id,
        )
        from ..mapping.to_front import pending_check_to_front
        yield {
            "type": "pending_check",
            "data": pending_check_to_front(state.pending_check),
        }
        async for ev in finalize(state, saves_dir, dirty, to_front_fn):
            yield ev
        return

    if isinstance(result, SummonCombatAction):
        actor = state.characters[state.player_id]
        location = state.locations.get(actor.location_id) if actor.location_id else None
        summoned = None
        if location is not None and client is not None:
            try:
                summoned = await summon_encounter(
                    client, state, location, profile_dir, state.profile,
                    dirty=dirty.entities, requested_role=result.role,
                )
            except Exception:
                summoned = None
        if summoned is None:
            yield push_act(state, dirty, "허공을 가르지만 적은 보이지 않는다.")
            async for ev in finalize(state, saves_dir, dirty, to_front_fn):
                yield ev
            return
        state.active_subject_id = summoned.id
        arm_combat_roll_pending(
            state,
            target_ids=[summoned.id],
            player_input=player_input,
            skill_id=result.skill_id,
        )
        from ..mapping.to_front import pending_check_to_front
        yield {
            "type": "pending_check",
            "data": pending_check_to_front(state.pending_check),
        }
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
        if result.tail_intent:
            yield push_gm(state, dirty, result.tail_intent)
        async for ev in _bump_and_finalize(state, saves_dir, dirty, to_front_fn):
            yield ev
        return

    if isinstance(result, EquipAction):
        state.turn_count += 1
        async for ev in emit_equip(state, state.player_id, result.item_id, dirty):
            yield ev
        if result.tail_intent:
            yield push_gm(state, dirty, result.tail_intent)
        async for ev in _bump_and_finalize(state, saves_dir, dirty, to_front_fn):
            yield ev
        return

    if isinstance(result, UnequipAction):
        state.turn_count += 1
        async for ev in emit_unequip(state, state.player_id, result.item_id, dirty):
            yield ev
        if result.tail_intent:
            yield push_gm(state, dirty, result.tail_intent)
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
        if result.tail_intent:
            yield push_gm(state, dirty, result.tail_intent)
        async for ev in _bump_and_finalize(state, saves_dir, dirty, to_front_fn):
            yield ev
        return

    if isinstance(result, LearnSkillAction):
        state.turn_count += 1
        async for ev in emit_learn_skill(state, state.player_id, result.index, dirty):
            yield ev
        if result.tail_intent:
            yield push_gm(state, dirty, result.tail_intent)
        async for ev in _bump_and_finalize(state, saves_dir, dirty, to_front_fn):
            yield ev
        return

    if isinstance(result, BuyAction):
        state.turn_count += 1
        async for ev in emit_trade(
            state, state.player_id, result.npc_id, result.item_id, dirty, direction="buy"
        ):
            yield ev
        if result.tail_intent:
            yield push_gm(state, dirty, result.tail_intent)
        async for ev in _bump_and_finalize(state, saves_dir, dirty, to_front_fn):
            yield ev
        return

    if isinstance(result, SellAction):
        state.turn_count += 1
        async for ev in emit_trade(
            state, state.player_id, result.npc_id, result.item_id, dirty, direction="sell"
        ):
            yield ev
        if result.tail_intent:
            yield push_gm(state, dirty, result.tail_intent)
        async for ev in _bump_and_finalize(state, saves_dir, dirty, to_front_fn):
            yield ev
        return

    if isinstance(result, ChainAction):
        state.turn_count += 1
        last_pass: PassAction | None = None
        for part in result.parts:
            if isinstance(part, PassAction):
                last_pass = part
                continue
            async for ev in _emit_chain_engine_part(client, state, dirty, part):
                yield ev
        if last_pass is not None:
            target_for_log = last_pass.targets[0] if last_pass.targets else None
            stream = run_narrate(
                client, state, profile_dir, player_input,
                judge_result=last_pass.model_dump(),
                grade=None,
            )
            async for ev in consume_narrate(
                state, dirty, stream,
                target_for_log=target_for_log,
                dialogue_input=player_input,
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
