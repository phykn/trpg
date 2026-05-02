import random
from collections.abc import AsyncIterator, Callable

from ..agents.dc_judge.schema import (
    BuyAction,
    ChainAction,
    CombatAction,
    EquipAction,
    FleeAction,
    GiveAction,
    LearnSkillAction,
    LevelUpAction,
    MoveAction,
    PassAction,
    RejectAction,
    RestAction,
    RollAction,
    SellAction,
    SummonCombatAction,
    UnequipAction,
    UseAction,
)
from ..domain.errors import JudgeMalformed, LLMUnavailable, PendingCheckActive
from ..engines.invariants import InvariantViolation
from pydantic import ValidationError
from ..domain.memory import PlayerLogEntry
from ..domain.state import GameState
from ..llm.client import LLMClient, set_llm_session_if_unset
from ..ontology.graph import GameGraph
from ..ontology.queries import location_of
from ..persistence.repo import SaveRepo, ScenarioRepo
from .actions import (
    emit_equip,
    emit_give,
    emit_learn_skill,
    emit_level_up,
    emit_move,
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
from .narrate import stream_narrate_tail
from .rest import run_rest
from .subject import refresh_active_subject


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

    # One-shot — cleared at entry so it can't echo into the next turn.
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
    GiveAction: lambda c, s, d, a: emit_give(s, a.from_id, a.to_id, a.item_id, d),
    MoveAction: lambda c, s, d, a: emit_move(s, s.player_id, a.destination, d),
}


def _drop_pushed_act(state: GameState, dirty: Dirty, entry_id: int | None) -> None:
    """Drop the pushed act entry so narrate's prose isn't shadowed by an engine-toned line."""
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
    # Move into a new location named after an alive NPC ("탈크의 대장간으로 이동") → pin that NPC so the target panel matches narrate's first prose.
    if isinstance(result, MoveAction):
        from .subject import pin_subject_by_input_name

        pin_subject_by_input_name(state, player_input, graph)
    fake_pass = PassAction(action="pass")
    async for ev in stream_narrate_tail(
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
    # Post-combat narrate so the system card isn't the terminal UI line — adds aftermath body + suggestions, and consumes the downed_recovered signal here when present. Skipped on player death (game-over) and on client=None (engine-only test path).
    # player_input is empty: the original input was already consumed by combat_narrate; this second narrate is the recovery beat, not a re-run of the player's intent.
    if client is not None and state.characters[state.player_id].alive:
        state.invalidate_graph()
        graph = state.graph()
        signal = state.previous_phase_signal
        state.previous_phase_signal = None
        async for ev in stream_narrate_tail(
            client,
            state,
            scenario_repo,
            "",
            dirty,
            to_front_fn,
            PassAction(action="pass"),
            graph=graph,
            previous_phase_signal=signal,
        ):
            yield ev
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
            # Invalid target doesn't consume the turn — the act line lands either as a raw push (no LLM) or absorbed into narrate prose (LLM available).
            fail_line = "공격할 수 있는 대상이 없습니다."
            if client is None:
                yield push_act(state, dirty, fail_line)
            else:
                fail_evt = push_act(state, dirty, fail_line)
                _drop_pushed_act(state, dirty, (fail_evt.get("data") or {}).get("id"))
                async for ev in stream_narrate_tail(
                    client, state, scenario_repo, player_input, dirty, to_front_fn,
                    PassAction(action="pass"),
                    graph=graph, act_log_lines=[fail_line],
                ):
                    yield ev
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
            except (LLMUnavailable, ValidationError, InvariantViolation):
                summoned = None
        if summoned is None:
            # No enemy materialized — fold the engine line into narrate prose so it doesn't read as chrome + silence. Failed summon doesn't consume the turn (mirrors the CombatAction invalid-target branch).
            fail_line = "허공을 가르지만 적은 보이지 않습니다."
            fail_evt = push_act(state, dirty, fail_line)
            _drop_pushed_act(state, dirty, (fail_evt.get("data") or {}).get("id"))
            state.invalidate_graph()
            graph = state.graph()
            fake_pass = PassAction(action="pass")
            async for ev in stream_narrate_tail(
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
            state, scenario_repo, save_repo, dirty, rng, to_front_fn,
            client=client, player_input=player_input,
        ):
            yield ev
        return

    if isinstance(result, FleeAction):
        # Flee outside combat doesn't consume the turn — same shape as the CombatAction invalid-target branch.
        fail_line = "지금은 도망칠 전투가 없습니다."
        if client is None:
            yield push_act(state, dirty, fail_line)
        else:
            fail_evt = push_act(state, dirty, fail_line)
            _drop_pushed_act(state, dirty, (fail_evt.get("data") or {}).get("id"))
            async for ev in stream_narrate_tail(
                client, state, scenario_repo, player_input, dirty, to_front_fn,
                PassAction(action="pass"),
                graph=graph, act_log_lines=[fail_line],
            ):
                yield ev
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
        # Chain that includes a move into a named-NPC location: pin the NPC so target panel matches narrate.
        if any(isinstance(p, MoveAction) for p in result.parts):
            from .subject import pin_subject_by_input_name

            pin_subject_by_input_name(state, player_input, graph)
        async for ev in stream_narrate_tail(
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
    async for ev in stream_narrate_tail(
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


