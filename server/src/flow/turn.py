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
from ..ontology.queries import location_of
from ..persistence.repo import SaveRepo, ScenarioRepo
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
from .error_phrases import humanize_runtime_error
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
    scenario_repo: ScenarioRepo,
    save_repo: SaveRepo,
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
        async for ev in finalize(state, save_repo, dirty, to_front_fn):
            yield ev
        return

    # Consume the one-shot phase signal at turn entry. If a narrate-emitting
    # branch runs below, it sees the signal once; combat re-entry skips the
    # signal entirely (combat_narrate handles its own opening). Either way
    # the marker is cleared before this turn's finalize, so it can't echo.
    previous_phase_signal = state.previous_phase_signal
    state.previous_phase_signal = None

    graph = state.graph()

    if state.combat_state is not None:
        async for ev in run_combat_player_turn(
            client,
            state,
            scenario_repo,
            save_repo,
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
        yield {
            "type": "error",
            "data": {
                "message": humanize_runtime_error(e),
                "code": "JudgeMalformed",
            },
        }
        return

    yield {"type": "judge", "data": result.model_dump()}

    refresh_active_subject(state, result)

    async for ev in _dispatch(
        client,
        state,
        scenario_repo,
        save_repo,
        player_input,
        dirty,
        rng,
        to_front_fn,
        result,
        graph=graph,
        previous_phase_signal=previous_phase_signal,
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


def _drop_pushed_act(state: GameState, dirty: Dirty, entry_id: int | None) -> None:
    """Remove the act log entry just emitted by `push_act` from both the
    in-memory state.log_entries tail and the to-flush dirty.log slice.

    Called from `_run_one_step_action` and the chain dispatch when the
    act line is being absorbed into narrate's prose — without this, a
    `state` SSE refresh or the per-turn persistence flush would still
    surface the system-toned line ("주인공이 「X」을 장비했습니다.")
    next to narrate's body, defeating the absorption.
    """
    if entry_id is None:
        return
    state.log_entries[:] = [
        e for e in state.log_entries if getattr(e, "id", None) != entry_id
    ]
    dirty.log[:] = [e for e in dirty.log if getattr(e, "id", None) != entry_id]


async def _run_one_step_action(
    client: LLMClient,
    state: GameState,
    scenario_repo: ScenarioRepo,
    save_repo: SaveRepo,
    dirty: Dirty,
    to_front_fn: ToFrontFn | None,
    player_input: str,
    result,
    emit_factory: EmitFactory,
) -> AsyncIterator[dict]:
    """turn_count++ → run the engine emit (act lines absorbed, not streamed)
    → narrate tail (treats it like a chain's last_pass) → finalize.

    The act log lines emitted by `emit_*` carry engine-side facts ("주인공이
    「X」을 장비했습니다.", "이미 체력이 가득합니다.") that we don't want
    surfacing as system-toned chrome — they're persisted to turn_log/history
    for narrate context but the SSE is suppressed so the client only renders
    narrate's prose. Narrate then absorbs the same lines via `act_log_lines`
    so the body reflects whatever the engine actually did."""
    state.turn_count += 1
    act_log_lines: list[str] = []
    async for ev in emit_factory(client, state, dirty, result):
        if ev.get("type") == "log_entry":
            data = ev.get("data") or {}
            if data.get("kind") == "act":
                text = data.get("text") or ""
                if text:
                    act_log_lines.append(text)
                # Drop the just-pushed entry from both `state.log_entries`
                # and `dirty.log` so the next `state` SSE / persistence
                # flush doesn't resurface it. narrate body now carries the
                # same fact in prose.
                _drop_pushed_act(state, dirty, data.get("id"))
                continue  # suppress SSE — narrate body covers it
        yield ev
    if getattr(result, "tail_intent", None):
        # tail_intent goes into act_log_lines for narrate to absorb but is
        # not pushed as its own log entry — same suppression as the emit_*
        # act lines above.
        act_log_lines.append(result.tail_intent)

    # emit_* mutated state (inventory, equipment, …); rebuild graph so
    # narrate reads relations from the post-action snapshot.
    state.invalidate_graph()
    graph = state.graph()
    fake_pass = PassAction(action="pass")
    async for ev in _stream_narrate_tail(
        client,
        state,
        scenario_repo,
        player_input,
        dirty,
        to_front_fn,
        fake_pass,
        graph=graph,
        act_log_lines=act_log_lines,
    ):
        yield ev

    tick_turn_buffs(state, dirty)
    async for ev in finalize(state, save_repo, dirty, to_front_fn):
        yield ev


async def _enter_combat_and_finalize(
    client: LLMClient,
    state: GameState,
    scenario_repo: ScenarioRepo,
    save_repo: SaveRepo,
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
        scenario_repo,
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
    async for ev in finalize(state, save_repo, dirty, to_front_fn):
        yield ev


async def _dispatch(
    client: LLMClient,
    state: GameState,
    scenario_repo: ScenarioRepo,
    save_repo: SaveRepo,
    player_input: str,
    dirty: Dirty,
    rng: random.Random | None,
    to_front_fn: ToFrontFn | None,
    result,
    *,
    graph: GameGraph,
    previous_phase_signal: str | None = None,
) -> AsyncIterator[dict]:
    if isinstance(result, CombatAction):
        if has_invalid_combat_targets(state, graph, result.targets):
            yield push_act(state, dirty, "공격할 수 있는 대상이 없습니다.")
            async for ev in finalize(state, save_repo, dirty, to_front_fn):
                yield ev
            return
        async for ev in _enter_combat_and_finalize(
            client,
            state,
            scenario_repo,
            save_repo,
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
        loc_id = location_of(graph, state.player_id)
        location = state.locations.get(loc_id) if loc_id else None
        summoned = None
        if location is not None and client is not None:
            try:
                summoned = await summon_encounter(
                    client,
                    state,
                    location,
                    scenario_repo,
                    state.profile,
                    dirty=dirty.entities,
                    requested_role=result.role,
                )
            except Exception:
                summoned = None
        if summoned is None:
            yield push_act(state, dirty, "허공을 가르지만 적은 보이지 않습니다.")
            async for ev in finalize(state, save_repo, dirty, to_front_fn):
                yield ev
            return
        state.active_subject_id = summoned.id
        # summon_encounter mutated state — rebuild graph so the new NPC's
        # located_at edge is visible to anything downstream.
        state.invalidate_graph()
        graph = state.graph()
        async for ev in _enter_combat_and_finalize(
            client,
            state,
            scenario_repo,
            save_repo,
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
            state, save_repo, player_input, result, dirty
        ):
            yield ev
        return  # /roll resumes the flow.

    if isinstance(result, RestAction):
        async for ev in run_rest(
            state, scenario_repo, save_repo, dirty, rng, to_front_fn, client=client
        ):
            yield ev
        return

    if isinstance(result, FleeAction):
        # Out-of-combat flee — short message, no turn bump.
        yield push_act(state, dirty, "지금은 도망칠 전투가 없습니다.")
        async for ev in finalize(state, save_repo, dirty, to_front_fn):
            yield ev
        return

    emit_factory = _ONE_STEP_EMITS.get(type(result))
    if emit_factory is not None:
        async for ev in _run_one_step_action(
            client,
            state,
            scenario_repo,
            save_repo,
            dirty,
            to_front_fn,
            player_input,
            result,
            emit_factory,
        ):
            yield ev
        return

    if isinstance(result, ChainAction):
        state.turn_count += 1
        last_pass: PassAction | None = None
        # Collect engine notices ("이미 체력 가득", "거래 시도했지만 금화 부족"
        # …) emitted by non-final chain parts so the narrate tail can reflect
        # them in prose. Without this, narrate sees only the player_input
        # ("약초 먹고 검 든다") and the final pass; if the heal silently
        # skipped at the engine layer, the body still describes a heal.
        # The act log SSE itself is suppressed — narrate body covers the
        # same fact in prose, so two side-by-side renders of the same event
        # (system-toned line + narrate paragraph) are avoided.
        chain_act_lines: list[str] = []
        for part in result.parts:
            if isinstance(part, PassAction):
                last_pass = part
                continue
            emit_factory = _ONE_STEP_EMITS.get(type(part))
            if emit_factory is not None:
                async for ev in emit_factory(client, state, dirty, part):
                    if ev.get("type") == "log_entry":
                        d = ev.get("data") or {}
                        if d.get("kind") == "act":
                            text = d.get("text") or ""
                            if text:
                                chain_act_lines.append(text)
                            _drop_pushed_act(state, dirty, d.get("id"))
                            continue  # suppress — narrate body absorbs
                    yield ev
            if getattr(part, "tail_intent", None):
                chain_act_lines.append(part.tail_intent)
        # Always run narrate at chain tail — even when there's no explicit
        # PassAction part (e.g. chain[use, equip]) the user expects prose.
        # Synthesize an empty pass so narrate has a target_id-less anchor.
        narrate_action = last_pass if last_pass is not None else PassAction(action="pass")
        # chain parts mutated state via emit_*; rebuild graph before narrate
        # reads relations through it.
        state.invalidate_graph()
        graph = state.graph()
        async for ev in _stream_narrate_tail(
            client,
            state,
            scenario_repo,
            player_input,
            dirty,
            to_front_fn,
            narrate_action,
            graph=graph,
            act_log_lines=chain_act_lines,
            previous_phase_signal=previous_phase_signal,
        ):
            yield ev
        tick_turn_buffs(state, dirty)
        async for ev in finalize(state, save_repo, dirty, to_front_fn):
            yield ev
        return

    # action == pass / reject — narrator path.
    assert isinstance(result, (PassAction, RejectAction))
    state.turn_count += 1
    async for ev in _stream_narrate_tail(
        client,
        state,
        scenario_repo,
        player_input,
        dirty,
        to_front_fn,
        result,
        graph=graph,
        previous_phase_signal=previous_phase_signal,
    ):
        yield ev
    tick_turn_buffs(state, dirty)
    async for ev in finalize(state, save_repo, dirty, to_front_fn):
        yield ev


# --- shared narrate tail ---------------------------------------------------


_CORPSE_BYPASS_BODY = "죽은 자는 말이 없습니다."


async def _stream_narrate_tail(
    client: LLMClient,
    state: GameState,
    scenario_repo: ScenarioRepo,
    player_input: str,
    dirty: Dirty,
    to_front_fn: ToFrontFn | None,
    action: "PassAction | RejectAction",
    *,
    graph: GameGraph,
    act_log_lines: list[str] | None = None,
    previous_phase_signal: str | None = None,
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
            state.invalidate_graph()
            graph = state.graph()

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
        scenario_repo,
        player_input,
        judge_result=action.model_dump(),
        graph=graph,
        grade=None,
        act_log_lines=act_log_lines,
        previous_phase_signal=previous_phase_signal,
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
