"""/turn — single entry that logs the input, then dispatches to combat or
non-combat handlers based on `state.combat_state`."""
import random
from collections.abc import AsyncIterator, Callable

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
from ..llm.client import LLMClient, set_llm_session_if_unset
from ..mapping.to_front import pending_check_to_front
from .actions import (
    emit_equip,
    emit_learn_skill,
    emit_level_up,
    emit_roll_pending,
    emit_trade,
    emit_unequip,
    emit_use,
)
from .combat_oneshot import arm_combat_roll_pending
from .combat_phase import run_combat_player_turn
from .encounter import summon_encounter
from .clock import tick_turn_buffs
from .dirty import (
    Dirty,
    ToFrontFn,
    finalize,
    next_log_id,
    push_act,
    push_log_entry,
)
from .judge import run_judge
from .narrate import apply_intended_move, consume_narrate, run_narrate
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
    set_llm_session_if_unset(state.game_id)
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
            "쓰러진 채로는 더 이상 움직이지 못합니다.",
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


# Each entry takes (client, state, dirty, action) and returns an event iterator
# for the engine action. Combat/Summon/Roll/Rest aren't here — they have
# bespoke pre/post handling and stay in `_dispatch`.
EmitFactory = Callable[[LLMClient, GameState, Dirty, object], AsyncIterator[dict]]
_ONE_STEP_EMITS: dict[type, EmitFactory] = {
    UseAction: lambda c, s, d, a: emit_use(s, s.player_id, a.item_id, a.target_id, d),
    EquipAction: lambda c, s, d, a: emit_equip(s, s.player_id, a.item_id, d),
    UnequipAction: lambda c, s, d, a: emit_unequip(s, s.player_id, a.item_id, d),
    LevelUpAction: lambda c, s, d, a: emit_level_up(s, s.player_id, a.stat_up, a.stat_down, c, d),
    LearnSkillAction: lambda c, s, d, a: emit_learn_skill(s, s.player_id, a.index, d),
    BuyAction: lambda c, s, d, a: emit_trade(s, s.player_id, a.npc_id, a.item_id, d, direction="buy"),
    SellAction: lambda c, s, d, a: emit_trade(s, s.player_id, a.npc_id, a.item_id, d, direction="sell"),
}


async def _run_one_step_action(
    client: LLMClient,
    state: GameState,
    saves_dir: str,
    dirty: Dirty,
    to_front_fn: ToFrontFn | None,
    result,
    emit_factory: EmitFactory,
) -> AsyncIterator[dict]:
    """turn_count++ → run the engine emit → push tail_intent → finalize.
    The seven one-step actions all follow this template."""
    state.turn_count += 1
    async for ev in emit_factory(client, state, dirty, result):
        yield ev
    if getattr(result, "tail_intent", None):
        yield push_act(state, dirty, result.tail_intent)
    tick_turn_buffs(state, dirty)
    async for ev in finalize(state, saves_dir, dirty, to_front_fn):
        yield ev


async def _arm_pending_and_finalize(
    state: GameState,
    saves_dir: str,
    dirty: Dirty,
    to_front_fn: ToFrontFn | None,
) -> AsyncIterator[dict]:
    """Emit the freshly-armed pending_check then finalize. Shared by the
    combat-roll and summon-then-combat-roll arming paths. The RollPrompt
    card on the client renders all the same data that an act-line would,
    so we don't push one here."""
    yield {
        "type": "pending_check",
        "data": pending_check_to_front(state, state.pending_check),
    }
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
            yield push_act(state, dirty, "공격할 수 있는 대상이 없습니다.")
            async for ev in finalize(state, saves_dir, dirty, to_front_fn):
                yield ev
            return
        arm_combat_roll_pending(
            state,
            target_ids=list(result.targets),
            player_input=player_input,
            skill_id=result.skill_id,
        )
        async for ev in _arm_pending_and_finalize(state, saves_dir, dirty, to_front_fn):
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
            yield push_act(state, dirty, "허공을 가르지만 적은 보이지 않습니다.")
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
        async for ev in _arm_pending_and_finalize(state, saves_dir, dirty, to_front_fn):
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

    if isinstance(result, FleeAction):
        # Out-of-combat flee — short message, no turn bump.
        yield push_act(state, dirty, "지금은 도망칠 전투가 없습니다.")
        async for ev in finalize(state, saves_dir, dirty, to_front_fn):
            yield ev
        return

    emit_factory = _ONE_STEP_EMITS.get(type(result))
    if emit_factory is not None:
        async for ev in _run_one_step_action(
            client, state, saves_dir, dirty, to_front_fn, result, emit_factory
        ):
            yield ev
        return

    if isinstance(result, ChainAction):
        state.turn_count += 1
        last_pass: PassAction | None = None
        for part in result.parts:
            if isinstance(part, PassAction):
                last_pass = part
                continue
            emit_factory = _ONE_STEP_EMITS.get(type(part))
            if emit_factory is not None:
                async for ev in emit_factory(client, state, dirty, part):
                    yield ev
            if getattr(part, "tail_intent", None):
                yield push_act(state, dirty, part.tail_intent)
        if last_pass is not None:
            async for ev in _stream_narrate_tail(
                client, state, profile_dir, player_input, dirty, to_front_fn, last_pass,
            ):
                yield ev
        tick_turn_buffs(state, dirty)
        async for ev in finalize(state, saves_dir, dirty, to_front_fn):
            yield ev
        return

    # action == pass / reject — narrator path.
    assert isinstance(result, (PassAction, RejectAction))
    state.turn_count += 1
    async for ev in _stream_narrate_tail(
        client, state, profile_dir, player_input, dirty, to_front_fn, result,
    ):
        yield ev
    tick_turn_buffs(state, dirty)
    async for ev in finalize(state, saves_dir, dirty, to_front_fn):
        yield ev


# --- shared narrate tail ---------------------------------------------------


async def _stream_narrate_tail(
    client: LLMClient,
    state: GameState,
    profile_dir: str,
    player_input: str,
    dirty: Dirty,
    to_front_fn: ToFrontFn | None,
    action: "PassAction | RejectAction",
) -> AsyncIterator[dict]:
    """Pre-apply movement (PassAction only), emit a panels state event, then
    drive run_narrate / consume_narrate. Used by both the ChainAction last_pass
    branch and the bottom PassAction/RejectAction tail — pre-narrate state
    emission lets the destination's surroundings appear in the prompt while
    the client's pill updates immediately. RejectAction has no movement intent
    so it skips apply_intended_move."""
    if isinstance(action, PassAction):
        target_for_log = action.targets[0] if action.targets else None
        apply_intended_move(state, action.model_dump(), dirty.entities)
    else:
        target_for_log = None

    if to_front_fn is not None:
        yield {"type": "state", "data": to_front_fn(state)}

    stream = run_narrate(
        client, state, profile_dir, player_input,
        judge_result=action.model_dump(),
        grade=None,
    )
    async for ev in consume_narrate(
        state, dirty, stream,
        target_for_log=target_for_log,
        dialogue_input=player_input,
    ):
        yield ev
