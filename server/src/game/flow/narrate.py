import logging
import re
from collections.abc import AsyncIterator

from src.locale import render
from src.llm.calls.classify.schema import Verb
from src.wire.emit import emit_error, emit_log_entry, emit_narrative_delta
from src.llm.calls.narrate import (
    NarrateInput,
    NarrateOutput,
    NarrativeDelta,
    NarrativeFinal,
    stream_narrate,
)
from ..domain.memory import GMLogEntry
from ..engines.apply import apply_changes
from ..engines.invariants import enforce_item_locality
from src.llm.client import LLMClient
from ..ontology.graph import GameGraph
from ..ontology.player_view import build_player_view
from ..ontology.queries import inhabitants_of
from ..ontology.target_view import build_target_view
from src.db.repo import ScenarioRepo, SaveRepo
from ..domain.state import GameState
from src.llm.context import (
    build_history_layer,
    build_session_layer,
    build_surroundings,
    build_world_layer,
    redact_dead_quotes,
)
from .buff_tick import tick_turn_buffs
from .dirty import (
    Dirty,
    ToFrontFn,
    finalize,
    flush_deferred_act_cards,
    next_log_id,
    push_dialogue,
    push_log_entry,
    push_turn_log,
)
from .format import (
    INPUT_REJECTED_TEXT,
    format_affinity_card_log,
    format_quest_start_log,
)
from .memory_writer import write_memories


_log = logging.getLogger(__name__)


async def run_narrate(
    client: LLMClient,
    state: GameState,
    scenario_repo: ScenarioRepo,
    player_input: str,
    judge_result: dict,
    *,
    graph: GameGraph,
    grade: str | None = None,
    target_id: str | None = None,
    act_log_lines: list[str] | None = None,
    previous_phase_signal: str | None = None,
    recent_engine_events: list[dict] | None = None,
) -> AsyncIterator[NarrativeDelta | NarrativeFinal]:
    """Yield NarrativeDelta tokens then NarrativeFinal. action='reject' is forced empty state_changes / memorable=false engine-side regardless of what the LLM returns."""
    action = judge_result.get("action")

    target_view = None
    if action in ("roll", "pass"):
        chosen = target_id
        if chosen is None:
            targets = judge_result.get("targets") or []
            if targets:
                chosen = targets[0]
        if chosen is not None:
            target_view = build_target_view(
                state, graph, chosen, state.player_id, grade=grade
            )

    surroundings = build_surroundings(state, state.player_id, graph)
    # Recovery beat: prior fight + memories would pull stale events into the aftermath; zero them so prose stays in the moment.
    is_recovery = previous_phase_signal == "downed_recovered"
    history_str = (
        ""
        if is_recovery
        else build_history_layer(state, surroundings.get("corpses", []))
    )
    player_view = build_player_view(state)
    if is_recovery:
        player_view = {**player_view, "memories": []}
    input_ = NarrateInput(
        world=await build_world_layer(scenario_repo, state.profile),
        session=build_session_layer(state),
        history=history_str,
        player_view=player_view,
        target_view=target_view,
        surroundings=surroundings,
        judge_result=judge_result,
        grade=grade,
        act_log_lines=act_log_lines or [],
        previous_phase_signal=previous_phase_signal,
        recent_engine_events=recent_engine_events or [],
        player_input=player_input,
    )

    async for item in stream_narrate(client, input_, state.locale):
        if isinstance(item, NarrativeFinal) and action == "reject":
            _sterilize_for_reject(item.output)
        yield item


# Engine ids are lowercase ASCII with an underscore — a token matching this shape in player-facing text is a prompt slip.
_ID_TOKEN = re.compile(r"\b[a-z][a-z0-9]*(?:_[a-z0-9]+)+\b")
_PAREN_ID = re.compile(
    r"\s*[\(\[（［][^\(\[\)\]）］]*[a-z][a-z0-9]*(?:_[a-z0-9]+)+[^\(\[\)\]）］]*[\)\]）］]"
)


def _strip_id_leaks(suggestions: list[str]) -> list[str]:
    """Remove parenthetical id glosses ('촌장의 부탁 (q_chief_request)') and drop
    any suggestion still carrying a bare id token after the strip."""
    cleaned: list[str] = []
    for s in suggestions:
        stripped = _PAREN_ID.sub("", s).strip()
        if not stripped or _ID_TOKEN.search(stripped):
            continue
        cleaned.append(stripped)
    return cleaned


def _sterilize_for_reject(output) -> None:
    """Engine-side enforcement: reject must produce zero side effects, regardless of what the LLM emitted."""
    output.state_changes = []
    output.memorable = False
    output.memory_targets = []
    output.memory = {}
    output.memory_links = {}
    output.importance = None
    output.suggestions = []


