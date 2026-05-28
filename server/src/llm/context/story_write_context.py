from typing import Any

from pydantic import BaseModel, ConfigDict

from src.game.domain.action import Action
from src.game.domain.story_contract import StoryContract
from src.game.domain.story_patch import StoryWriteIntent
from src.game.runtime.state import GameRuntimeState


class StoryWriteInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    contract: dict[str, Any]
    intent: dict[str, Any]
    player_input: str
    action: dict[str, Any]
    visible_context: dict[str, Any]


def build_story_write_input(
    runtime: GameRuntimeState,
    *,
    contract: StoryContract,
    intent: StoryWriteIntent,
    player_input: str,
    action: Action,
    accepted_narration: str | None = None,
    patch_required: bool = False,
    patch_reason: str | None = None,
) -> StoryWriteInput:
    visible_context: dict[str, Any] = {
        "player_id": runtime.progress.player_id,
        "turn": runtime.progress.turn_count,
        "nodes": [
            {
                "id": node.id,
                "type": node.type,
                "name": node.properties.get("name")
                or node.properties.get("title")
                or node.id,
            }
            for node in runtime.graph.nodes.values()
            if node.type in {"character", "item", "location", "quest", "knowledge"}
        ],
    }
    if accepted_narration:
        visible_context["accepted_narration"] = accepted_narration
    if patch_required:
        visible_context["patch_requirement"] = {
            "required": True,
            "reason": patch_reason or "accepted narration contains an actionable lead",
        }
    return StoryWriteInput(
        contract=contract.model_dump(mode="json", by_alias=True),
        intent=intent.model_dump(mode="json"),
        player_input=player_input,
        action=action.model_dump(mode="json", by_alias=True, exclude_none=True),
        visible_context=visible_context,
    )
