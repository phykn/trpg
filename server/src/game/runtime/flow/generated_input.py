from typing import Any, Awaitable, Callable

from src.db.repo import GraphRepo
from src.game.domain.action import Action
from src.game.domain.graph import GraphChange
from src.game.domain.graph.apply import apply_graph_changes
from src.game.domain.story_contract import StoryContract
from src.game.domain.story_patch import StoryWriteIntent, StoryWriteResponse
from src.game.domain.story_patch_ledger import (
    StoryPatchLedgerEntry,
    StoryPatchLedgerStatus,
)
from src.game.engines.story_patch_apply import story_patches_to_graph_changes
from src.game.engines.story_patch_validator import validate_story_write_response
from src.game.runtime.state import GameRuntimeState
from src.llm.calls.story_write import story_write
from src.llm.context.story_write_context import build_story_write_input
from src.llm.diag import engine_diag
from src.wire.graph.to_front import graph_to_front_state

from ..request_result import GraphActionRequestResult


StoryWriter = Callable[..., Awaitable[StoryWriteResponse]]


def derive_story_write_intent(action: Action) -> StoryWriteIntent:
    if action.verb == "perceive":
        return StoryWriteIntent(kind="clue_candidate", reason="perception action")
    if action.verb == "speak":
        return StoryWriteIntent(kind="memory_candidate", reason="accepted dialogue")
    if action.verb in {"transfer", "move", "use", "attack", "decide"}:
        return StoryWriteIntent(kind="memory_candidate", reason="accepted action")
    return StoryWriteIntent(kind="none")


def story_write_intent_for_contract(
    action: Action,
    contract: StoryContract,
    *,
    runtime: GameRuntimeState | None = None,
) -> StoryWriteIntent:
    intent = derive_story_write_intent(action)
    if intent.kind == "none":
        return intent
    world_ops = {"add_location", "add_character", "add_item", "add_quest_beat"}
    if set(contract.allowed_ops).intersection(world_ops):
        if runtime is None:
            return StoryWriteIntent(kind="both", reason="world write allowed")
        if _has_recent_generated_discovery(runtime):
            return intent
        return StoryWriteIntent(kind="both", reason="no recent generated discoveries")
    return intent


async def apply_generated_story_after_action(
    *,
    client: Any,
    repo: GraphRepo,
    result: GraphActionRequestResult,
    contract: StoryContract | None,
    player_input: str,
    action: Action,
    accepted_narration: str | None = None,
    writer: StoryWriter = story_write,
) -> GraphActionRequestResult:
    if contract is None or result.status != "executed":
        return result

    intent = story_write_intent_for_contract(
        action,
        contract,
        runtime=result.runtime,
    )
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
            accepted_narration=accepted_narration,
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
        await repo.append_story_patch_entries(
            result.runtime.progress.game_id,
            [
                _ledger_entry(
                    result,
                    response=response,
                    intent=intent,
                    status="rejected",
                    rejected_reasons=validation.reasons,
                )
            ],
        )
        return result

    changes = story_patches_to_graph_changes(
        response.patches,
        graph=result.runtime.graph,
        player_id=result.runtime.progress.player_id,
        turn_id=result.runtime.progress.turn_count,
    )
    changed_node_ids = _changed_node_ids(changes)
    changed_edge_ids = _changed_edge_ids(changes)
    if not changes:
        await repo.append_story_patch_entries(
            result.runtime.progress.game_id,
            [
                _ledger_entry(
                    result,
                    response=response,
                    intent=intent,
                    status="accepted",
                    changed_node_ids=changed_node_ids,
                    changed_edge_ids=changed_edge_ids,
                )
            ],
        )
        return result

    next_graph = apply_graph_changes(result.runtime.graph, changes)
    await repo.save_graph_changes(
        result.runtime.progress.game_id,
        next_graph,
        changed_node_ids=changed_node_ids,
        changed_edge_ids=changed_edge_ids,
        removed_edge_ids=[],
    )
    await repo.append_story_patch_entries(
        result.runtime.progress.game_id,
        [
            _ledger_entry(
                result,
                response=response,
                intent=intent,
                status="accepted",
                changed_node_ids=changed_node_ids,
                changed_edge_ids=changed_edge_ids,
            )
        ],
    )
    next_runtime = result.runtime.model_copy(update={"graph": next_graph})
    next_runtime.__dict__.pop("graph_index", None)
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


def _has_recent_generated_discovery(runtime: GameRuntimeState) -> bool:
    threshold = max(0, runtime.progress.turn_count - 3)
    for node in runtime.graph.nodes.values():
        if node.type != "knowledge":
            continue
        props = node.properties
        if props.get("kind") not in {"memory", "clue"}:
            continue
        turn_id = props.get("turn_id")
        if isinstance(turn_id, int) and turn_id >= threshold:
            return True
    return False


def _changed_edge_ids(changes: list[GraphChange]) -> list[str]:
    return [
        change.edge.id
        for change in changes
        if getattr(change, "type", None) == "add_edge"
    ]


def _ledger_entry(
    result: GraphActionRequestResult,
    *,
    response: StoryWriteResponse,
    intent: StoryWriteIntent,
    status: StoryPatchLedgerStatus,
    rejected_reasons: list[str] | None = None,
    changed_node_ids: list[str] | None = None,
    changed_edge_ids: list[str] | None = None,
) -> StoryPatchLedgerEntry:
    return StoryPatchLedgerEntry(
        turn=result.runtime.progress.turn_count,
        status=status,
        intent_kind=intent.kind,
        reason=response.reason,
        patches=[patch.model_dump(mode="json") for patch in response.patches],
        rejected_reasons=rejected_reasons or [],
        changed_node_ids=changed_node_ids or [],
        changed_edge_ids=changed_edge_ids or [],
    )
