"""Apply generated story patches after accepted actions."""

from typing import Any

from src.db.repo import GraphRepo
from src.game.domain.action import Action
from src.game.domain.graph.apply import apply_graph_changes
from src.game.domain.story_contract import StoryContract
from src.game.domain.story_patch import StoryWriteIntent
from src.game.engines.story_patch_apply import (
    changed_edge_ids as _changed_edge_ids,
    changed_node_ids as _changed_node_ids,
    story_patches_to_graph_changes,
)
from src.game.engines.story_patch_validator import validate_story_write_response
from src.game.runtime.request_result import GraphActionRequestResult
from src.llm.calls.story_write import story_write
from src.llm.diag import engine_diag
from src.locale.generated_story import GENERATED_SPEAK_WORLD_LEAD_MARKERS
from src.wire.graph.to_front import graph_to_front_state

from .changes import has_actionable_world_change, requires_actionable_patch
from .intent import story_write_intent_for_contract
from .ledger import ledger_entry
from .writer import (
    StoryWriter,
    call_writer_or_fallback,
    fit_response_to_contract_budget,
    is_writer_error_skip,
)


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
    if should_promote_speak_world_lead(
        action=action,
        intent=intent,
        contract=contract,
        accepted_narration=accepted_narration,
    ):
        intent = StoryWriteIntent(
            kind="both",
            reason="dialogue names actionable world lead",
        )
    if intent.kind == "none":
        return result

    patch_required = requires_actionable_patch(
        text=" ".join(filter(None, [accepted_narration, player_input])),
        intent=intent,
        contract=contract,
    )
    response = await call_writer_or_fallback(
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
    response = fit_response_to_contract_budget(response, contract)
    validation = validate_story_write_response(
        response,
        graph=result.runtime.graph,
        contract=contract,
        player_id=result.runtime.progress.player_id,
    )
    if not validation.ok:
        engine_diag(
            "story_write:reject",
            reasons=",".join(validation.reasons),
        )
        await repo.append_story_patch_entries(
            result.runtime.progress.game_id,
            [
                ledger_entry(
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
    if (
        patch_required
        and not has_actionable_world_change(changes)
        and not is_writer_error_skip(response)
    ):
        response = await call_writer_or_fallback(
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
        response = fit_response_to_contract_budget(response, contract)
        validation = validate_story_write_response(
            response,
            graph=result.runtime.graph,
            contract=contract,
            player_id=result.runtime.progress.player_id,
        )
        if not validation.ok:
            engine_diag(
                "story_write:reject",
                reasons=",".join(validation.reasons),
            )
            await repo.append_story_patch_entries(
                result.runtime.progress.game_id,
                [
                    ledger_entry(
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
        if (
            patch_required
            and not has_actionable_world_change(changes)
            and not is_writer_error_skip(response)
        ):
            rejected_reasons = ["required_actionable_patch_missing"]
            engine_diag(
                "story_write:reject",
                reasons=",".join(rejected_reasons),
            )
            await repo.append_story_patch_entries(
                result.runtime.progress.game_id,
                [
                    ledger_entry(
                        result,
                        response=response,
                        intent=intent,
                        status="rejected",
                        rejected_reasons=rejected_reasons,
                    )
                ],
            )
            return result
    changed_node_ids = _changed_node_ids(changes)
    changed_edge_ids = _changed_edge_ids(changes)
    if not changes:
        await repo.append_story_patch_entries(
            result.runtime.progress.game_id,
            [
                ledger_entry(
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
            ledger_entry(
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


def is_deferable_speak_story_write(
    *,
    action: Action,
    contract: StoryContract | None,
    runtime: Any,
    accepted_narration: str | None,
) -> bool:
    if contract is None:
        return False
    intent = story_write_intent_for_contract(action, contract, runtime=runtime)
    return action.verb == "speak" and intent.kind == "memory_candidate" and not (
        should_promote_speak_world_lead(
            action=action,
            intent=intent,
            contract=contract,
            accepted_narration=accepted_narration,
        )
    )


def should_promote_speak_world_lead(
    *,
    action: Action,
    intent: StoryWriteIntent,
    contract: StoryContract,
    accepted_narration: str | None,
) -> bool:
    if action.verb != "speak" or intent.kind != "memory_candidate":
        return False
    if not set(contract.allowed_ops).intersection(
        {"add_location", "add_character", "add_item", "add_quest_beat"}
    ):
        return False
    text = (accepted_narration or "").strip()
    if not text:
        return False
    return any(marker in text for marker in GENERATED_SPEAK_WORLD_LEAD_MARKERS)
