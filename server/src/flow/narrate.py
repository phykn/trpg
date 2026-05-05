import logging
import re
from collections.abc import AsyncIterator

from ..locale import render
from ..llm_calls.classify.schema import Verb
from ..wire.emit import emit_error, emit_log_entry
from ..llm_calls.narrate import (
    NarrateInput,
    NarrateOutput,
    NarrativeDelta,
    NarrativeFinal,
    stream_narrate,
)
from ..domain.memory import GMLogEntry
from ..engines.apply import apply_changes
from ..engines.invariants import enforce_item_locality
from ..engines.quest import apply_judge_result
from ..llm.client import LLMClient
from ..ontology.graph import GameGraph
from ..ontology.player_view import build_player_view
from ..ontology.queries import giver_of, inhabitants_of
from ..ontology.target_view import build_target_view
from ..persistence.repo import ScenarioRepo
from ..domain.state import GameState
from ..context import (
    build_history_layer,
    build_session_layer,
    build_surroundings,
    build_world_layer,
    redact_dead_quotes,
)
from .dirty import (
    Dirty,
    ToFrontFn,
    flush_deferred_act_cards,
    next_log_id,
    push_dialogue,
    push_log_entry,
    push_turn_log,
)
from .format import (
    format_affinity_card_log,
    format_affinity_card_turn_log,
    format_quest_start_log,
    format_quest_start_turn_log,
)
from .judge import judge_quest_progress
from .memory_writer import write_memories


_log = logging.getLogger(__name__)


def npc_dialogue_quest_check(
    state: GameState, claim: str, npc_id: str, dirty=None
) -> None:
    """During NPC dialogue, run free-path judge for quests given by this NPC.
    `dirty` (when full Dirty) lets a satisfied judgment push the success card."""
    history = [{"summary": e.summary} for e in state.turn_log[-5:]]
    graph = state.graph()
    npc = state.characters.get(npc_id)
    npc_favor = npc.relations.get(state.player_id, 0) if npc else 0
    for quest in list(state.quests.values()):
        if quest.status != "active":
            continue
        if giver_of(graph, quest.id) != npc_id:
            continue
        result = judge_quest_progress(
            quest={
                "id": quest.id,
                "objective_text": quest.objective_text or quest.title,
            },
            history=history,
            claim=claim,
            npc_context={"npc_id": npc_id, "favor": npc_favor},
        )
        apply_judge_result(state, quest.id, result, dirty)


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

    async for item in stream_narrate(client, input_):
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
    npc_dialogue_target: str | None = None,
) -> AsyncIterator[dict]:
    """Stream narrate body, then commit the post-narrate tail. `dialogue_input=None` skips the dialogue push (intro).
    `npc_dialogue_target` (an NPC id) triggers the post-body free-path quest judge so any success card lands AFTER the gm prose."""
    if graph is None:
        graph = state.graph()
    final: NarrativeFinal | None = None
    async for item in stream:
        if isinstance(item, NarrativeDelta):
            yield {"type": "narrative_delta", "data": {"text": item.text}}
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
        yield {"type": "narrative_delta", "data": {"text": body}}

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
    # flush together with quest 성공/실패 — single ordering invariant for
    # all reaction cards (always after the gm body that motivated them).
    for q_id in apply_result["started_quests"]:
        quest = state.quests.get(q_id)
        if quest is None:
            continue
        dirty.deferred_act_cards.append(
            (
                format_quest_start_log(quest.title),
                format_quest_start_turn_log(quest.title),
            )
        )
    for npc_id, delta in apply_result["affinity_deltas"]:
        if delta == 0:
            continue
        npc = state.characters.get(npc_id)
        if npc is None:
            continue
        dirty.deferred_act_cards.append(
            (
                format_affinity_card_log(npc.name, delta),
                format_affinity_card_turn_log(npc.name, delta),
            )
        )
    # NPC dialogue free-path judge runs AFTER the gm body so any '퀘스트 성공/실패' card
    # emits through dirty.log past the prose that justifies it. Pre-existing dirty.log
    # length lets us drain only the cards the judge added.
    if npc_dialogue_target is not None and dialogue_input is not None:
        try:
            pre_log_len = len(dirty.log)
            npc_dialogue_quest_check(
                state, claim=dialogue_input, npc_id=npc_dialogue_target, dirty=dirty
            )
            for entry in dirty.log[pre_log_len:]:
                yield emit_log_entry(entry)
        except NotImplementedError:
            pass  # judge LLM stub; live turns stay safe
    # Drain all deferred reaction cards (quest_start, affinity, quest
    # 성공/실패) so they emit AFTER the gm body that motivated them.
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

    # NPC dialogue quest check resolves the npc target here, but the call itself
    # runs inside consume_narrate AFTER the gm body push so any '퀘스트 성공/실패'
    # card emits past the prose that justifies it.
    npc_dialogue_target: str | None = None
    if is_pass and target_for_log is not None:
        target_char = state.characters.get(target_for_log)
        if target_char is not None and not target_char.is_player:
            npc_dialogue_target = target_for_log

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
        npc_dialogue_target=npc_dialogue_target,
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
