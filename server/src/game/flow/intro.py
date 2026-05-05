"""GM intro — scene-zero narration. No judge, no turn bump."""

from collections.abc import AsyncIterator

from ..domain.state import GameState
from ...llm.client import LLMClient, set_llm_session_if_unset
from ...persistence.repo import SaveRepo, ScenarioRepo
from .dirty import Dirty, ToFrontFn, finalize
from .narrate import consume_narrate, run_narrate


async def run_intro(
    client: LLMClient,
    state: GameState,
    scenario_repo: ScenarioRepo,
    save_repo: SaveRepo,
    *,
    to_front_fn: ToFrontFn | None = None,
) -> AsyncIterator[dict]:
    """First GM intro, called once right after game start. Skips judge and
    only calls narrate. turn_count stays at zero (= day_phase 'dawn')."""
    set_llm_session_if_unset(state.game_id)
    dirty = Dirty()
    graph = state.graph()
    stream = run_narrate(
        client,
        state,
        scenario_repo,
        "",
        judge_result={"action": "intro"},
        graph=graph,
        grade=None,
    )
    async for ev in consume_narrate(
        state,
        dirty,
        stream,
        target_for_log=None,
        dialogue_input=None,
        graph=graph,
    ):
        yield ev

    async for ev in finalize(state, save_repo, dirty, to_front_fn):
        yield ev
