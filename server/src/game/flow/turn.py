import random
from collections.abc import AsyncIterator, Callable

from src.llm.calls.classify.schema import JudgeOutput, Verb
from ..domain.errors import JudgeMalformed, PendingCheckActive
from pydantic import ValidationError
from ..domain.memory import GMLogEntry, PlayerLogEntry
from ..domain.state import GameState
from src.llm.client import LLMClient, set_llm_session_if_unset
from ..ontology.graph import GameGraph
from src.db.repo import SaveRepo, ScenarioRepo
from .actions import emit_cast, emit_move, emit_use
from .chain import (
    _enter_combat_and_finalize,
    _is_receipt,
    _resolve_transfer_emit,
    _run_verb_chain,
)
from .combat_phase import has_invalid_combat_targets, run_combat_player_turn
from src.wire.emit import (
    emit_judge_refuse,
    emit_judge_verb,
    emit_judge_verbs,
    emit_log_entry,
)
from .buff_tick import tick_turn_buffs
from .error_phrases import is_dramatic_fail
from .dirty import (
    Dirty,
    ToFrontFn,
    drop_pushed_act,
    finalize,
    next_log_id,
    push_act,
    push_log_entry,
)
from .format import (
    FLEE_OUTSIDE_COMBAT_TEXT,
    GAME_OVER_TEXT,
    INPUT_REJECTED_TEXT,
    NO_COMBAT_TARGETS_TEXT,
)
from .judge import run_judge
from .narrate import stream_narrate_tail
from .rest import run_rest
from .subject import refresh_active_subject
from ..engines.quest import abandon_quest, accept_quest


async def _narrate_absorb_and_finalize(
    client: LLMClient,
    state: GameState,
    scenario_repo: ScenarioRepo,
    save_repo: SaveRepo,
    dirty: Dirty,
    to_front_fn: ToFrontFn | None,
    player_input: str,
    verb: Verb,
    graph: GameGraph,
    previous_phase_signal: str | None,
) -> AsyncIterator[dict]:
    """Shared tail for verbs whose effect is captured entirely by GM prose
    (wait, perceive, speak with social intent, defensive cast fallback, the
    judge/dispatch-fail absorb paths): bump turn count, run narrate, then
    quest check + buff tick + finalize. Without the finalize tail, narrate's
    state_changes (e.g. affinity drops) and pushed cards live only in dirty
    and vanish on the next /turn reload."""
    state.turn_count += 1
    async for ev in stream_narrate_tail(
        client,
        state,
        scenario_repo,
        player_input,
        dirty,
        to_front_fn,
        verb,
        graph=graph,
        previous_phase_signal=previous_phase_signal,
    ):
        yield ev
    tick_turn_buffs(state, dirty)
    async for ev in finalize(state, save_repo, dirty, to_front_fn):
        yield ev


async def _emit_input_rejected_and_finalize(
    client: LLMClient,
    state: GameState,
    scenario_repo: ScenarioRepo,
    save_repo: SaveRepo,
    dirty: Dirty,
    to_front_fn: ToFrontFn | None,
    player_input: str,
    graph: GameGraph,
    previous_phase_signal: str | None,
) -> AsyncIterator[dict]:
    """Verb-dispatch-fail path: surface INPUT_REJECTED_TEXT card, then absorb
    player_input via narrate so the internal exception type isn't exposed."""
    yield emit_log_entry(
        GMLogEntry(
            id=next_log_id(state),
            kind="gm",
            text=INPUT_REJECTED_TEXT,
        )
    )
    async for ev in _narrate_absorb_and_finalize(
        client,
        state,
        scenario_repo,
        save_repo,
        dirty,
        to_front_fn,
        player_input,
        Verb(name="wait"),
        graph,
        previous_phase_signal,
    ):
        yield ev


