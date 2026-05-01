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
from ..domain.entities import Character
from ..domain.errors import JudgeMalformed, PendingCheckActive
from ..domain.memory import PlayerLogEntry
from ..domain.state import GameState
from ..llm.client import LLMClient, set_llm_session_if_unset
from ..ontology.graph import GameGraph, build_graph
from .actions import (
    emit_equip,
    emit_learn_skill,
    emit_level_up,
    emit_roll_pending,
    emit_trade,
    emit_unequip,
    emit_use,
)
from .combat_auto import PlayerAction
from .combat_phase import (
    has_invalid_combat_targets,
    run_combat_player_turn,
    start_combat_and_drive_auto,
)
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
from .subject import reconcile_subject_after_move, refresh_active_subject


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

    player_log = PlayerLogEntry(id=next_log_id(state), kind="player", text=player_input)
    push_log_entry(state, player_log, dirty)
    yield {"type": "log_entry", "data": player_log.model_dump()}

    if not state.characters[state.player_id].alive:
        yield push_act(
            state,
            dirty,
            "당신의 이야기가 여기서 끝납니다.",
        )
        async for ev in finalize(state, saves_dir, dirty, to_front_fn):
            yield ev
        return

    graph = build_graph(state)

    if state.combat_state is not None:
        async for ev in run_combat_player_turn(
            client,
            state,
            profile_dir,
            saves_dir,
            player_input,
            dirty,
            rng,
            to_front_fn,
            graph=graph,
        ):
            yield ev
        return

    try:
        result = await run_judge(client, state, player_input, graph=graph)
    except JudgeMalformed as e:
        yield {"type": "error", "data": {"message": str(e), "code": "JudgeMalformed"}}
        return

    yield {"type": "judge", "data": result.model_dump()}

    refresh_active_subject(state, result)

    async for ev in _dispatch(
        client,
        state,
        profile_dir,
        saves_dir,
        player_input,
        dirty,
        rng,
        to_front_fn,
        result,
        graph=graph,
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
    LevelUpAction: lambda c, s, d, a: emit_level_up(
        s, s.player_id, a.stat_up, a.stat_down, c, d
    ),
    LearnSkillAction: lambda c, s, d, a: emit_learn_skill(s, s.player_id, a.index, d),
    BuyAction: lambda c, s, d, a: emit_trade(
        s, s.player_id, a.npc_id, a.item_id, d, direction="buy"
    ),
    SellAction: lambda c, s, d, a: emit_trade(
        s, s.player_id, a.npc_id, a.item_id, d, direction="sell"
    ),
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


async def _enter_combat_and_finalize(
    client: LLMClient,
    state: GameState,
    profile_dir: str,
    saves_dir: str,
    dirty: Dirty,
    rng: random.Random | None,
    to_front_fn: ToFrontFn | None,
    *,
    player_input: str,
    enemy_ids: list[str],
    skill_id: str | None,
    graph: GameGraph,
) -> AsyncIterator[dict]:
    """Start a fresh fight and run one auto-combat sim cycle, then finalize.
    Shared by CombatAction and SummonCombatAction entries."""
    player_action = PlayerAction(
        kind="skill" if skill_id else "attack",
        skill_id=skill_id,
        targets=list(enemy_ids),
    )
    async for ev in start_combat_and_drive_auto(
        client,
        state,
        profile_dir,
        enemy_ids,
        dirty,
        rng,
        player_input=player_input,
        player_action=player_action,
        graph=graph,
    ):
        yield ev
    state.turn_count += 1
    tick_turn_buffs(state, dirty)
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
    *,
    graph: GameGraph,
) -> AsyncIterator[dict]:
    if isinstance(result, CombatAction):
        if has_invalid_combat_targets(state, result.targets):
            yield push_act(state, dirty, "공격할 수 있는 대상이 없습니다.")
            async for ev in finalize(state, saves_dir, dirty, to_front_fn):
                yield ev
            return
        async for ev in _enter_combat_and_finalize(
            client,
            state,
            profile_dir,
            saves_dir,
            dirty,
            rng,
            to_front_fn,
            player_input=player_input,
            enemy_ids=list(result.targets),
            skill_id=result.skill_id,
            graph=graph,
        ):
            yield ev
        return

    if isinstance(result, SummonCombatAction):
        actor = state.characters[state.player_id]
        location = state.locations.get(actor.location_id) if actor.location_id else None
        summoned = None
        if location is not None and client is not None:
            try:
                summoned = await summon_encounter(
                    client,
                    state,
                    location,
                    profile_dir,
                    state.profile,
                    dirty=dirty.entities,
                    requested_role=result.role,
                )
            except Exception:
                summoned = None
        if summoned is None:
            yield push_act(state, dirty, "허공을 가르지만 적은 보이지 않습니다.")
            async for ev in finalize(state, saves_dir, dirty, to_front_fn):
                yield ev
            return
        state.active_subject_id = summoned.id
        # summon_encounter mutated state — rebuild graph so the new NPC's
        # located_at edge is visible to anything downstream.
        graph = build_graph(state)
        async for ev in _enter_combat_and_finalize(
            client,
            state,
            profile_dir,
            saves_dir,
            dirty,
            rng,
            to_front_fn,
            player_input=player_input,
            enemy_ids=[summoned.id],
            skill_id=result.skill_id,
            graph=graph,
        ):
            yield ev
        return

    if isinstance(result, RollAction):
        async for ev in emit_roll_pending(
            state, saves_dir, player_input, result, dirty
        ):
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
            # chain parts mutated state via emit_*; rebuild graph before narrate
            # reads relations through it.
            graph = build_graph(state)
            async for ev in _stream_narrate_tail(
                client,
                state,
                profile_dir,
                player_input,
                dirty,
                to_front_fn,
                last_pass,
                graph=graph,
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
        client,
        state,
        profile_dir,
        player_input,
        dirty,
        to_front_fn,
        result,
        graph=graph,
    ):
        yield ev
    tick_turn_buffs(state, dirty)
    async for ev in finalize(state, saves_dir, dirty, to_front_fn):
        yield ev


