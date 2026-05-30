"""Story patch change policy helpers."""

from src.game.domain.graph import GraphChange
from src.game.domain.story_contract import StoryContract
from src.game.domain.story_patch import StoryWriteIntent
from src.locale.generated_story import looks_actionable_for_story_patch


def has_actionable_world_change(changes: list[GraphChange]) -> bool:
    for change in changes:
        if getattr(change, "type", None) != "add_node":
            continue
        node_type = getattr(change.node, "type", None)
        if node_type in {"location", "character", "item", "quest"}:
            return True
    return False


def requires_actionable_patch(
    *,
    text: str,
    intent: StoryWriteIntent,
    contract: StoryContract,
) -> bool:
    if intent.kind != "both" or not text:
        return False
    if not set(contract.allowed_ops).intersection(
        {"add_location", "add_character", "add_item", "add_quest_beat"}
    ):
        return False
    text = text.strip()
    if len(text) < 8:
        return False
    return looks_actionable_for_story_patch(text)
