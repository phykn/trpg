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
from ..ontology.graph import build_graph
from ..ontology.target_view import build_target_view
from ..domain.state import GameState
from ..context import (
    build_history_layer,
    build_session_layer,
    build_surroundings,
    build_world_layer,
)
from .dirty import (
    Dirty,
    next_log_id,
    push_dialogue,
    push_log_entry,
    push_turn_log,
)
from .memory_writer import write_memories


# --- run_narrate -----------------------------------------------------------


async def run_narrate(
    client: LLMClient,
    state: GameState,
    profile_dir: str,
    player_input: str,
    judge_result: dict,
    grade: str | None = None,
    target_id: str | None = None,
) -> AsyncIterator[NarrativeDelta | NarrativeFinal]:
    """Yields NarrativeDelta tokens, then a final NarrativeFinal.

    target_view assembly:
    - action='roll' / 'pass': use `target_id` if given, else first of
      judge_result.targets. pass picks up target_view too because dialogue
      turns ('말 건다', '인사한다') route here and narrate needs the NPC's
      memories/tone_hint/disposition to stay tonally consistent.
    - action='reject': no target_view (surroundings only).

    reject post-processing: forces empty state_changes / memorable=false on the
    final NarrateOutput (engine-side enforcement; narrator is *also* told to do
    this in the prompt, but we don't trust LLM here).
    """
    action = judge_result.get("action")

    target_view = None
    if action in ("roll", "pass"):
        chosen = target_id
        if chosen is None:
            targets = judge_result.get("targets") or []
            if targets:
                chosen = targets[0]
        if chosen is not None:
            graph = build_graph(state)
            target_view = build_target_view(state, graph, chosen, state.player_id)

    input_ = NarrateInput(
        world=build_world_layer(profile_dir, state.profile),
        session=build_session_layer(state),
        history=build_history_layer(state),
        target_view=target_view,
        surroundings=build_surroundings(state, state.player_id),
        judge_result=judge_result,
        grade=grade,
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


# --- reject sterilizer -----------------------------------------------------


def _sterilize_for_reject(output) -> None:
    """Reject path must produce zero side effects: empty state_changes, no
    memory, no suggestions. The narrate prompt also tells the LLM to do
    this, but we don't trust the LLM here — engine-side enforcement."""
    output.state_changes = []
    output.memorable = False
    output.memory_targets = []
    output.memory = {}
    output.memory_links = {}
    output.importance = None
    output.suggestions = []


# --- player-move reconcile (pass action) -----------------------------------


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
    """When judge picks `pass targets=[loc_id]` and that loc differs from the
    player's current location, that's the player's movement intent. Returns
    the destination loc id or None."""
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
    """Pre-apply the player's relocation before narrate streams, so panels and
    the narrate prompt's surroundings both treat the destination as already
    reached. After this runs, `_reconcile_player_move` becomes a no-op for the
    move (player.location_id == expected → returns None), and any leftover
    relocation deltas narrate still emits get stripped by the same path."""
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
    """Resolve narrate's player-relocation output against judge's intent.

    - No movement intent (no location target) → strip any player relocations
      narrate emitted (e.g., '잠시 숨을 고른다' shouldn't move the player).
    - Movement intent → keep player moves only if they match the expected
      destination, drop hallucinated moves to other locations, and auto-inject
      a `move` change if narrate forgot to emit one (the bug where prose
      reads '여관에 들어선다' but state stays at town_square)."""
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


# --- consume_narrate -------------------------------------------------------


async def consume_narrate(
    state: GameState,
    dirty: Dirty,
    stream: AsyncIterator[NarrativeDelta | NarrativeFinal],
    *,
    target_for_log: str | None,
    dialogue_input: str | None,
) -> AsyncIterator[dict]:
    """Drive a `run_narrate` stream: emit `narrative_delta` SSE events as body
    tokens arrive, then commit the post-narrate tail (state_changes, turn_log,
    optional dialogue, memory writes, GM log line). The caller still owns the
    `run_narrate` kwargs (judge_result, grade, target_id) and just hands us
    the resulting iterator.

    `dialogue_input=None` skips the dialogue push (used by intro, which has
    no player utterance).
    """
    final: NarrativeFinal | None = None
    async for item in stream:
        if isinstance(item, NarrativeDelta):
            yield {"type": "narrative_delta", "data": {"text": item.text}}
        else:
            final = item

    # Narrate guarantee: even when the LLM produces nothing usable (empty
    # body after retries, or the stream short-circuited without a final),
    # the narrator must still say something. Otherwise the turn looks broken
    # — typing dots vanish and no GM line lands. Fall back to a deterministic
    # "잠시 정적이 흐른다" and stream it as a delta so the client sees it.
    if final is None:
        final = NarrativeFinal(body="", output=NarrateOutput())
    body = final.body.strip()
    if not body:
        body = "잠시 정적이 흐른다."
        yield {"type": "narrative_delta", "data": {"text": body}}

    yield {"type": "suggestions", "data": {"items": list(final.output.suggestions)}}

    apply_changes(state, final.output.state_changes, dirty.entities)
    push_turn_log(state, target_for_log, final.output.turn_summary, dirty)
    if dialogue_input is not None:
        push_dialogue(state, dialogue_input, body, dirty)
    write_memories(state, final.output, turn=state.turn_count, dirty=dirty.entities)
    gm_log = GMLogEntry(id=next_log_id(state), kind="gm", text=body)
    push_log_entry(state, gm_log, dirty)
