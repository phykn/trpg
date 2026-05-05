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
from .actions import (
    emit_cast,
    emit_equip,
    emit_give,
    emit_move,
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
from src.wire.emit import (
    emit_error,
    emit_judge_pending_check_trigger,
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
    format_combat_event_summary,
)
from .judge import run_judge, judge_quest_progress
from .combat_auto import AutoCombatResult
from .narrate import stream_narrate_tail
from .rest import run_rest
from .subject import refresh_active_subject
from ..engines.quest import abandon_quest, accept_quest, apply_judge_result


def end_turn_quest_check(state: GameState) -> None:
    """At turn end, run free-path judge over active quests using recent turn log."""
    if not state.turn_log:
        return
    history = [{"summary": e.summary} for e in state.turn_log[-5:]]
    for quest in list(state.quests.values()):
        if quest.status != "active":
            continue
        result = judge_quest_progress(
            quest={
                "id": quest.id,
                "objective_text": quest.objective_text or quest.title,
            },
            history=history,
            claim=None,
            npc_context=None,
        )
        apply_judge_result(state, quest.id, result)


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
    """Shared dispatch-raise fallback: surface INPUT_REJECTED_TEXT, run a
    bare narrate so the player_input is absorbed as in-world prose, then
    quest check + buff tick + finalize. Used by single-verb and multi-verb
    redirect branches when verb dispatch raises ValidationError / ValueError."""
    yield emit_log_entry(
        GMLogEntry(
            id=next_log_id(state),
            kind="gm",
            text=INPUT_REJECTED_TEXT,
        )
    )
    state.turn_count += 1
    async for ev in stream_narrate_tail(
        client, state, scenario_repo, player_input, dirty, to_front_fn,
        Verb(name="wait"),
        graph=graph, previous_phase_signal=previous_phase_signal,
    ):
        yield ev
    try:
        end_turn_quest_check(state)
    except NotImplementedError:
        pass
    tick_turn_buffs(state, dirty)
    async for ev in finalize(state, save_repo, dirty, to_front_fn):
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

    if quest_action is not None:
        kind, qid = quest_action
        if kind == "accept":
            accept_quest(state, qid)
        elif kind == "abandon":
            abandon_quest(state, qid, dirty)

    # Skip empty player log entries — quest_action turns can arrive with
    # player_input="" (button-only). An empty 'player' card would render blank.
    if player_input:
        player_log = PlayerLogEntry(id=next_log_id(state), kind="player", text=player_input)
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
    except JudgeMalformed as e:
        yield emit_error(e)
        return

    # PendingCheckTrigger → emit_roll_pending_from_trigger directly.
    from .judge import PendingCheckTrigger
    if isinstance(result, PendingCheckTrigger):
        from .actions import emit_roll_pending_from_trigger
        yield emit_judge_pending_check_trigger(
            tier=result.tier,
            stat=result.stat,
            targets=result.targets,
            reason=result.reason,
        )
        async for ev in emit_roll_pending_from_trigger(
            state, save_repo, player_input, result, dirty,
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
                client, state, scenario_repo, player_input, dirty, to_front_fn,
                Verb(name="wait"),
                graph=graph,
                previous_phase_signal=previous_phase_signal,
            ):
                yield ev
            try:
                end_turn_quest_check(state)
            except NotImplementedError:
                pass
            tick_turn_buffs(state, dirty)
            async for ev in finalize(state, save_repo, dirty, to_front_fn):
                yield ev
            return

        # Single-verb redirect
        if (result.refuse is None
                and result.actions is not None
                and len(result.actions) == 1):
            single_verb = result.actions[0]
            try:
                yield emit_judge_verb(single_verb)
                refresh_active_subject(state, [single_verb])
                async for ev in _dispatch_verb(
                    single_verb,
                    client=client, state=state, scenario_repo=scenario_repo,
                    save_repo=save_repo, dirty=dirty, rng=rng,
                    to_front_fn=to_front_fn, player_input=player_input, graph=graph,
                    previous_phase_signal=previous_phase_signal,
                ):
                    yield ev
                return
            except (ValidationError, ValueError):
                # Surface INPUT_REJECTED_TEXT to the player so the internal
                # exception type isn't exposed; absorb player_input via narrate.
                async for ev in _emit_input_rejected_and_finalize(
                    client, state, scenario_repo, save_repo, dirty,
                    to_front_fn, player_input, graph, previous_phase_signal,
                ):
                    yield ev
                return

        # Multi-verb redirect (length >= 2): call _run_verb_chain.
        if (result.refuse is None
                and result.actions is not None
                and len(result.actions) >= 2):
            verbs = result.actions
            try:
                yield emit_judge_verbs(verbs)
                refresh_active_subject(state, verbs)
                async for ev in _run_verb_chain(
                    verbs,
                    client=client, state=state, scenario_repo=scenario_repo,
                    save_repo=save_repo, dirty=dirty, rng=rng,
                    to_front_fn=to_front_fn, player_input=player_input, graph=graph,
                    previous_phase_signal=previous_phase_signal,
                ):
                    yield ev
                return
            except (ValidationError, ValueError):
                # Same INPUT_REJECTED_TEXT fallback as the single-verb branch.
                async for ev in _emit_input_rejected_and_finalize(
                    client, state, scenario_repo, save_repo, dirty,
                    to_front_fn, player_input, graph, previous_phase_signal,
                ):
                    yield ev
                return

    # Unreachable: run_judge returns only JudgeOutput | PendingCheckTrigger;
    # the _exactly_one validator rejects empty actions and both branches above
    # return.
    raise AssertionError(
        f"unexpected run_judge result: {type(result).__name__}"
    )


EmitFactory = Callable[[LLMClient, GameState, Dirty, object], AsyncIterator[dict]]


def _emit_verb_in_chain(client, state, dirty, verb: Verb) -> AsyncIterator[dict]:
    """Dispatch a single chain-internal verb to its emit_* handler. No
    self-finalize — the chain outer loop owns narrate / finalize."""
    n = verb.name
    m = verb.modifiers or {}
    if n == "use":
        return emit_use(state, state.player_id, m["item_id"], m.get("target_id"), dirty)
    if n == "move":
        destination = m["destination"]
        return emit_move(state, state.player_id, destination, dirty)
    if n == "transfer":
        mode = m["mode"]
        from_id = m["from_id"]
        to_id = m["to_id"]
        item_id = m["item_id"]
        if "<self>.equipped" in to_id:
            return emit_equip(state, state.player_id, item_id, dirty)
        if "<self>.equipped" in from_id:
            return emit_unequip(state, state.player_id, item_id, dirty)
        if mode == "gift":
            return emit_give(state, from_id, to_id, item_id, dirty)
        if from_id == state.player_id:
            return emit_trade(
                state, state.player_id, to_id, item_id, dirty,
                direction="sell", agreed_price=m.get("price"),
            )
        return emit_trade(
            state, state.player_id, from_id, item_id, dirty,
            direction="buy", agreed_price=m.get("price"),
        )
    # wait/perceive/speak/cast: absorbed by narrate inside a chain — no
    # emit. _emit_verb_in_chain handles only chain-prefix-compatible verbs.
    raise ValueError(f"verb {n!r} cannot be emitted in chain (use _dispatch_verb)")


def _is_receipt(
    state: GameState,
    action: Verb,
    pre_move_visited: set[str] | None = None,
) -> bool:
    """Receipt-only verb: act_log + state mutation, no narrate. `use` is always
    receipt; `transfer` is receipt only for equip/unequip; `move` is receipt
    only on re-visit."""
    if action.name == "use":
        return True
    if action.name == "transfer":
        mods = action.modifiers or {}
        from_id = mods.get("from_id", "")
        to_id = mods.get("to_id", "")
        if "<self>.equipped" in to_id or "<self>.equipped" in from_id:
            return True
        return False
    if action.name == "move":
        destination = (action.modifiers or {}).get("destination")
        if destination is None or pre_move_visited is None:
            return False
        return destination in pre_move_visited
    return False


def _chain_needs_narrate(
    state: GameState,
    parts: list[Verb],
    part_failures: list[bool] | None = None,
    pre_move_visited: set[str] | None = None,
) -> bool:
    """Chain narrates iff any part is narrate-worthy:
    wait/perceive/speak/cast/attack are narrate-worthy (cast/attack in prefix
    position get prose-absorbed under the current cast policy + chain-prefix
    attack-ignore policy). transfer (gift/trade) is an NPC interaction.
    first-visit move narrates. Skip: receipt-only chains (equip/unequip/
    use-self) and chains where every narrate-worthy part failed."""
    for i, part in enumerate(parts):
        if part.name in ("wait", "perceive", "speak", "cast", "attack"):
            return True
        if part.name == "transfer":
            mods = part.modifiers or {}
            mode = mods.get("mode")
            from_id = mods.get("from_id", "")
            to_id = mods.get("to_id", "")
            if "<self>.equipped" in to_id or "<self>.equipped" in from_id:
                continue
            if mode in ("gift", "trade"):
                failed = bool(part_failures[i]) if part_failures is not None else False
                if not failed:
                    return True
        if part.name == "move":
            destination = (part.modifiers or {}).get("destination")
            if destination and pre_move_visited is not None:
                if destination not in pre_move_visited:
                    failed = bool(part_failures[i]) if part_failures is not None else False
                    if not failed:
                        return True
    return False


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

    try:
        end_turn_quest_check(state)
    except NotImplementedError:
        pass  # LLM not wired yet; hook placement is correct
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
    surprise: bool = False,
    previous_phase_signal: str | None = None,
    act_log_lines: list[str] | None = None,
) -> AsyncIterator[dict]:
    """Start a fresh fight, run one auto-combat sim cycle, then finalize.
    `act_log_lines` carries chain-prefix tail_intents into the post-combat
    narrate so cast/attack absorbed lines aren't lost on a combat-tail chain."""
    player_action = PlayerAction(
        kind="skill" if skill_id else "attack",
        skill_id=skill_id,
        targets=list(enemy_ids),
    )
    combat_results: list[AutoCombatResult] = []
    async for ev in start_combat_and_drive_auto(
        client,
        state,
        scenario_repo,
        enemy_ids,
        dirty,
        rng,
        player_input=player_input,
        player_action=player_action,
        surprise="player" if surprise else None,
        graph=graph,
        _result_out=combat_results,
    ):
        yield ev
    state.turn_count += 1
    # Post-combat narrate so the system card isn't the terminal UI line — adds aftermath body and consumes the downed_recovered signal here when present. Skipped on player death (game-over) and on client=None (engine-only test path).
    # player_input is empty: the original input was already consumed by combat_narrate; this second narrate is the recovery beat, not a re-run of the player's intent.
    if client is not None and state.characters[state.player_id].alive:
        state.invalidate_graph()
        graph = state.graph()
        # Combat-set signal (e.g. downed_recovered) takes priority over the
        # pre-turn signal carried in via previous_phase_signal arg.
        signal = state.previous_phase_signal or previous_phase_signal
        state.previous_phase_signal = None
        recent_events: list[dict] = []
        if combat_results:
            recent_events.append(
                {
                    "type": "combat",
                    "summary": format_combat_event_summary(combat_results[0]),
                }
            )
        async for ev in stream_narrate_tail(
            client,
            state,
            scenario_repo,
            "",
            dirty,
            to_front_fn,
            Verb(name="wait"),
            graph=graph,
            previous_phase_signal=signal,
            recent_engine_events=recent_events,
            act_log_lines=act_log_lines,
        ):
            yield ev
    # Buffs already ticked per-round inside run_auto_combat; no /turn-end tick here.
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
        async for ev in stream_narrate_tail(
            client, state, scenario_repo, player_input, dirty, to_front_fn,
            verb, graph=graph, previous_phase_signal=previous_phase_signal,
        ):
            yield ev
        return

    if name == "perceive":
        # Pre-Stage-2 uncertainty rule: absorbed by narrate.
        async for ev in stream_narrate_tail(
            client, state, scenario_repo, player_input, dirty, to_front_fn,
            verb, graph=graph, previous_phase_signal=previous_phase_signal,
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
            async for ev in stream_narrate_tail(
                client, state, scenario_repo, player_input, dirty, to_front_fn,
                verb, graph=graph, previous_phase_signal=previous_phase_signal,
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
            client, state, scenario_repo, save_repo, dirty, to_front_fn,
            player_input, verb, cast_emit_factory,
            previous_phase_signal=previous_phase_signal,
        ):
            yield ev
        return

    if name == "rest":
        async for ev in run_rest(
            state, scenario_repo, save_repo, dirty, rng, to_front_fn,
            client=client, player_input=player_input,
        ):
            yield ev
        return

    if name == "speak":
        intent = m.get("intent")
        target = m.get("target")
        if intent == "recruit" and target:
            from .companion import run_recruit_verb
            async for ev in run_recruit_verb(
                verb, state=state, save_repo=save_repo,
                player_input=player_input, dirty=dirty, to_front_fn=to_front_fn,
            ):
                yield ev
            return
        if intent == "part" and target:
            from .companion import run_dismiss_verb
            async for ev in run_dismiss_verb(
                verb, state=state, scenario_repo=scenario_repo,
                save_repo=save_repo, client=client, dirty=dirty,
                to_front_fn=to_front_fn,
            ):
                yield ev
            return
        # friendly/hostile/deceptive: absorbed by narrate — narrate emits
        # the affinity state_change keyed off intent's tone.
        async for ev in stream_narrate_tail(
            client, state, scenario_repo, player_input, dirty, to_front_fn,
            verb, graph=graph, previous_phase_signal=previous_phase_signal,
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
                    client, state, scenario_repo, player_input, dirty, to_front_fn,
                    Verb(name="wait"), graph=graph, act_log_lines=[fail_line],
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
            client, state, scenario_repo, save_repo, dirty, to_front_fn,
            player_input, verb, move_emit_factory,
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
            client, state, scenario_repo, save_repo, dirty, to_front_fn,
            player_input, verb, use_emit_factory,
            previous_phase_signal=previous_phase_signal,
        ):
            yield ev
        return

    if name == "transfer":
        mode = m["mode"]
        from_id = m["from_id"]
        to_id = m["to_id"]
        item_id = m["item_id"]
        agreed_price = m.get("price")

        def transfer_emit_factory(c, s, d, v):
            if "<self>.equipped" in to_id:
                return emit_equip(s, s.player_id, item_id, d)
            if "<self>.equipped" in from_id:
                return emit_unequip(s, s.player_id, item_id, d)
            if mode == "gift":
                return emit_give(s, from_id, to_id, item_id, d)
            if from_id == s.player_id:
                return emit_trade(
                    s, s.player_id, to_id, item_id, d,
                    direction="sell", agreed_price=agreed_price,
                )
            return emit_trade(
                s, s.player_id, from_id, item_id, d,
                direction="buy", agreed_price=agreed_price,
            )

        async for ev in _run_one_step_action(
            client, state, scenario_repo, save_repo, dirty, to_front_fn,
            player_input, verb, transfer_emit_factory,
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
                    client, state, scenario_repo, player_input, dirty, to_front_fn,
                    Verb(name="wait"), graph=graph, act_log_lines=[fail_line],
                    previous_phase_signal=previous_phase_signal,
                ):
                    yield ev
            async for ev in finalize(state, save_repo, dirty, to_front_fn):
                yield ev
            return
        async for ev in _enter_combat_and_finalize(
            client, state, scenario_repo, save_repo, dirty, rng, to_front_fn,
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


async def _run_verb_chain(
    verbs: list[Verb],
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
    """Multi-verb chain dispatch — iterate list[Verb].

    tail attack → combat phase entry. tail cast is narrate-only in the current
    policy (same as single cast in _dispatch_verb — avoid self-targeting combat
    entry). prefix verbs go to _emit_verb_in_chain (use/move/transfer) or are
    absorbed by narrate (wait/perceive/speak/cast/attack — the latter two get
    prose-absorbed inside a chain). narrate decision is _chain_needs_narrate
    + dramatic_chain."""
    # Only tail attack triggers combat phase entry. cast falls into the
    # narrate-absorb path so chain semantics match single-cast in _dispatch_verb.
    tail_combat: Verb | None = (
        verbs[-1] if verbs and verbs[-1].name == "attack" else None
    )
    prefix = verbs[:-1] if tail_combat is not None else list(verbs)
    if tail_combat is None:
        state.turn_count += 1

    # pre-move snapshot
    pre_move_visited = (
        state.characters[state.player_id].visited_location_ids.copy()
        if any(p.name == "move" for p in prefix)
        else None
    )

    last_wait: Verb | None = None
    chain_act_lines: list[str] = []
    chain_act_evts: list[tuple[dict, int]] = []
    chain_failure_raws: list[str] = []
    part_failures: list[bool] = [False] * len(prefix)

    for idx, verb in enumerate(prefix):
        if verb.name == "wait":
            last_wait = verb
            continue
        if verb.name in ("speak", "perceive", "cast", "attack"):
            # In-chain narrate absorption — no emit; narrate handles prose.
            # cast/attack in prefix position are not phase-changing (tail is
            # non-combat), so narrate describes them as prose. Skipping emit
            # here also avoids the ValueError that _emit_verb_in_chain raises
            # for these verbs.
            tail_intent = (verb.modifiers or {}).get("tail_intent")
            if tail_intent:
                chain_act_lines.append(tail_intent)
            continue
        # use / move / transfer → emit_*
        async for ev in _emit_verb_in_chain(client, state, dirty, verb):
            if ev.get("type") == "_engine_fail":
                chain_failure_raws.append(
                    (ev.get("data") or {}).get("raw_error_msg") or ""
                )
                part_failures[idx] = True
                continue
            if ev.get("type") == "log_entry":
                d = ev.get("data") or {}
                if d.get("kind") == "act":
                    text = d.get("text") or ""
                    if text:
                        chain_act_lines.append(text)
                    chain_act_evts.append((ev, idx))
                    continue
            yield ev
        if (verb.modifiers or {}).get("tail_intent"):
            chain_act_lines.append(verb.modifiers["tail_intent"])

    state.invalidate_graph()
    graph = state.graph()
    if any(p.name == "move" for p in prefix):
        from .subject import pin_subject_by_input_name
        pin_subject_by_input_name(state, player_input, graph)

    if tail_combat is not None:
        # combat path — handle prefix act cards.
        for ev, part_idx in chain_act_evts:
            keep_card = (
                prefix[part_idx].name == "move" and not part_failures[part_idx]
            )
            if keep_card:
                yield ev
            else:
                drop_pushed_act(state, dirty, (ev.get("data") or {}).get("id"))
        targets = list(tail_combat.target_ids)
        if has_invalid_combat_targets(state, graph, targets):
            fail_line = NO_COMBAT_TARGETS_TEXT
            if client is None:
                yield push_act(state, dirty, fail_line)
            else:
                fail_evt = push_act(state, dirty, fail_line)
                drop_pushed_act(state, dirty, (fail_evt.get("data") or {}).get("id"))
                chain_act_lines.append(fail_line)
                async for ev in stream_narrate_tail(
                    client, state, scenario_repo, player_input, dirty, to_front_fn,
                    Verb(name="wait"),
                    graph=graph, act_log_lines=chain_act_lines,
                    previous_phase_signal=previous_phase_signal,
                ):
                    yield ev
            async for ev in finalize(state, save_repo, dirty, to_front_fn):
                yield ev
            return
        async for ev in _enter_combat_and_finalize(
            client, state, scenario_repo, save_repo, dirty, rng, to_front_fn,
            player_input=player_input,
            enemy_ids=targets,
            skill_id=(tail_combat.modifiers or {}).get("skill_id"),
            graph=graph,
            surprise=bool((tail_combat.modifiers or {}).get("surprise", False)),
            previous_phase_signal=previous_phase_signal,
            act_log_lines=chain_act_lines or None,
        ):
            yield ev
        return

    # narrate path
    narrate_action = last_wait if last_wait is not None else Verb(name="wait")
    dramatic_chain = any(is_dramatic_fail(r) for r in chain_failure_raws)
    narrate_chain = (
        _chain_needs_narrate(state, prefix, part_failures, pre_move_visited)
        or dramatic_chain
    )

    if narrate_chain:
        for ev, part_idx in chain_act_evts:
            keep_card = (
                prefix[part_idx].name == "move" and not part_failures[part_idx]
            )
            if keep_card:
                yield ev
            else:
                drop_pushed_act(state, dirty, (ev.get("data") or {}).get("id"))
        async for ev in stream_narrate_tail(
            client, state, scenario_repo, player_input, dirty, to_front_fn,
            narrate_action,
            graph=graph, act_log_lines=chain_act_lines,
            previous_phase_signal=previous_phase_signal,
        ):
            yield ev
    else:
        for ev, _part_idx in chain_act_evts:
            yield ev
        if to_front_fn is not None:
            yield {"type": "state", "data": to_front_fn(state)}

    try:
        end_turn_quest_check(state)
    except NotImplementedError:
        pass
    tick_turn_buffs(state, dirty)
    async for ev in finalize(state, save_repo, dirty, to_front_fn):
        yield ev