async def consume_narrate(
    state: GameState,
    dirty: Dirty,
    stream: AsyncIterator[NarrativeDelta | NarrativeFinal],
    *,
    target_for_log: str | None,
    dialogue_input: str | None,
    graph: GameGraph | None = None,
) -> AsyncIterator[dict]:
    """Stream narrate body, then commit the post-narrate tail.
    `dialogue_input=None` skips the dialogue push (intro)."""
    if graph is None:
        graph = state.graph()
    final: NarrativeFinal | None = None
    async for item in stream:
        if isinstance(item, NarrativeDelta):
            yield emit_narrative_delta(item.text)
        else:
            final = item

    # Fallback "잠시 정적이 흐릅니다" — without it an empty narrate leaves the turn looking broken (no GM line lands).
    if final is None:
        final = NarrativeFinal(body="", output=NarrateOutput())
    if final.parse_error:
        # Body has already streamed by the time we know the JSON tail is malformed; runner can't retry, so surface as SSE error so the dropped state_changes/memory aren't silent.
        yield emit_error("NarrateMalformed")
    body = final.body.strip()
    if not body:
        body = render("log.narrate.fallback", "ko")
        yield emit_narrative_delta(body)

    # Redact dead-NPC direct quotes before persisting — without this a single LLM slip lands in recent_dialogue and compounds across turns.
    body = redact_dead_quotes(body, _dead_names_in_scope(state, graph))

    final.output.suggestions = _strip_id_leaks(final.output.suggestions)
    dirty.narrate_suggestions = list(final.output.suggestions)

    apply_result = apply_changes(state, final.output.state_changes, dirty)
    locality_warnings = enforce_item_locality(state, dirty=dirty.entities)
    for warning in locality_warnings:
        # Auto-repair telemetry — server logs only; engine-internal text (English + ids) must never reach the player log.
        _log.warning("item_locality_repair: %s", warning)
    state.invalidate_graph()
    push_turn_log(state, target_for_log, final.output.turn_summary, dirty)
    if dialogue_input is not None:
        push_dialogue(state, dialogue_input, body, dirty)
    write_memories(state, final.output, turn=state.turn_count, dirty=dirty.entities)
    # GM body lands and SSE-emits before reaction cards so the client clears the in-flight stream and reaction cards (affinity, quest-start) render after the prose that justifies them.
    gm_log = GMLogEntry(id=next_log_id(state), kind="gm", text=body)
    push_log_entry(state, gm_log, dirty)
    yield emit_log_entry(gm_log)
    # Quest-start and affinity cards stash into the deferred queue so they
    # flush together with quest success/failure — single ordering invariant
    # for all reaction cards (always after the gm body that motivated them).
    for q_id in apply_result["started_quests"]:
        quest = state.quests.get(q_id)
        if quest is None:
            continue
        text = format_quest_start_log(quest.title)
        dirty.deferred_act_cards.append((text, text))
    for npc_id, delta in apply_result["affinity_deltas"]:
        if delta == 0:
            continue
        npc = state.characters.get(npc_id)
        if npc is None:
            continue
        text = format_affinity_card_log(npc.name, delta)
        dirty.deferred_act_cards.append((text, text))
    # Drain all deferred reaction cards (quest_start, affinity) so they emit
    # AFTER the gm body that motivated them.
    for ev in flush_deferred_act_cards(state, dirty):
        yield ev


async def stream_narrate_tail(
    client: LLMClient,
    state: GameState,
    scenario_repo: ScenarioRepo,
    player_input: str,
    dirty: Dirty,
    to_front_fn: ToFrontFn | None,
    action: Verb,
    *,
    graph: GameGraph,
    act_log_lines: list[str] | None = None,
    previous_phase_signal: str | None = None,
    recent_engine_events: list[dict] | None = None,
) -> AsyncIterator[dict]:
    """Emit a state event, then drive narrate. Empty player_input is the post-combat / intro signal — dialogue push is skipped so recent_dialogue isn't polluted with a blank turn."""
    is_pass = action.name == "wait"
    target_for_log = action.target_ids[0] if (is_pass and action.target_ids) else None

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
        recent_engine_events=recent_engine_events,
    )
    dialogue_input = player_input if player_input else None
    async for ev in consume_narrate(
        state,
        dirty,
        stream,
        target_for_log=target_for_log,
        dialogue_input=dialogue_input,
        graph=graph,
    ):
        yield ev


def _dead_names_in_scope(state: GameState, graph: GameGraph | None = None) -> list[str]:
    """Dead NPCs visible to the narrate prompt — same scope as `_corpses_payload`."""
    if graph is None:
        graph = state.graph()
    actor = state.characters.get(state.player_id)
    if actor is None or actor.location_id is None:
        return []
    seen: set[str] = set()
    names: list[str] = []
    for cid in inhabitants_of(graph, actor.location_id):
        if cid == actor.id:
            continue
        ch = state.characters.get(cid)
        if ch is None or ch.alive:
            continue
        names.append(ch.name)
        seen.add(cid)
    for entry in state.turn_log:
        tid = entry.target
        if tid is None or tid == actor.id or tid in seen:
            continue
        ch = state.characters.get(tid)
        if ch is None or ch.alive:
            continue
        names.append(ch.name)
        seen.add(tid)
    return names


async def narrate_absorb_and_finalize(
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
    buff tick + finalize. Without the finalize tail, narrate's state_changes
    (e.g. affinity drops) and pushed cards live only in dirty and vanish on
    the next /turn reload."""
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


async def emit_input_rejected_and_finalize(
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
