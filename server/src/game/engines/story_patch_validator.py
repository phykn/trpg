from pydantic import BaseModel, ConfigDict, Field

from src.game.domain.graph import Graph
from src.game.domain.story_contract import StoryContract
from src.game.domain.story_patch import AddCluePatch, StoryWriteResponse


class StoryPatchValidationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ok: bool
    reasons: list[str] = Field(default_factory=list)


def validate_story_write_response(
    response: StoryWriteResponse,
    *,
    graph: Graph,
    contract: StoryContract,
) -> StoryPatchValidationResult:
    reasons: list[str] = []

    if len(response.patches) > contract.budgets.patches_per_turn:
        reasons.append("budget_exceeded")
    if len(response.new_terms) > contract.budgets.new_terms_per_turn:
        reasons.append("new_terms_budget_exceeded")

    seen_ids: set[str] = set()
    for patch in response.patches:
        if patch.op not in contract.allowed_ops:
            reasons.append(f"op_not_allowed:{patch.op}")
        if patch.id in graph.nodes or patch.id in seen_ids:
            reasons.append(f"duplicate_id:{patch.id}")
        seen_ids.add(patch.id)
        if isinstance(patch, AddCluePatch) and patch.anchor_id:
            anchor = graph.nodes.get(patch.anchor_id)
            if anchor is None:
                reasons.append(f"missing_anchor:{patch.anchor_id}")
            elif anchor.type not in {"character", "item", "location", "quest"}:
                reasons.append(f"invalid_anchor_type:{patch.anchor_id}")

    return StoryPatchValidationResult(ok=not reasons, reasons=reasons)
