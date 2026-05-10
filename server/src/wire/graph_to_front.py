from __future__ import annotations

from src.game.runtime.state import GameRuntimeState
from src.wire.graph_combat import combat_payload
from src.wire.graph_hero import hero_payload
from src.wire.graph_payload_helpers import require_node
from src.wire.graph_place import place_payload
from src.wire.graph_quests import active_quest_payload, quest_offer_payloads
from src.wire.models import GraphFrontStatePayload, GraphPendingConfirmationPayload


def graph_to_front_state(runtime: GameRuntimeState) -> GraphFrontStatePayload:
    graph = runtime.graph
    player_id = runtime.progress.player_id
    player = require_node(graph, player_id, "character")
    return GraphFrontStatePayload(
        hero=hero_payload(graph, player),
        quest=active_quest_payload(runtime),
        quest_offers=quest_offer_payloads(runtime),
        place=place_payload(graph, player_id),
        combat=combat_payload(runtime),
        pending_confirmation=_pending_confirmation_payload(
            runtime.progress.pending_confirmation
        ),
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
