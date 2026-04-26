from collections.abc import AsyncIterator

from ..llm_client.agents.narrate import (
    NarrateInput,
    NarrativeDelta,
    NarrativeFinal,
    stream_narrate,
)
from ..llm_client.client import LLMClient
from ..ontology.graph import build_graph
from ..ontology.target_view import build_target_view
from ..state.models import GameState
from .context import (
    build_history_layer,
    build_session_layer,
    build_surroundings,
    build_world_layer,
)


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
        if isinstance(item, NarrativeFinal) and action == "reject":
            item.output.state_changes = []
            item.output.memorable = False
            item.output.memory_targets = []
            item.output.memory = {}
            item.output.memory_links = {}
            item.output.importance = None
        yield item
