"""Single-verb dispatch.

Split out of `turn.py` once `_dispatch_verb` grew past 300 lines. Owns the
per-verb routing for non-chain dispatch.
"""

import random
from collections.abc import AsyncIterator, Callable

from src.llm.calls.classify.schema import Verb
from src.llm.client import LLMClient
from src.db.repo import SaveRepo, ScenarioRepo
from ..domain.state import GameState
from ..ontology.graph import GameGraph
from ._diag import diag, fmt_verb
from .actions import emit_cast, emit_move, emit_use
from .buff_tick import tick_turn_buffs
from .chain import (
    _enter_combat_and_finalize,
    _is_receipt,
    _resolve_transfer_emit,
)
from .combat_phase import has_invalid_combat_targets
from .dirty import (
    Dirty,
    ToFrontFn,
    drop_pushed_act,
    finalize,
    push_act,
)
from .error_phrases import is_dramatic_fail
from .format import (
    FLEE_OUTSIDE_COMBAT_TEXT,
    NO_COMBAT_TARGETS_TEXT,
)
from .narrate import (
    emit_fail_line_and_finalize,
    narrate_absorb_and_finalize,
    stream_narrate_tail,
)
from .rest import run_rest


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
    diag(
        state.game_id, state.turn_count,
        "step:fail" if is_failure else "step:ok",
        verb=fmt_verb(result),
        reasons=failure_raws if is_failure else None,
    )
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
        async for ev in narrate_absorb_and_finalize(
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
        async for ev in narrate_absorb_and_finalize(
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
            async for ev in narrate_absorb_and_finalize(
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
        if intent == "accept" and target:
            # Engine flips the NPC's first locked quest to active before
            # narrate runs — body lands first, deferred 퀘스트 시작 card flushes
            # after. No-op when the NPC has no locked quest to give; falls
            # through to the friendly narrate path so prose still covers the
            # beat.
            from ..engines.quest import accept_npc_locked_quest

            accept_npc_locked_quest(state, graph, target, dirty)
            async for ev in narrate_absorb_and_finalize(
                client, state, scenario_repo, save_repo, dirty,
                to_front_fn, player_input, verb, graph, previous_phase_signal,
            ):
                yield ev
            return
        if intent == "abandon" and target:
            # Mirror of accept: engine flips the NPC's active quest to failed
            # before narrate. No-op when the NPC has no active quest from the
            # player.
            from ..engines.quest import abandon_npc_active_quest

            abandon_npc_active_quest(state, graph, target, dirty)
            async for ev in narrate_absorb_and_finalize(
                client, state, scenario_repo, save_repo, dirty,
                to_front_fn, player_input, verb, graph, previous_phase_signal,
            ):
                yield ev
            return
        # friendly/hostile/deceptive: absorbed by narrate — narrate emits
        # the affinity state_change keyed off intent's tone.
        async for ev in narrate_absorb_and_finalize(
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
            async for ev in emit_fail_line_and_finalize(
                client,
                state,
                scenario_repo,
                save_repo,
                dirty,
                to_front_fn,
                fail_line=FLEE_OUTSIDE_COMBAT_TEXT,
                player_input=player_input,
                graph=graph,
                previous_phase_signal=previous_phase_signal,
            ):
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
            async for ev in emit_fail_line_and_finalize(
                client,
                state,
                scenario_repo,
                save_repo,
                dirty,
                to_front_fn,
                fail_line=NO_COMBAT_TARGETS_TEXT,
                player_input=player_input,
                graph=graph,
                previous_phase_signal=previous_phase_signal,
            ):
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
