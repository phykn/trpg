"""GM intro — scene-zero narration. No judge, no turn bump."""
from collections.abc import AsyncIterator

from ..domain.state import GameState
from ..llm.client import LLMClient, set_llm_session_if_unset
from .dirty import Dirty, ToFrontFn, finalize
from .narrate import consume_narrate, run_narrate


async def run_intro(
    client: LLMClient,
    state: GameState,
    profile_dir: str,
    saves_dir: str,
    *,
    to_front_fn: ToFrontFn | None = None,
) -> AsyncIterator[dict]:
    """First GM intro, called once right after game start. Skips judge and
    only calls narrate. turn_count stays at zero (= day_phase '새벽')."""
    set_llm_session_if_unset(state.game_id)
    dirty = Dirty()
    stream = run_narrate(
        client,
        state,
        profile_dir,
        "",
        judge_result={"action": "intro"},
        grade=None,
    )
    async for ev in consume_narrate(
        state,
        dirty,
        stream,
        target_for_log=None,
        dialogue_input=None,
    ):
        yield ev

    async for ev in finalize(state, saves_dir, dirty, to_front_fn):
        yield ev
