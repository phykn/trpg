"""Story write intent selection."""

from src.game.domain.action import Action
from src.game.domain.story_contract import StoryContract
from src.game.domain.story_patch import StoryWriteIntent
from src.game.runtime.state import GameRuntimeState


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
        if _has_recent_generated_world_node(runtime):
            return intent
        return StoryWriteIntent(kind="both", reason="no recent generated discoveries")
    return intent


def _has_recent_generated_world_node(runtime: GameRuntimeState) -> bool:
    threshold = max(0, runtime.progress.turn_count - 3)
    for node in runtime.graph.nodes.values():
        if node.type not in {"location", "character", "item", "quest"}:
            continue
        turn_id = node.properties.get("turn_id")
        if isinstance(turn_id, int) and turn_id >= threshold:
            return True
    return False
