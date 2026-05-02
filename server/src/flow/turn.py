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
from .buff_tick import tick_turn_buffs
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

    # Consume the one-shot phase signal at entry — cleared before finalize so it can't echo to next turn.
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


# Combat/Summon/Roll/Rest stay in `_dispatch` — they need bespoke pre/post handling.
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
    """Remove the act entry from `state.log_entries` and `dirty.log` so narrate's prose isn't shadowed by a system-toned chrome line."""
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
    """turn_count++ → run engine emit (SSE suppressed) → narrate tail absorbs the act lines → finalize."""
    state.turn_count += 1
    act_log_lines: list[str] = []
    async for ev in emit_factory(client, state, dirty, result):
        if ev.get("type") == "log_entry":
            data = ev.get("data") or {}
            if data.get("kind") == "act":
                text = data.get("text") or ""
                if text:
                    act_log_lines.append(text)
                _drop_pushed_act(state, dirty, data.get("id"))
                continue
        yield ev
    if getattr(result, "tail_intent", None):
        act_log_lines.append(result.tail_intent)

    # emit_* mutated relations; rebuild graph before narrate reads.
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
    """Start a fresh fight, run one auto-combat sim cycle, then finalize."""
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
            # No enemy materialized — fold the engine line into narrate prose so it doesn't read as chrome + silence.
            fail_line = "허공을 가르지만 적은 보이지 않습니다."
            fail_evt = push_act(state, dirty, fail_line)
            _drop_pushed_act(state, dirty, (fail_evt.get("data") or {}).get("id"))
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
                act_log_lines=[fail_line],
            ):
                yield ev
            async for ev in finalize(state, save_repo, dirty, to_front_fn):
                yield ev
            return
        state.active_subject_id = summoned.id
        # New NPC added; rebuild graph so its located_at edge is visible.
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
        return

    if isinstance(result, RestAction):
        async for ev in run_rest(
            state, scenario_repo, save_repo, dirty, rng, to_front_fn, client=client
        ):
            yield ev
        return

    if isinstance(result, FleeAction):
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
        # Feed engine notices ("이미 체력 가득" etc.) into narrate so prose can't contradict the engine.
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
                            continue
                    yield ev
            if getattr(part, "tail_intent", None):
                chain_act_lines.append(part.tail_intent)
        # Synthesize an empty pass so narrate always runs at chain tail, even without an explicit PassAction part.
        narrate_action = last_pass if last_pass is not None else PassAction(action="pass")
        # Chain parts mutated relations via emit_*; rebuild graph before narrate reads.
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
    """Pre-apply movement, emit a state event, then drive narrate. Corpse bypass short-circuits to a deterministic body."""
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
    """No-LLM bypass for dead-target pass — mirrors consume_narrate's persistence steps but skips state_changes."""
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
