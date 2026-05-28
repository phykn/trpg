from typing import Any, Awaitable, Callable

from src.db.repo import GraphRepo
from src.game.domain.action import Action
from src.game.domain.graph import GraphChange
from src.game.domain.graph.apply import apply_graph_changes
from src.game.domain.graph.query import location_of
from src.game.domain.story_contract import StoryContract
from src.game.domain.story_patch import StoryWriteIntent, StoryWriteResponse
from src.game.domain.story_patch_ledger import (
    StoryPatchLedgerEntry,
    StoryPatchLedgerStatus,
)
from src.game.engines.story_patch_apply import story_patches_to_graph_changes
from src.game.engines.story_patch_validator import validate_story_write_response
from src.game.runtime.state import GameRuntimeState
from src.locale.generated_story import (
    candidate_character_name,
    candidate_character_role,
    candidate_location_name,
    candidate_quest_beat,
    location_description,
    looks_actionable_for_story_patch,
    node_id_suffix,
)
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

    patch_required = _requires_actionable_patch(
        accepted_narration=accepted_narration,
        intent=intent,
        contract=contract,
    )
    response = await _call_writer_or_fallback(
        writer=writer,
        client=client,
        result=result,
        contract=contract,
        intent=intent,
        player_input=player_input,
        action=action,
        accepted_narration=accepted_narration,
        patch_required=patch_required,
        patch_reason="accepted narration names a player-actionable lead",
    )
    response = _fit_response_to_contract_budget(response, contract)
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
    if patch_required and not changes and not _is_writer_error_skip(response):
        response = await _call_writer_or_fallback(
            writer=writer,
            client=client,
            result=result,
            contract=contract,
            intent=intent.model_copy(
                update={"reason": "retry: accepted narration requires a graph patch"}
            ),
            player_input=player_input,
            action=action,
            accepted_narration=accepted_narration,
            patch_required=True,
            patch_reason=(
                "do not leave the actionable lead only in prose; "
                "write one allowed patch"
            ),
        )
        response = _fit_response_to_contract_budget(response, contract)
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
                    status="skipped",
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


async def _call_writer_or_fallback(
    *,
    writer: StoryWriter,
    client: Any,
    result: GraphActionRequestResult,
    contract: StoryContract,
    intent: StoryWriteIntent,
    player_input: str,
    action: Action,
    accepted_narration: str | None,
    patch_required: bool,
    patch_reason: str,
) -> StoryWriteResponse:
    try:
        return await writer(
            client=client,
            input_=build_story_write_input(
                result.runtime,
                contract=contract,
                intent=intent,
                player_input=player_input,
                action=action,
                accepted_narration=accepted_narration,
                patch_required=patch_required,
                patch_reason=patch_reason,
            ),
            locale=result.runtime.progress.locale,
        )
    except Exception as exc:
        fallback = _fallback_actionable_response(
            result.runtime,
            text=" ".join(filter(None, [accepted_narration, player_input])),
            contract=contract,
            reason=f"story_write fallback after {type(exc).__name__}",
        )
        if fallback is not None and (patch_required or intent.kind == "both"):
            engine_diag("story_write:fallback", err=type(exc).__name__)
            return fallback
        engine_diag("story_write:skip_after_error", err=type(exc).__name__)
        return StoryWriteResponse.model_validate(
            {
                "reason": f"story_write skipped after {type(exc).__name__}",
                "patches": [],
            }
        )


def _is_writer_error_skip(response: StoryWriteResponse) -> bool:
    return response.reason.startswith("story_write skipped after ")


def _fit_response_to_contract_budget(
    response: StoryWriteResponse,
    contract: StoryContract,
) -> StoryWriteResponse:
    patch_limit = contract.budgets.patches_per_turn
    term_limit = contract.budgets.new_terms_per_turn
    if len(response.patches) <= patch_limit and len(response.new_terms) <= term_limit:
        return response
    return response.model_copy(
        update={
            "patches": response.patches[:patch_limit],
            "new_terms": response.new_terms[:term_limit],
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


def _fallback_actionable_response(
    runtime: GameRuntimeState,
    *,
    text: str,
    contract: StoryContract,
    reason: str,
) -> StoryWriteResponse | None:
    if not text:
        return None
    location_id = location_of(runtime.graph, runtime.progress.player_id)
    if location_id is None:
        return None
    character_name = candidate_character_name(text)
    if "add_character" in contract.allowed_ops and character_name is not None:
        if _has_display_name(runtime, character_name):
            return None
        return StoryWriteResponse.model_validate(
            {
                "reason": reason,
                "patches": [
                    {
                        "op": "add_character",
                        "id": _unique_node_id(
                            runtime,
                            _node_id("char", character_name),
                        ),
                        "name": character_name,
                        "role": candidate_character_role(character_name),
                        "location_id": location_id,
                    }
                ],
            }
        )
    location_name = candidate_location_name(text)
    if "add_location" in contract.allowed_ops and location_name is not None:
        if _has_display_name(runtime, location_name):
            return None
        return StoryWriteResponse.model_validate(
            {
                "reason": reason,
                "patches": [
                    {
                        "op": "add_location",
                        "id": _unique_node_id(runtime, _node_id("loc", location_name)),
                        "name": location_name,
                        "description": location_description(location_name),
                        "connect_from": location_id,
                    }
                ],
            }
        )
    quest_beat = candidate_quest_beat(text)
    if "add_quest_beat" in contract.allowed_ops and quest_beat is not None:
        if _has_display_name(runtime, quest_beat["title"]):
            return None
        return StoryWriteResponse.model_validate(
            {
                "reason": reason,
                "patches": [
                    {
                        "op": "add_quest_beat",
                        "id": _unique_node_id(
                            runtime,
                            _node_id("quest", quest_beat["title"]),
                        ),
                        "title": quest_beat["title"],
                        "summary": quest_beat["summary"],
                    }
                ],
            }
        )
    return None


def _node_id(prefix: str, name: str) -> str:
    return f"{prefix}_{node_id_suffix(name)}"


def _has_display_name(runtime: GameRuntimeState, name: str) -> bool:
    return any(
        node.properties.get("name") == name or node.properties.get("title") == name
        for node in runtime.graph.nodes.values()
    )


def _unique_node_id(runtime: GameRuntimeState, base_id: str) -> str:
    if base_id not in runtime.graph.nodes:
        return base_id
    index = 2
    while f"{base_id}_{index}" in runtime.graph.nodes:
        index += 1
    return f"{base_id}_{index}"


def _requires_actionable_patch(
    *,
    accepted_narration: str | None,
    intent: StoryWriteIntent,
    contract: StoryContract,
) -> bool:
    if intent.kind != "both" or not accepted_narration:
        return False
    if not set(contract.allowed_ops).intersection(
        {"add_location", "add_character", "add_item", "add_quest_beat"}
    ):
        return False
    text = accepted_narration.strip()
    if len(text) < 8:
        return False
    return looks_actionable_for_story_patch(text)


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