async def run_turn(
    client: LLMClient,
    state: GameState,
    scenario_repo: ScenarioRepo,
    save_repo: SaveRepo,
    player_input: str,
    *,
    to_front_fn: ToFrontFn | None = None,
    rng: random.Random | None = None,
    quest_action: tuple[str, str] | None = None,
) -> AsyncIterator[dict]:
    set_llm_session_if_unset(state.game_id)
    if state.pending_check is not None:
        raise PendingCheckActive(
            "a pending_check is already active; call /roll instead"
        )

    dirty = Dirty()
    try:
        async for ev in _run_turn_inner(
            client,
            state,
            scenario_repo,
            save_repo,
            player_input,
            dirty,
            to_front_fn,
            rng,
            quest_action,
        ):
            yield ev
    except Exception:
        # Streamed content (player input, GM body, engine events) lives in
        # `dirty` until finalize flushes it. If something raised before that,
        # the next /turn would load pre-error state and the user sees the turn
        # "rewound". Flush what we have, then re-raise.
        if not dirty.finalized:
            try:
                async for ev in finalize(state, save_repo, dirty, to_front_fn):
                    yield ev
            except Exception:
                pass
        raise


async def _run_turn_inner(
    client: LLMClient,
    state: GameState,
    scenario_repo: ScenarioRepo,
    save_repo: SaveRepo,
    player_input: str,
    dirty: Dirty,
    to_front_fn: ToFrontFn | None,
    rng: random.Random | None,
    quest_action: tuple[str, str] | None,
) -> AsyncIterator[dict]:
    if quest_action is not None:
        kind, qid = quest_action
        if kind == "accept":
            accept_quest(state, qid)
        elif kind == "abandon":
            abandon_quest(state, qid, dirty)

    # Skip empty player log entries — quest_action turns can arrive with
    # player_input="" (button-only). An empty 'player' card would render blank.
    if player_input:
        player_log = PlayerLogEntry(
            id=next_log_id(state), kind="player", text=player_input
        )
        push_log_entry(state, player_log, dirty)
        yield emit_log_entry(player_log)

    # Button-only quest_action turn: state mutation already applied, no input
    # to classify — short-circuit to finalize so we don't burn a judge LLM
    # call on an empty prompt. turn_count stays put (UI button isn't an
    # in-world action).
    if quest_action is not None and not player_input:
        async for ev in finalize(state, save_repo, dirty, to_front_fn):
            yield ev
        return

    if not state.characters[state.player_id].alive:
        yield push_act(state, dirty, GAME_OVER_TEXT)
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
    except JudgeMalformed:
        # Judge couldn't structure or ground the input. Absorb into narrate
        # rather than surfacing a system error — state stays unchanged.
        async for ev in _narrate_absorb_and_finalize(
            client,
            state,
            scenario_repo,
            save_repo,
            dirty,
            to_front_fn,
            player_input,
            Verb(name="wait"),
            graph,
            previous_phase_signal,
        ):
            yield ev
        return

    # JudgeOutput: refuse → narrate alone, single verb → _dispatch_verb,
    # multi-verb → _run_verb_chain. Dispatch raises are absorbed by the
    # narrate fallback below.
    if isinstance(result, JudgeOutput):
        # Refuse direct path
        if result.refuse is not None:
            yield emit_judge_refuse(result.refuse)
            state.turn_count += 1
            async for ev in stream_narrate_tail(
                client,
                state,
                scenario_repo,
                player_input,
                dirty,
                to_front_fn,
                Verb(name="wait"),
                graph=graph,
                previous_phase_signal=previous_phase_signal,
            ):
                yield ev
            tick_turn_buffs(state, dirty)
            async for ev in finalize(state, save_repo, dirty, to_front_fn):
                yield ev
            return

        # Single-verb redirect
        if (
            result.refuse is None
            and result.actions is not None
            and len(result.actions) == 1
        ):
            single_verb = result.actions[0]
            try:
                yield emit_judge_verb(single_verb)
                refresh_active_subject(state, [single_verb])
                async for ev in _dispatch_verb(
                    single_verb,
                    client=client,
                    state=state,
                    scenario_repo=scenario_repo,
                    save_repo=save_repo,
                    dirty=dirty,
                    rng=rng,
                    to_front_fn=to_front_fn,
                    player_input=player_input,
                    graph=graph,
                    previous_phase_signal=previous_phase_signal,
                ):
                    yield ev
                return
            except (ValidationError, ValueError):
                # Surface INPUT_REJECTED_TEXT to the player so the internal
                # exception type isn't exposed; absorb player_input via narrate.
                async for ev in _emit_input_rejected_and_finalize(
                    client,
                    state,
                    scenario_repo,
                    save_repo,
                    dirty,
                    to_front_fn,
                    player_input,
                    graph,
                    previous_phase_signal,
                ):
                    yield ev
                return

        # Multi-verb redirect (length >= 2): call _run_verb_chain.
        if (
            result.refuse is None
            and result.actions is not None
            and len(result.actions) >= 2
        ):
            verbs = result.actions
            try:
                yield emit_judge_verbs(verbs)
                refresh_active_subject(state, verbs)
                async for ev in _run_verb_chain(
                    verbs,
                    client=client,
                    state=state,
                    scenario_repo=scenario_repo,
                    save_repo=save_repo,
                    dirty=dirty,
                    rng=rng,
                    to_front_fn=to_front_fn,
                    player_input=player_input,
                    graph=graph,
                    previous_phase_signal=previous_phase_signal,
                ):
                    yield ev
                return
            except (ValidationError, ValueError):
                # Same INPUT_REJECTED_TEXT fallback as the single-verb branch.
                async for ev in _emit_input_rejected_and_finalize(
                    client,
                    state,
                    scenario_repo,
                    save_repo,
                    dirty,
                    to_front_fn,
                    player_input,
                    graph,
                    previous_phase_signal,
                ):
                    yield ev
                return

    # Unreachable: out of combat run_judge returns only JudgeOutput, and the
    # _exactly_one validator rejects empty actions; all branches above return.
    raise AssertionError(f"unexpected run_judge result: {type(result).__name__}")


