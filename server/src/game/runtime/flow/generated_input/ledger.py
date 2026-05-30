"""Story patch ledger entry construction."""

from src.game.domain.story_patch import StoryWriteIntent, StoryWriteResponse
from src.game.domain.story_patch_ledger import (
    StoryPatchLedgerEntry,
    StoryPatchLedgerStatus,
)
from src.game.runtime.request_result import GraphActionRequestResult


def ledger_entry(
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
