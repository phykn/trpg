import random
from collections.abc import AsyncIterator

from pydantic import ValidationError

from src.llm.calls.classify.schema import JudgeOutput, Verb
from ..domain.errors import JudgeMalformed, PendingCheckActive
from ..domain.memory import PlayerLogEntry
from ..domain.state import GameState
from src.llm.client import LLMClient, set_llm_session_if_unset
from src.db.repo import SaveRepo, ScenarioRepo
from .buff_tick import tick_turn_buffs
from .chain import _run_verb_chain
from .combat_phase import run_combat_player_turn
from ._diag import diag, fmt_verb, set_diag_context
from .dispatch import _dispatch_verb
from src.wire.emit import (
    emit_judge_refuse,
    emit_judge_verb,
    emit_judge_verbs,
    emit_log_entry,
)
from .dirty import (
    Dirty,
    ToFrontFn,
    finalize,
    flush_deferred_act_cards,
    next_log_id,
    persist_on_exit,
    push_act,
    push_log_entry,
)
from .format import GAME_OVER_TEXT
from .judge import run_judge
from .narrate import (
    emit_input_rejected_and_finalize,
    narrate_absorb_and_finalize,
    stream_narrate_tail,
)
from .subject import refresh_active_subject
from ..engines.quest import abandon_quest, accept_quest


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
    inner = _run_turn_inner(
        client,
        state,
        scenario_repo,
        save_repo,
        player_input,
        dirty,
        to_front_fn,
        rng,
        quest_action,
    )
    async for ev in persist_on_exit(state, save_repo, dirty, to_front_fn, inner):
        yield ev


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
    set_diag_context(state.game_id, state.turn_count)
    diag(state.game_id, state.turn_count, "turn:start", input=player_input)

    if quest_action is not None:
        kind, qid = quest_action
        diag(state.game_id, state.turn_count, "quest:action", kind=kind, qid=qid)
        if kind == "accept":
            accept_quest(state, qid, dirty)
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
    # in-world action). Drain quest start/fail cards before finalize so the
    # client sees the in-game ack.
    if quest_action is not None and not player_input:
        for ev in flush_deferred_act_cards(state, dirty):
            yield ev
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
        diag(state.game_id, state.turn_count, "classify -> JudgeMalformed")
        async for ev in narrate_absorb_and_finalize(
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
            diag(
                state.game_id,
                state.turn_count,
                "classify -> refuse",
                category=result.refuse.category,
            )
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
            diag(
                state.game_id,
                state.turn_count,
                "classify -> single",
                verb=fmt_verb(single_verb),
            )
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
                async for ev in emit_input_rejected_and_finalize(
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
            diag(
                state.game_id,
                state.turn_count,
                "classify -> chain",
                verbs=[fmt_verb(v) for v in verbs],
            )
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
                async for ev in emit_input_rejected_and_finalize(
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


