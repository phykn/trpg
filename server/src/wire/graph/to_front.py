from src.game.runtime.state import GameRuntimeState
from .chapters import active_chapter_payload
from .combat import combat_payload
from .hero import hero_payload
from .place import place_payload
from .quests import active_quest_payload, quest_offer_payloads  # ssot-allow: module import
from .values import require_node
from src.wire.models import (
    GraphDiscoveriesPayload,
    GraphDiscoveryEntryPayload,
    GraphFrontStatePayload,
    GraphPendingConfirmationPayload,
    GraphPendingRollPayload,
)


def graph_to_front_state(runtime: GameRuntimeState) -> GraphFrontStatePayload:
    graph = runtime.graph_index
    player_id = runtime.progress.player_id
    player = require_node(graph, player_id, "character")
    scenario_completed = _scenario_completed(runtime)
    return GraphFrontStatePayload(
        hero=hero_payload(graph, player, runtime.content),
        chapter=active_chapter_payload(runtime),
        scenario_completed=scenario_completed,
        quest=active_quest_payload(runtime),
        quest_offers=quest_offer_payloads(runtime),
        place=place_payload(
            graph,
            player_id,
            runtime.progress.locale,
            runtime.content,
            runtime.progress.active_subject_id,
        ),
        combat=combat_payload(runtime),
        pending_confirmation=_pending_confirmation_payload(
            runtime.progress.pending_confirmation
        ),
        pending_roll=_pending_roll_payload(runtime.progress.pending_roll),
        discoveries=_discoveries_payload(runtime),
        log=list(runtime.log_entries),
    )


def _scenario_completed(runtime: GameRuntimeState) -> bool:
    required_quests = [
        node
        for node in runtime.graph_index.nodes.values()
        if node.type == "quest" and node.properties.get("required") is not False
    ]
    return bool(required_quests) and all(
        node.properties.get("status") == "completed" for node in required_quests
    )


def _pending_confirmation_payload(
    pending: dict[str, object] | None,
) -> GraphPendingConfirmationPayload | None:
    if pending is None:
        return None
    return GraphPendingConfirmationPayload.model_validate(
        {
            "id": pending.get("id"),
            "kind": pending.get("kind"),
            "title": pending.get("title"),
            "body": pending.get("body"),
            "confirm_label": pending.get("confirm_label"),
            "cancel_label": pending.get("cancel_label"),
            "target_label": pending.get("target_label"),
        }
    )


def _pending_roll_payload(
    pending: dict[str, object] | None,
) -> GraphPendingRollPayload | None:
    if pending is None:
        return None
    return GraphPendingRollPayload.model_validate(
        {
            "id": pending.get("id"),
            "kind": pending.get("kind"),
            "title": pending.get("title"),
            "body": pending.get("body"),
            "stat": pending.get("stat"),
            "stat_label": pending.get("stat_label"),
            "required_roll": pending.get("required_roll"),
        }
    )


def _discoveries_payload(runtime: GameRuntimeState) -> GraphDiscoveriesPayload:
    memories: list[GraphDiscoveryEntryPayload] = []
    clues: list[GraphDiscoveryEntryPayload] = []
    for node in runtime.graph.nodes.values():
        if node.type != "knowledge":
            continue
        props = node.properties
        if props.get("visibility", "player") != "player":
            continue
        entry = _discovery_entry(node.id, props)
        if entry is None:
            continue
        if props.get("kind") == "memory":
            memories.append(entry)
        elif props.get("kind") == "clue":
            clues.append(entry)
    memories.sort(key=_discovery_sort_key)
    clues.sort(key=_discovery_sort_key)
    return GraphDiscoveriesPayload(memories=memories, clues=clues)


def _discovery_entry(
    node_id: str,
    props: dict[str, object],
) -> GraphDiscoveryEntryPayload | None:
    title = props.get("title")
    summary = props.get("summary")
    stability = props.get("stability", "scene")
    if not isinstance(title, str) or not isinstance(summary, str):
        return None
    if stability not in {"scene", "chapter", "campaign", "core"}:
        stability = "scene"
    turn_id = props.get("turn_id")
    return GraphDiscoveryEntryPayload(
        id=node_id,
        title=title,
        summary=summary,
        stability=stability,
        turn_id=turn_id if isinstance(turn_id, int) else None,
    )


def _discovery_sort_key(entry: GraphDiscoveryEntryPayload) -> tuple[int, str]:
    return (entry.turn_id if entry.turn_id is not None else -1, entry.id)
