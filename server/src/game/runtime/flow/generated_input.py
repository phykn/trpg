from typing import Any, Awaitable, Callable

from src.db.repo import GraphRepo
from src.game.domain.action import Action
from src.game.domain.graph import GraphChange
from src.game.domain.graph.apply import apply_graph_changes
from src.game.domain.story_contract import StoryContract
from src.game.domain.story_patch import StoryWriteIntent, StoryWriteResponse
from src.game.engines.story_patch_apply import story_patches_to_graph_changes
from src.game.engines.story_patch_validator import validate_story_write_response
from src.llm.calls.story_write import story_write
from src.llm.context.story_write_context import build_story_write_input
from src.llm.diag import engine_diag
from src.wire.graph.to_front import graph_to_front_state

from ..request_result import GraphActionRequestResult


StoryWriter = Callable[..., Awaitable[StoryWriteResponse]]


def derive_story_write_intent(action: Action) -> StoryWriteIntent:
    if action.verb == "perceive":
        return StoryWriteIntent(kind="clue_candidate", reason="perception action")
    if action.verb in {"transfer", "move", "use", "attack", "decide"}:
        return StoryWriteIntent(kind="memory_candidate", reason="accepted action")
    return StoryWriteIntent(kind="none")


async def apply_generated_story_after_action(
    *,
    client: Any,
    repo: GraphRepo,
    result: GraphActionRequestResult,
    contract: StoryContract | None,
    player_input: str,
    action: Action,
    writer: StoryWriter = story_write,
) -> GraphActionRequestResult:
    if contract is None or result.status != "executed":
        return result

    intent = derive_story_write_intent(action)
    if intent.kind == "none":
        return result

    response = await writer(
        client=client,
        input_=build_story_write_input(
            result.runtime,
            contract=contract,
            intent=intent,
            player_input=player_input,
            action=action,
        ),
        locale=result.runtime.progress.locale,
    )
    validation = validate_story_write_response(
        response,
        graph=result.runtime.graph,
        contract=contract,
    )
    if not validation.ok:
        engine_diag(
            "story_write:reject",
            reasons=",".join(validation.reasons),
        )
        return result

    changes = story_patches_to_graph_changes(
        response.patches,
        graph=result.runtime.graph,
        player_id=result.runtime.progress.player_id,
        turn_id=result.runtime.progress.turn_count,
    )
    if not changes:
        return result

    next_graph = apply_graph_changes(result.runtime.graph, changes)
    await repo.save_graph_changes(
        result.runtime.progress.game_id,
        next_graph,
        changed_node_ids=_changed_node_ids(changes),
        changed_edge_ids=_changed_edge_ids(changes),
        removed_edge_ids=[],
    )
    next_runtime = result.runtime.model_copy(update={"graph": next_graph})
    return result.model_copy(
        update={
            "runtime": next_runtime,
            "front_state": graph_to_front_state(next_runtime),
        }
    )


def _changed_node_ids(changes: list[GraphChange]) -> list[str]:
    return [
        change.node.id
        for change in changes
        if getattr(change, "type", None) == "add_node"
    ]


def _changed_edge_ids(changes: list[GraphChange]) -> list[str]:
    return [
        change.edge.id
        for change in changes
        if getattr(change, "type", None) == "add_edge"
    ]
