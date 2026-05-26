from pydantic import BaseModel, ConfigDict, Field

from src.game.domain.graph import Graph
from src.game.domain.story_contract import StoryContract
from src.game.domain.story_patch import (
    AddCharacterPatch,
    AddCluePatch,
    AddItemPatch,
    AddLocationPatch,
    StoryWriteResponse,
)


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
    if _violates_forbid(response, contract):
        reasons.append("contract_forbidden")

    seen_ids: set[str] = set()
    existing_names = _existing_display_names(graph)
    for patch in response.patches:
        if patch.op not in contract.allowed_ops:
            reasons.append(f"op_not_allowed:{patch.op}")
        if patch.id in graph.nodes or patch.id in seen_ids:
            reasons.append(f"duplicate_id:{patch.id}")
        seen_ids.add(patch.id)
        patch_name = getattr(patch, "name", None)
        if isinstance(patch_name, str) and patch_name in existing_names:
            reasons.append(f"duplicate_name:{patch_name}")
        if isinstance(patch, AddCluePatch) and patch.anchor_id:
            anchor = graph.nodes.get(patch.anchor_id)
            if anchor is None:
                reasons.append(f"missing_anchor:{patch.anchor_id}")
            elif anchor.type not in {"character", "item", "location", "quest"}:
                reasons.append(f"invalid_anchor_type:{patch.anchor_id}")
        if isinstance(patch, AddLocationPatch):
            source = graph.nodes.get(patch.connect_from)
            if source is None:
                reasons.append(f"missing_connect_from:{patch.connect_from}")
            elif source.type != "location":
                reasons.append(f"invalid_connect_from_type:{patch.connect_from}")
        if isinstance(patch, AddCharacterPatch):
            location = graph.nodes.get(patch.location_id)
            if location is None:
                reasons.append(f"missing_location:{patch.location_id}")
            elif location.type != "location":
                reasons.append(f"invalid_location_type:{patch.location_id}")
        if isinstance(patch, AddItemPatch):
            if patch.location_id is not None:
                location = graph.nodes.get(patch.location_id)
                if location is None:
                    reasons.append(f"missing_item_location:{patch.location_id}")
                elif location.type != "location":
                    reasons.append(f"invalid_item_location_type:{patch.location_id}")
            if patch.owner_id is not None:
                owner = graph.nodes.get(patch.owner_id)
                if owner is None:
                    reasons.append(f"missing_item_owner:{patch.owner_id}")
                elif owner.type != "character":
                    reasons.append(f"invalid_item_owner_type:{patch.owner_id}")

    return StoryPatchValidationResult(ok=not reasons, reasons=reasons)


def _existing_display_names(graph: Graph) -> set[str]:
    out: set[str] = set()
    for node in graph.nodes.values():
        for key in ("name", "title"):
            value = node.properties.get(key)
            if isinstance(value, str) and value:
                out.add(value)
    return out


def _violates_forbid(
    response: StoryWriteResponse,
    contract: StoryContract,
) -> bool:
    if not contract.forbid:
        return False
    texts = [response.reason, *response.new_terms]
    for patch in response.patches:
        texts.extend(_string_values(patch.model_dump(mode="json")).values())
    return any(forbidden in text for forbidden in contract.forbid for text in texts)


def _string_values(value: object) -> dict[str, str]:
    if isinstance(value, str):
        return {"": value}
    if isinstance(value, dict):
        out: dict[str, str] = {}
        for key, child in value.items():
            for child_key, child_value in _string_values(child).items():
                out[f"{key}.{child_key}" if child_key else str(key)] = child_value
        return out
    if isinstance(value, list):
        out: dict[str, str] = {}
        for index, child in enumerate(value):
            for child_key, child_value in _string_values(child).items():
                out[f"{index}.{child_key}" if child_key else str(index)] = child_value
        return out
    return {}