EmitFactory = Callable[[LLMClient, GameState, Dirty, object], AsyncIterator[dict]]


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
    *,
    previous_phase_signal: str | None = None,
) -> AsyncIterator[dict]:
    """turn_count++ → engine emit. Receipt actions surface the act line and
    skip narrate; non-receipts (first-visit move, dramatic fails) drop the act
    and let narrate absorb the lines into prose."""
    state.turn_count += 1
    # Snapshot pre-move so first-visit detection survives _apply_move's atomic visited update.
    is_move = result.name == "move"
    pre_move_visited = (
        state.characters[state.player_id].visited_location_ids.copy()
        if is_move
        else None
    )
    act_log_lines: list[str] = []
    pushed_act_evts: list[dict] = []
    failure_raws: list[str] = []
    async for ev in emit_factory(client, state, dirty, result):
        if ev.get("type") == "_engine_fail":
            failure_raws.append((ev.get("data") or {}).get("raw_error_msg") or "")
            continue
        if ev.get("type") == "log_entry":
            data = ev.get("data") or {}
            if data.get("kind") == "act":
                text = data.get("text") or ""
                if text:
                    act_log_lines.append(text)
                pushed_act_evts.append(ev)
                continue
        yield ev

    # emit_* mutated relations; rebuild graph before narrate reads.
    state.invalidate_graph()
    graph = state.graph()
    # Move into a new location named after an alive NPC ("탈크의 대장간으로 이동") → pin that NPC so the target panel matches narrate's first prose.
    if is_move:
        from .subject import pin_subject_by_input_name

        pin_subject_by_input_name(state, player_input, graph)

    is_failure = bool(failure_raws)
    dramatic = is_failure and any(is_dramatic_fail(r) for r in failure_raws)
    receipt_action = _is_receipt(state, result, pre_move_visited)
    # narrate iff: dramatic failure OR (success on a non-receipt action, i.e. first-visit move)
    narrate_path = dramatic or (not is_failure and not receipt_action)

    if narrate_path:
        # Move's location-enter act is the system card; surface it on the
        # narrate path too instead of dropping it into prose.
        keep_card = is_move and not is_failure
        for ev in pushed_act_evts:
            if keep_card:
                yield ev
            else:
                drop_pushed_act(state, dirty, (ev.get("data") or {}).get("id"))
        tail_intent = (result.modifiers or {}).get("tail_intent")
        if tail_intent:
            act_log_lines.append(tail_intent)
        fake_pass = Verb(name="wait")
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
            previous_phase_signal=previous_phase_signal,
        ):
            yield ev
    else:
        for ev in pushed_act_evts:
            yield ev
        if to_front_fn is not None:
            yield {"type": "state", "data": to_front_fn(state)}

    tick_turn_buffs(state, dirty)
    async for ev in finalize(state, save_repo, dirty, to_front_fn):
        yield ev


