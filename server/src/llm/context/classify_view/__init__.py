from __future__ import annotations

from typing import Any

from src.game.domain.graph.query import location_of
from src.game.runtime.state import GameRuntimeState

from .entities import (
    attackable_ids,
    corpses,
    equipment,
    exits,
    inventory,
    location_items,
    merchants,
    node_ref,
    skills,
    visible_targets,
)
from .grounding import classify_context_to_grounding_view
from .quests import active_quest, available_quests, quest_choice_ids, quest_ids
from .references import last_entity_ref, recent_exchanges, recent_scene
from .types import ClassifyContextLimits

__all__ = [
    "ClassifyContextLimits",
    "build_classify_context_view",
    "classify_context_to_grounding_view",
]


def build_classify_context_view(
    runtime: GameRuntimeState,
    player_input: str,
    *,
    limits: ClassifyContextLimits | None = None,
) -> dict[str, Any]:
    limits = limits or ClassifyContextLimits()
    graph = runtime.graph_index
    player_id = runtime.progress.player_id
    location_id = location_of(graph, player_id)
    location = graph.nodes.get(location_id or "")
    current_visible_targets = visible_targets(runtime, location_id)
    current_exits = exits(runtime, location_id)
    current_inventory = inventory(runtime, player_id)
    current_skills = skills(runtime, player_id)
    current_location_items = location_items(runtime, location_id)
    current_corpses = corpses(runtime, location_id)

    current_active_quest = active_quest(runtime)
    current_available_quests = available_quests(
        runtime,
        current_visible_targets,
        current_active_quest,
    )

    return {
        "mode": (
            "combat"
            if runtime.progress.graph_combat_state is not None
            else "exploration"
        ),
        "identity": {
            "player": node_ref(runtime, runtime.graph.nodes.get(player_id)),
            "location": node_ref(runtime, location),
            "active_quest": current_active_quest,
            "available_quests": current_available_quests,
            "visible_targets": current_visible_targets,
            "exits": current_exits,
            "inventory": current_inventory,
            "equipment": equipment(runtime, player_id),
            "skills": current_skills,
            "location_items": current_location_items,
            "merchants": merchants(runtime, current_visible_targets),
            "corpses": current_corpses,
        },
        "affordances": {
            "can_speak_to": [
                target["id"]
                for target in current_visible_targets
                if target["type"] in {"npc", "enemy"}
            ],
            "can_attack": attackable_ids(current_visible_targets),
            "can_move_to": [exit_["id"] for exit_ in current_exits],
            "can_use": [item["id"] for item in current_inventory],
            "can_pick_up": [item["id"] for item in current_location_items],
            "can_accept_or_abandon_quest": quest_ids(
                runtime,
                current_available_quests,
            ),
            "can_decide": quest_choice_ids(runtime),
        },
        "references": {
            "recent_scene": recent_scene(runtime, limits),
            "recent_exchanges": recent_exchanges(runtime, limits),
            "last_npc": last_entity_ref(runtime, entity_types={"character"}),
            "last_target": last_entity_ref(runtime),
            "last_item": last_entity_ref(runtime, entity_types={"item"}),
        },
    }
