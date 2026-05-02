import re
from collections.abc import AsyncIterator

from ..agents.narrate import (
    NarrateInput,
    NarrateOutput,
    NarrativeDelta,
    NarrativeFinal,
    stream_narrate,
)
from ..domain.memory import GMLogEntry
from ..engines.apply import apply_changes
from ..llm.client import LLMClient
from ..ontology.graph import GameGraph
from ..ontology.player_view import build_player_view
from ..ontology.queries import inhabitants_of
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
    next_log_id,
    push_dialogue,
    push_log_entry,
    push_turn_log,
)
from .memory_writer import write_memories


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
    body = final.body.strip()
    if not body:
        body = "잠시 정적이 흐릅니다."
        yield {"type": "narrative_delta", "data": {"text": body}}

    # Redact dead-NPC direct quotes before persisting — without this a single LLM slip lands in recent_dialogue and compounds across turns.
    body = redact_dead_quotes(body, _dead_names_in_scope(state, graph))

    final.output.suggestions = _strip_id_leaks(final.output.suggestions)
    yield {"type": "suggestions", "data": {"items": list(final.output.suggestions)}}

    apply_changes(state, final.output.state_changes, dirty.entities)
    state.invalidate_graph()
    push_turn_log(state, target_for_log, final.output.turn_summary, dirty)
    if dialogue_input is not None:
        push_dialogue(state, dialogue_input, body, dirty)
    write_memories(state, final.output, turn=state.turn_count, dirty=dirty.entities)
    gm_log = GMLogEntry(id=next_log_id(state), kind="gm", text=body)
    push_log_entry(state, gm_log, dirty)


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
