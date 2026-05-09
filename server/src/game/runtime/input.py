from __future__ import annotations

from src.db.repo import GraphRepo
from src.game.domain.action import verb_to_action
from src.llm.calls.classify.runner import classify
from src.llm.calls.classify.schema import JudgeInput
from src.llm.client import LLMClient
from src.llm.context.graph_surroundings import build_graph_surroundings

from .confirmation import GraphActionRequestResult, run_graph_action_request
from .load import load_runtime_state


class GraphInputError(ValueError):
    pass


async def run_graph_input_turn(
    client: LLMClient,
    repo: GraphRepo,
    game_id: str,
    player_input: str,
) -> GraphActionRequestResult:
    runtime = await load_runtime_state(repo, game_id)
    output = await classify(
        client,
        JudgeInput(
            player_input=player_input,
            surroundings=build_graph_surroundings(runtime),
        ),
        locale=runtime.progress.locale,
    )

    if output.refuse is not None:
        raise GraphInputError(output.refuse.reason)
    actions = output.actions or []
    if len(actions) != 1:
        raise GraphInputError("graph input requires exactly one action")

    return await run_graph_action_request(
        repo,
        game_id,
        verb_to_action(actions[0]),
    )