async def _dispatch_verb(
    verb: Verb,
    *,
    client: LLMClient,
    state: GameState,
    scenario_repo: ScenarioRepo,
    save_repo: SaveRepo,
    dirty: Dirty,
    rng: random.Random | None,
    to_front_fn: ToFrontFn | None,
    player_input: str,
    graph: GameGraph,
    previous_phase_signal: str | None = None,
) -> AsyncIterator[dict]:
    """Dispatch a single verb to its emit_* / run_* handler.

    wait / perceive absorb into narrate. move / use / transfer / attack / cast
    / speak / rest call their emit_* or run_* handler directly."""
    name = verb.name
    m = verb.modifiers or {}

    if name == "wait":
        async for ev in _narrate_absorb_and_finalize(
            client,
            state,
            scenario_repo,
            save_repo,
            dirty,
            to_front_fn,
            player_input,
            verb,
            graph,
            previous_phase_signal,
        ):
            yield ev
        return

    if name == "perceive":
        # Pre-Stage-2 uncertainty rule: absorbed by narrate.
        async for ev in _narrate_absorb_and_finalize(
            client,
            state,
            scenario_repo,
            save_repo,
            dirty,
            to_front_fn,
            player_input,
            verb,
            graph,
            previous_phase_signal,
        ):
            yield ev
        return

    if name == "cast":
        skill_id = m.get("skill_id")
        skill = state.skills.get(skill_id) if skill_id else None
        # Defensive — semantic check rejects non-heal/buff cast and unknown
        # skill_id, so reaching here with a bad skill means a slipped retry.
        # Fall back to narrate so the turn doesn't crash.
        if skill is None or skill.type not in ("heal", "buff"):
            async for ev in _narrate_absorb_and_finalize(
                client,
                state,
                scenario_repo,
                save_repo,
                dirty,
                to_front_fn,
                player_input,
                verb,
                graph,
                previous_phase_signal,
            ):
                yield ev
            return
        if skill.target == "self":
            target_ids: list[str] = [state.player_id]
        elif skill.target == "single":
            target_ids = list(verb.target_ids[:1]) or [state.player_id]
        else:
            target_ids = []

        def cast_emit_factory(c, s, d, v):
            return emit_cast(s, s.player_id, skill_id, target_ids, d, rng=rng)

        async for ev in _run_one_step_action(
            client,
            state,
            scenario_repo,
            save_repo,
            dirty,
            to_front_fn,
            player_input,
            verb,
            cast_emit_factory,
            previous_phase_signal=previous_phase_signal,
        ):
            yield ev
        return

    if name == "rest":
        async for ev in run_rest(
            state,
            scenario_repo,
            save_repo,
            dirty,
            rng,
            to_front_fn,
            client=client,
            player_input=player_input,
        ):
            yield ev
        return

    if name == "speak":
        intent = m.get("intent")
        target = m.get("target")
        if intent == "recruit" and target:
            from .companion import run_recruit_verb

            async for ev in run_recruit_verb(
                verb,
                state=state,
                save_repo=save_repo,
                player_input=player_input,
                dirty=dirty,
                to_front_fn=to_front_fn,
            ):
                yield ev
            return
        if intent == "part" and target:
            from .companion import run_dismiss_verb

            async for ev in run_dismiss_verb(
                verb,
                state=state,
                scenario_repo=scenario_repo,
                save_repo=save_repo,
                client=client,
                dirty=dirty,
                to_front_fn=to_front_fn,
            ):
                yield ev
            return
        # friendly/hostile/deceptive: absorbed by narrate — narrate emits
        # the affinity state_change keyed off intent's tone.
        async for ev in _narrate_absorb_and_finalize(
            client,
            state,
            scenario_repo,
            save_repo,
            dirty,
            to_front_fn,
            player_input,
            verb,
            graph,
            previous_phase_signal,
        ):
            yield ev
        return

    if name == "move":
        destination = m.get("destination")
        if destination is None:
            # Out-of-combat move with no destination is blocked by schema —
            # defensive. manner=hasty (flee equivalent) is meaningless out of
            # combat, same message.
            fail_line = FLEE_OUTSIDE_COMBAT_TEXT
            if client is None:
                yield push_act(state, dirty, fail_line)
            else:
                fail_evt = push_act(state, dirty, fail_line)
                drop_pushed_act(state, dirty, (fail_evt.get("data") or {}).get("id"))
                async for ev in stream_narrate_tail(
                    client,
                    state,
                    scenario_repo,
                    player_input,
                    dirty,
                    to_front_fn,
                    Verb(name="wait"),
                    graph=graph,
                    act_log_lines=[fail_line],
                    previous_phase_signal=previous_phase_signal,
                ):
                    yield ev
            async for ev in finalize(state, save_repo, dirty, to_front_fn):
                yield ev
            return

        # _run_one_step_action: pre_move snapshot + emit + narrate decision (first-visit)
        def move_emit_factory(c, s, d, v):
            return emit_move(s, s.player_id, destination, d)

        async for ev in _run_one_step_action(
            client,
            state,
            scenario_repo,
            save_repo,
            dirty,
            to_front_fn,
            player_input,
            verb,
            move_emit_factory,
            previous_phase_signal=previous_phase_signal,
        ):
            yield ev
        return

    if name == "use":
        item_id = m["item_id"]
        target_id = m.get("target_id")

        def use_emit_factory(c, s, d, v):
            return emit_use(s, s.player_id, item_id, target_id, d)

        async for ev in _run_one_step_action(
            client,
            state,
            scenario_repo,
            save_repo,
            dirty,
            to_front_fn,
            player_input,
            verb,
            use_emit_factory,
            previous_phase_signal=previous_phase_signal,
        ):
            yield ev
        return

    if name == "transfer":
        mode = m["mode"]
        from_id = m["from_id"]
        to_id = m["to_id"]
        if mode == "steal":
            from .steal import run_steal

            async for ev in run_steal(
                state,
                save_repo,
                player_input,
                from_id,
                dirty,
                to_front_fn,
            ):
                yield ev
            return
        item_id = m["item_id"]
        agreed_price = m.get("price")

        def transfer_emit_factory(c, s, d, v):
            return _resolve_transfer_emit(
                s,
                d,
                mode=mode,
                from_id=from_id,
                to_id=to_id,
                item_id=item_id,
                price=agreed_price,
            )

        async for ev in _run_one_step_action(
            client,
            state,
            scenario_repo,
            save_repo,
            dirty,
            to_front_fn,
            player_input,
            verb,
            transfer_emit_factory,
            previous_phase_signal=previous_phase_signal,
        ):
            yield ev
        return

    if name == "attack":
        targets = list(verb.target_ids)
        if has_invalid_combat_targets(state, graph, targets):
            fail_line = NO_COMBAT_TARGETS_TEXT
            if client is None:
                yield push_act(state, dirty, fail_line)
            else:
                fail_evt = push_act(state, dirty, fail_line)
                drop_pushed_act(state, dirty, (fail_evt.get("data") or {}).get("id"))
                async for ev in stream_narrate_tail(
                    client,
                    state,
                    scenario_repo,
                    player_input,
                    dirty,
                    to_front_fn,
                    Verb(name="wait"),
                    graph=graph,
                    act_log_lines=[fail_line],
                    previous_phase_signal=previous_phase_signal,
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
            enemy_ids=targets,
            skill_id=m.get("skill_id"),
            graph=graph,
            surprise=bool(m.get("surprise", False)),
            previous_phase_signal=previous_phase_signal,
        ):
            yield ev
        return

    raise ValueError(f"unknown verb name: {name}")


