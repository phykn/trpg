from src.game.runtime.state import GameRuntimeState
from .combat import combat_payload
from .hero import hero_payload
from .place import place_payload
from .quests import active_quest_payload, quest_offer_payloads
from .values import require_node
from src.wire.models import (
    GraphFrontStatePayload,
    GraphPendingConfirmationPayload,
    GraphPendingRollPayload,
)


def graph_to_front_state(runtime: GameRuntimeState) -> GraphFrontStatePayload:
    graph = runtime.graph_index
    player_id = runtime.progress.player_id
    player = require_node(graph, player_id, "character")
    return GraphFrontStatePayload(
        hero=hero_payload(graph, player, runtime.content),
        quest=active_quest_payload(runtime),
        quest_offers=quest_offer_payloads(runtime),
        place=place_payload(graph, player_id, runtime.progress.locale, runtime.content),
        combat=combat_payload(runtime),
        pending_confirmation=_pending_confirmation_payload(
            runtime.progress.pending_confirmation
        ),
        pending_roll=_pending_roll_payload(runtime.progress.pending_roll),
        log=list(runtime.log_entries),
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
