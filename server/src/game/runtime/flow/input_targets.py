"""Target resolution helpers for graph input flow."""

from src.game.domain.action import Action
from src.game.domain.content import node_label
from src.game.domain.graph import GraphNode
from src.game.domain.graph.character import is_visible_character
from src.game.domain.graph.query import characters_at, location_of
from src.game.domain.quest import quest_triggers, quest_triggers_met
from src.locale.render import render

from ..action_refs import first_ref
from ..state import GameRuntimeState


def with_implicit_speak_target(runtime: GameRuntimeState, action: Action) -> Action:
    if action.verb != "speak":
        return action
    if first_ref(action.what) is not None or first_ref(action.to) is not None:
        return action
    target = _unique_visible_active_social_check_target(runtime)
    if target is None:
        target = resolve_narrative_subject(runtime, action)
    if target is None:
        return action
    return action.model_copy(update={"to": target})


def resolve_narrative_subject(
    runtime: GameRuntimeState,
    action: Action,
) -> str | None:
    target = first_ref(action.what) or first_ref(action.to)
    if isinstance(target, str) and _is_at_player_location(runtime, target):
        return target
    if action.verb != "speak":
        return None
    active_subject = runtime.progress.active_subject_id
    if active_subject and _is_visible_character_at_player_location(
        runtime,
        active_subject,
    ):
        return active_subject
    graph = runtime.graph_index
    location_id = location_of(graph, runtime.progress.player_id)
    if location_id is None:
        return None
    for character_id in characters_at(graph, location_id):
        if character_id == runtime.progress.player_id:
            continue
        node = graph.nodes.get(character_id)
        if node is None or node.type != "character":
            continue
        if is_visible_character(node):
            return character_id
    return None


def node_name(runtime: GameRuntimeState, node: GraphNode | None) -> str:
    if node is None:
        return render("runtime.none", runtime.progress.locale)
    return node_label(runtime.content, node)


def action_target(action: Action) -> str | None:
    return first_ref(action.what) or first_ref(action.to) or first_ref(action.with_)


def _unique_visible_active_social_check_target(
    runtime: GameRuntimeState,
) -> str | None:
    active_id = runtime.progress.active_quest_id
    if active_id is None:
        return None
    quest = runtime.graph.nodes.get(active_id)
    if quest is None or quest.type != "quest":
        return None
    triggers = quest_triggers(quest)
    met = quest_triggers_met(quest, len(triggers))
    targets: set[str] = set()
    for index, trigger in enumerate(triggers):
        if met[index] is True:
            continue
        if trigger.get("type") != "social_check":
            continue
        target = trigger.get("target")
        if not isinstance(target, str):
            continue
        if _is_visible_character_at_player_location(runtime, target):
            targets.add(target)
    if len(targets) != 1:
        return None
    return next(iter(targets))


def _is_visible_character_at_player_location(
    runtime: GameRuntimeState,
    node_id: str,
) -> bool:
    node = runtime.graph.nodes.get(node_id)
    return (
        node is not None
        and node.type == "character"
        and is_visible_character(node)
        and _is_at_player_location(runtime, node_id)
    )


def _is_at_player_location(runtime: GameRuntimeState, node_id: str) -> bool:
    graph = runtime.graph_index
    player_location = location_of(graph, runtime.progress.player_id)
    return (
        player_location is not None and location_of(graph, node_id) == player_location
    )
