from collections.abc import AsyncIterator

from ..agents.narrate import (
    NarrateInput,
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
    - action='roll': use `target_id` if given, else first of judge_result.targets.
    - action='pass' / 'reject': no target_view (surroundings only).

    reject post-processing: forces empty state_changes / memorable=false on the
    final NarrateOutput (engine-side enforcement; narrator is *also* told to do
    this in the prompt, but we don't trust LLM here).
    """
    action = judge_result.get("action")

    target_view = None
    if action == "roll":
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
                item.output.state_changes = []
                item.output.memorable = False
                item.output.memory_targets = []
                item.output.memory = {}
                item.output.memory_links = {}
                item.output.importance = None
                item.output.suggestions = []
            elif action == "pass":
                # Narrator must not relocate the player on a "stand still"-style
                # action — survivor t8 produced a player move on a "잠시 숨을 고른다"
                # input. Strip player-relocation changes; leave NPC moves alone.
                item.output.state_changes = [
                    c for c in item.output.state_changes
                    if not _is_player_relocation(c, state.player_id)
                ]
        yield item


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
    assert final is not None

    yield {"type": "suggestions", "data": {"items": list(final.output.suggestions)}}

    apply_changes(state, final.output.state_changes, dirty.entities)
    push_turn_log(state, target_for_log, final.output.turn_summary, dirty)
    if dialogue_input is not None:
        push_dialogue(state, dialogue_input, final.body, dirty)
    write_memories(state, final.output, turn=state.turn_count, dirty=dirty.entities)
    gm_log = GMLogEntry(id=next_log_id(state), kind="gm", text=final.body)
    push_log_entry(state, gm_log, dirty)
