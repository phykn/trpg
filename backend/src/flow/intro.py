"""GM intro — scene-zero narration. No judge, no turn bump."""
from collections.abc import AsyncIterator

from ..agents.narrate import NarrativeDelta, NarrativeFinal
from ..domain.memory import GMLogEntry
from ..domain.state import GameState
from ..engines.apply import apply_changes
from ..flow.memory_writer import write_memories
from ..llm.client import LLMClient
from .dirty import (
    Dirty,
    ToFrontFn,
    finalize,
    next_log_id,
    push_log_entry,
    push_turn_log,
)
from .narrate import run_narrate


async def run_intro(
    client: LLMClient,
    state: GameState,
    profile_dir: str,
    saves_dir: str,
    *,
    to_front_fn: ToFrontFn | None = None,
) -> AsyncIterator[dict]:
    """First GM intro, called once right after game start. Skips judge and
    only calls narrate. turn_count and world_time stay at zero."""
    dirty = Dirty()
    body = ""
    final: NarrativeFinal | None = None
    async for item in run_narrate(
        client,
        state,
        profile_dir,
        "",
        judge_result={"action": "intro"},
        grade=None,
    ):
        if isinstance(item, NarrativeDelta):
            yield {"type": "narrative_delta", "data": {"text": item.text}}
            body += item.text
        else:
            final = item
    assert final is not None

    apply_changes(state, final.output.state_changes, dirty.entities)
    push_turn_log(state, None, final.output.turn_summary, dirty)
    write_memories(state, final.output, turn=state.turn_count, dirty=dirty.entities)
    gm_log = GMLogEntry(id=next_log_id(state), kind="gm", text=body)
    push_log_entry(state, gm_log, dirty)

    async for ev in finalize(state, saves_dir, dirty, to_front_fn):
        yield ev
