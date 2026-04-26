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
from ..agents.narrate import NarrativeDelta, NarrativeFinal
from ..domain.errors import JudgeMalformed, PendingCheckActive
from ..domain.memory import ActLogEntry, GMLogEntry, PlayerLogEntry
from ..domain.state import GameState
from ..engines import combat as combat_engine
from ..engines.apply import apply_changes
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
    push_dialogue,
    push_log_entry,
    push_turn_log,
)
from .judge import run_judge
from .memory_writer import write_memories
from .narrate import run_narrate
from .rest import run_rest


def _push_act(state: GameState, dirty: Dirty, text: str) -> dict:
    log = ActLogEntry(id=next_log_id(state), kind="act", text=text)
    push_log_entry(state, log, dirty)
    return {"type": "log_entry", "data": log.model_dump()}


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
    if isinstance(result, CombatAction):
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
        yield _push_act(state, dirty, result.question)
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
        yield _push_act(state, dirty, "지금은 도망쳐 달아날 전투가 없다.")
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

    body = ""
    final: NarrativeFinal | None = None
    async for item in run_narrate(
        client,
        state,
        profile_dir,
        player_input,
        judge_result=result.model_dump(),
        grade=None,
    ):
        if isinstance(item, NarrativeDelta):
            yield {"type": "narrative_delta", "data": {"text": item.text}}
            body += item.text
        else:
            final = item
    assert final is not None

    apply_changes(state, final.output.state_changes, dirty.entities)
    push_turn_log(state, target_for_log, final.output.turn_summary, dirty)
    push_dialogue(state, player_input, body, dirty)
    write_memories(state, final.output, turn=state.turn_count, dirty=dirty.entities)
    gm_log = GMLogEntry(id=next_log_id(state), kind="gm", text=body)
    push_log_entry(state, gm_log, dirty)

    async for ev in _bump_and_finalize(state, saves_dir, dirty, to_front_fn):
        yield ev
