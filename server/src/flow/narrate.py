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
        if isinstance(item, NarrativeFinal):
            if action == "reject":
                _sterilize_for_reject(item.output)
            elif action == "pass":
                item.output.state_changes = _reconcile_player_move(
                    item.output.state_changes,
                    judge_result,
                    state,
                )
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


def _is_player_relocation(change: dict, player_id: str) -> bool:
    t = change.get("type")
    if t == "move" and change.get("target") == player_id:
        return True
    if (
        t == "set"
        and change.get("entity") == "characters"
        and change.get("id") == player_id
        and change.get("field") == "location_id"
    ):
        return True
    return False


def _expected_destination(judge_result: dict, state: GameState) -> str | None:
    """Destination loc id when judge's `pass targets=[loc_id]` differs from the player's current location, else None."""
    targets = judge_result.get("targets") or []
    if not targets:
        return None
    first = targets[0]
    if first not in state.locations:
        return None
    player = state.characters.get(state.player_id)
    if player is None or player.location_id == first:
        return None
    return first


def apply_intended_move(
    state: GameState, judge_result: dict, dirty_entities: set
) -> None:
    """Pre-apply player relocation so panels + narrate surroundings see the destination as already reached."""
    expected = _expected_destination(judge_result, state)
    if expected is None:
        return
    apply_changes(
        state,
        [{"type": "move", "target": state.player_id, "destination": expected}],
        dirty_entities,
    )


def _reconcile_player_move(
    changes: list[dict], judge_result: dict, state: GameState
) -> list[dict]:
    """Reconcile narrate's player-relocation output with judge's intent: strip stray moves, inject a missing one if needed."""
    expected = _expected_destination(judge_result, state)
    player_id = state.player_id
    if expected is None:
        return [c for c in changes if not _is_player_relocation(c, player_id)]
    kept: list[dict] = []
    has_match = False
    for c in changes:
        if not _is_player_relocation(c, player_id):
            kept.append(c)
            continue
        dest = c.get("destination") if c.get("type") == "move" else c.get("value")
        if dest == expected:
            kept.append(c)
            has_match = True
    if not has_match:
        kept.append({"type": "move", "target": player_id, "destination": expected})
    return kept


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
