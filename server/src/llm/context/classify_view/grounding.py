from __future__ import annotations

from typing import Any


def classify_context_to_grounding_view(context: dict[str, Any]) -> dict[str, Any]:
    identity = (
        context.get("identity") if isinstance(context.get("identity"), dict) else {}
    )
    references = (
        context.get("references") if isinstance(context.get("references"), dict) else {}
    )
    player = (
        identity.get("player") if isinstance(identity.get("player"), dict) else None
    )
    active_quest = (
        identity.get("active_quest")
        if isinstance(identity.get("active_quest"), dict)
        else None
    )
    available_quests = dict_entries(identity.get("available_quests"))
    visible_targets = dict_entries(identity.get("visible_targets"))
    exits = dict_entries(identity.get("exits"))

    grounding_targets = [
        {
            **target,
            "type": target["type"] if target.get("type") in {"npc", "enemy"} else "npc",
        }
        for target in visible_targets
        if isinstance(target.get("id"), str) and isinstance(target.get("name"), str)
    ]

    return {
        "in_combat": context.get("mode") == "combat",
        "location": identity.get("location") or {},
        "entities": [
            *(
                [{"id": player["id"], "name": player["name"], "type": "player"}]
                if isinstance(player, dict)
                and isinstance(player.get("id"), str)
                and isinstance(player.get("name"), str)
                else []
            ),
            *grounding_targets,
            *[
                {"id": exit_["id"], "name": exit_["name"], "type": "connection"}
                for exit_ in exits
                if isinstance(exit_.get("id"), str)
                and isinstance(exit_.get("name"), str)
            ],
        ],
        "inventory": dict_entries(identity.get("inventory")),
        "equipment": identity.get("equipment") or {},
        "skills": dict_entries(identity.get("skills")),
        "location_items": dict_entries(identity.get("location_items")),
        "merchants": dict_entries(identity.get("merchants")),
        "corpses": dict_entries(identity.get("corpses")),
        "quests": [
            *([active_quest] if active_quest is not None else []),
            *available_quests,
        ],
        "recent_npc": references.get("last_npc"),
    }


def dict_entries(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [entry for entry in value if isinstance(entry, dict)]
