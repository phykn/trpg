from collections.abc import AsyncIterator

from ..llm_calls.classify.schema import PassAction, RejectAction
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
    next_log_id,
    push_dialogue,
    push_log_entry,
    push_turn_log,
)
from .judge import judge_quest_progress
from .memory_writer import write_memories


def npc_dialogue_quest_check(state: GameState, claim: str, npc_id: str) -> None:
    """During NPC dialogue, run free-path judge for quests given by this NPC."""
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
        apply_judge_result(state, quest.id, result)


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

    surroundings = build_surroundings(state, state.player_id, graph, grade=grade)
    input_ = NarrateInput(
        world=await build_world_layer(scenario_repo, state.profile),
        session=build_session_layer(state),
        history=build_history_layer(state, surroundings.get("corpses", [])),
        player_view=build_player_view(state),
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


def _sterilize_for_reject(output) -> None:
    """Engine-side enforcement: reject must produce zero side effects, regardless of what the LLM emitted."""
    output.state_changes = []
    output.memorable = False
    output.memory_targets = []
    output.memory = {}
    output.memory_links = {}
    output.importance = None


async def consume_narrate(
    state: GameState,
    dirty: Dirty,
    stream: AsyncIterator[NarrativeDelta | NarrativeFinal],
    *,
    target_for_log: str | None,
    dialogue_input: str | None,
    graph: GameGraph | None = None,
) -> AsyncIterator[dict]:
    """Stream narrate body, then commit the post-narrate tail. `dialogue_input=None` skips the dialogue push (intro)."""
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
        yield {
            "type": "error",
            "data": {"message": final.parse_error, "code": "NarrateParseFailed"},
        }
    body = final.body.strip()
    if not body:
        body = "잠시 정적이 흐릅니다."
        yield {"type": "narrative_delta", "data": {"text": body}}

    # Redact dead-NPC direct quotes before persisting — without this a single LLM slip lands in recent_dialogue and compounds across turns.
    body = redact_dead_quotes(body, _dead_names_in_scope(state, graph))

    apply_changes(state, final.output.state_changes, dirty.entities)
    locality_warnings = enforce_item_locality(state, dirty=dirty.entities)
    for warning in locality_warnings:
        gm_log = GMLogEntry(id=next_log_id(state), kind="gm", text=warning)
        push_log_entry(state, gm_log, dirty)
    state.invalidate_graph()
    push_turn_log(state, target_for_log, final.output.turn_summary, dirty)
    if dialogue_input is not None:
        push_dialogue(state, dialogue_input, body, dirty)
    write_memories(state, final.output, turn=state.turn_count, dirty=dirty.entities)
    gm_log = GMLogEntry(id=next_log_id(state), kind="gm", text=body)
    push_log_entry(state, gm_log, dirty)


async def stream_narrate_tail(
    client: LLMClient,
    state: GameState,
    scenario_repo: ScenarioRepo,
    player_input: str,
    dirty: Dirty,
    to_front_fn: ToFrontFn | None,
    action: PassAction | RejectAction,
    *,
    graph: GameGraph,
    act_log_lines: list[str] | None = None,
    previous_phase_signal: str | None = None,
    recent_engine_events: list[dict] | None = None,
) -> AsyncIterator[dict]:
    """Emit a state event, then drive narrate. Empty player_input is the post-combat / intro signal — dialogue push is skipped so recent_dialogue isn't polluted with a blank turn."""
    if isinstance(action, PassAction):
        target_for_log = action.targets[0] if action.targets else None
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