# --- shared narrate tail ---------------------------------------------------


_CORPSE_BYPASS_BODY = "죽은 자는 말이 없습니다."


async def _stream_narrate_tail(
    client: LLMClient,
    state: GameState,
    profile_dir: str,
    player_input: str,
    dirty: Dirty,
    to_front_fn: ToFrontFn | None,
    action: "PassAction | RejectAction",
    *,
    graph: GameGraph,
) -> AsyncIterator[dict]:
    """Pre-apply movement (PassAction only), emit a panels state event, then
    drive run_narrate / consume_narrate. Used by both the ChainAction last_pass
    branch and the bottom PassAction/RejectAction tail — pre-narrate state
    emission lets the destination's surroundings appear in the prompt while
    the client's pill updates immediately. RejectAction has no movement intent
    so it skips apply_intended_move.

    Graph plumbing: caller passes the turn-start graph. If `apply_intended_move`
    relocates the player, the graph's `located_at` edges go stale, so we
    rebuild before run_narrate consumes it.

    Corpse bypass: when a PassAction targets a dead character, narrate is
    skipped entirely and a deterministic single-line body is emitted. No LLM
    in the loop = no chance of resurrected speech, regardless of how the
    model would have phrased it (`「…」`, indirect report, pronoun chain,
    ambient mention — all moot). Quote-redaction in `consume_narrate` /
    `build_history_layer` stays as a 2nd line for the case where the corpse
    is in the scene but the action targets a live NPC and the LLM still
    tries to put words in the dead one's mouth.
    """
    if isinstance(action, PassAction):
        target_for_log = action.targets[0] if action.targets else None
        prev_loc = state.characters[state.player_id].location_id
        apply_intended_move(state, action.model_dump(), dirty.entities)
        reconcile_subject_after_move(state)
        if state.characters[state.player_id].location_id != prev_loc:
            graph = build_graph(state)

        dead = next(
            (
                state.characters[t]
                for t in action.targets
                if t in state.characters and not state.characters[t].alive
            ),
            None,
        )
        if dead is not None:
            async for ev in _emit_corpse_bypass(
                state,
                dirty,
                player_input,
                dead,
                target_for_log,
                to_front_fn,
            ):
                yield ev
            return
    else:
        target_for_log = None

    if to_front_fn is not None:
        yield {"type": "state", "data": to_front_fn(state)}

    stream = run_narrate(
        client,
        state,
        profile_dir,
        player_input,
        judge_result=action.model_dump(),
        graph=graph,
        grade=None,
    )
    async for ev in consume_narrate(
        state,
        dirty,
        stream,
        target_for_log=target_for_log,
        dialogue_input=player_input,
        graph=graph,
    ):
        yield ev


async def _emit_corpse_bypass(
    state: GameState,
    dirty: Dirty,
    player_input: str,
    dead: Character,
    target_for_log: str | None,
    to_front_fn: ToFrontFn | None,
) -> AsyncIterator[dict]:
    """Skip narrate entirely for a dead-target pass: emit panel state, stream
    one deterministic narrative_delta, push the per-turn tail (turn_log /
    dialogue / GM log_entry). Mirrors `consume_narrate`'s persistence steps
    but with no LLM call and no state_changes."""
    from ..domain.memory import GMLogEntry  # local import to avoid cycle
    from .dirty import next_log_id, push_dialogue, push_log_entry, push_turn_log

    if to_front_fn is not None:
        yield {"type": "state", "data": to_front_fn(state)}

    body = _CORPSE_BYPASS_BODY
    yield {"type": "narrative_delta", "data": {"text": body}}
    yield {"type": "suggestions", "data": {"items": []}}

    push_turn_log(state, target_for_log, f"{dead.name}의 시신과 마주함", dirty)
    push_dialogue(state, player_input, body, dirty)
    gm_log = GMLogEntry(id=next_log_id(state), kind="gm", text=body)
    push_log_entry(state, gm_log, dirty)
