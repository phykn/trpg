import secrets
from typing import Any

from src.game.domain.action import Action
from src.game.domain.content import node_label
from src.game.domain.graph import Graph, GraphEdge
from src.game.domain.graph.character import can_character_be_attacked
from src.game.domain.graph.query import connection_is_unlocked, edges_from, location_of
from src.locale.render import render

from ..action_refs import first_ref, ref_list
from ..pending_action import build_pending_action_payload
from ..state import GameRuntimeState


def build_graph_action_confirmation(
    runtime: GameRuntimeState,
    action: Action,
) -> dict[str, Any] | None:
    if runtime.progress.graph_combat_state is None and action.verb == "attack":
        return _build_attack_start_confirmation(runtime, action)

    if action.verb == "transfer" and action.how == "steal":
        return _build_steal_confirmation(runtime, action)

    if action.verb == "transfer" and action.how in ("accept", "abandon"):
        return _build_quest_confirmation(runtime, action)

    if action.verb == "move":
        return _build_important_move_confirmation(runtime, action)

    return None


def requires_roll_after_confirmation(action: Action) -> bool:
    return action.verb == "transfer" and action.how == "steal"


def _build_attack_start_confirmation(
    runtime: GameRuntimeState,
    action: Action,
) -> dict[str, Any] | None:
    target_ref = _attack_target(runtime.graph, runtime.progress.player_id, action)
    if target_ref is None:
        return None

    target = runtime.graph.nodes[target_ref]
    target_label = node_label(runtime.content, target)
    locale = runtime.progress.locale
    return _pending(
        kind="attack_start",
        title=render("runtime.confirmation.attack.title", locale),
        body=render("runtime.confirmation.attack.body", locale, target=target_label),
        confirm_label=render("runtime.confirmation.attack.confirm", locale),
        target_label=target_label,
        action=_normalize_attack_action(action, target_ref),
        locale=locale,
    )


def _build_quest_confirmation(
    runtime: GameRuntimeState,
    action: Action,
) -> dict[str, Any] | None:
    quest_id = first_ref(action.what) or first_ref(action.to)
    if quest_id is None:
        return None
    quest = runtime.graph.nodes.get(quest_id)
    if quest is None or quest.type != "quest":
        return None

    locale = runtime.progress.locale
    quest_label = node_label(runtime.content, quest)
    if action.how == "accept":
        return _pending(
            kind="quest_accept",
            title=render("runtime.confirmation.quest_accept.title", locale),
            body=render(
                "runtime.confirmation.quest_accept.body", locale, quest=quest_label
            ),
            confirm_label=render("runtime.confirmation.quest_accept.confirm", locale),
            target_label=quest_label,
            action=action,
            locale=locale,
        )

    return _pending(
        kind="quest_abandon",
        title=render("runtime.confirmation.quest_abandon.title", locale),
        body=render(
            "runtime.confirmation.quest_abandon.body", locale, quest=quest_label
        ),
        confirm_label=render("runtime.confirmation.quest_abandon.confirm", locale),
        target_label=quest_label,
        action=action,
        locale=locale,
    )


def _build_important_move_confirmation(
    runtime: GameRuntimeState,
    action: Action,
) -> dict[str, Any] | None:
    source_id = location_of(runtime.graph, runtime.progress.player_id)
    destination_id = first_ref(action.to) or first_ref(action.what)
    if source_id is None or destination_id is None or source_id == destination_id:
        return None

    edge = _move_edge(runtime.graph, source_id, destination_id)
    if edge is None:
        return None
    if not _is_important_move_gate(runtime.graph, edge):
        return None
    if _has_reverse_connection(runtime.graph, destination_id, source_id):
        return None

    source = runtime.graph.nodes.get(source_id)
    destination = runtime.graph.nodes.get(destination_id)
    if source is None or destination is None:
        return None

    locale = runtime.progress.locale
    source_label = node_label(runtime.content, source)
    destination_label = node_label(runtime.content, destination)
    return _pending(
        kind="important_move",
        title=render("runtime.confirmation.important_move.title", locale),
        body=render(
            "runtime.confirmation.important_move.body",
            locale,
            source=source_label,
            destination=destination_label,
        ),
        confirm_label=render(
            "runtime.confirmation.important_move.confirm",
            locale,
        ),
        target_label=destination_label,
        action=action,
        locale=locale,
    )


def _build_steal_confirmation(
    runtime: GameRuntimeState,
    action: Action,
) -> dict[str, Any] | None:
    item_id = first_ref(action.what) or first_ref(action.with_)
    target = first_ref(action.from_) or first_ref(action.to)
    if item_id is None or target is None:
        return None
    item = runtime.graph.nodes.get(item_id)
    target = runtime.graph.nodes.get(target)
    if item is None or target is None:
        return None

    locale = runtime.progress.locale
    item_label = node_label(runtime.content, item)
    target_label = node_label(runtime.content, target)
    return _pending(
        kind="steal",
        title=render("runtime.confirmation.steal.title", locale),
        body=render(
            "runtime.confirmation.steal.body",
            locale,
            item=item_label,
            target=target_label,
        ),
        confirm_label=render("runtime.confirmation.steal.confirm", locale),
        target_label=target_label,
        action=action,
        locale=locale,
    )


def _pending(
    *,
    kind: str,
    title: str,
    body: str,
    confirm_label: str,
    target_label: str,
    action: Action,
    locale: str,
) -> dict[str, Any]:
    return {
        "id": f"confirm_{secrets.token_hex(4)}",
        "kind": kind,
        "title": title,
        "body": body,
        "confirm_label": confirm_label,
        "cancel_label": render("runtime.confirmation.cancel", locale),
        "target_label": target_label,
        "payload": build_pending_action_payload(action),
    }


def _move_edge(graph: Graph, source_id: str, destination_id: str) -> GraphEdge | None:
    for edge in edges_from(graph, source_id, "connects_to"):
        if edge.to_node_id == destination_id:
            return edge
    return None


def _is_important_move_gate(graph: Graph, edge: GraphEdge) -> bool:
    quest_id = edge.properties.get("requires_quest")
    active_quest_id = edge.properties.get("requires_active_quest")
    return (
        (isinstance(quest_id, str) and bool(quest_id))
        or (isinstance(active_quest_id, str) and bool(active_quest_id))
    ) and connection_is_unlocked(graph, edge)


def _has_reverse_connection(graph: Graph, source_id: str, destination_id: str) -> bool:
    for edge in edges_from(graph, source_id, "connects_to"):
        if edge.to_node_id == destination_id:
            return True
    return False


def _attack_target(
    graph: Graph,
    player_id: str,
    action: Action,
) -> str | None:
    if action.verb == "attack":
        candidates = ref_list(action.what)
    else:
        return None
    for target in candidates:
        if _can_target_start_combat(graph, player_id, target):
            return target
    return None


def _normalize_attack_action(action: Action, target: str) -> Action:
    if action.verb == "attack":
        return action.model_copy(update={"what": [target]})
    return action


def _can_target_start_combat(
    graph: Graph,
    player_id: str,
    target: str,
) -> bool:
    player_location = location_of(graph, player_id)
    target_location = location_of(graph, target)
    target = graph.nodes.get(target)
    return (
        target is not None
        and target.type == "character"
        and target != player_id
        and player_location is not None
        and player_location == target_location
        and can_character_be_attacked(target)
    )
