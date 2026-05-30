from __future__ import annotations

from typing import Any

from src.game.domain.action import Action

from .surroundings import dict_entries, entry_ref, named_entry, player


def pickup_action(
    player_input: str,
    surroundings: dict[str, Any],
) -> Action | None:
    item = named_entry(player_input, dict_entries(surroundings.get("location_items")))
    if item is None:
        return None
    location = surroundings.get("location")
    player_ref = player(surroundings)
    if not isinstance(location, dict) or player_ref is None:
        return None
    location_id = location.get("id")
    if not isinstance(location_id, str):
        return None
    return Action(
        verb="transfer",
        what=item["id"],
        from_=location_id,
        to=player_ref["id"],
        how="free",
    )


def corpse_loot_action(
    player_input: str,
    surroundings: dict[str, Any],
) -> Action | None:
    corpse = named_entry(player_input, dict_entries(surroundings.get("corpses")))
    corpses = dict_entries(surroundings.get("corpses"))
    if corpse is None and len(corpses) == 1:
        corpse = entry_ref(corpses[0])
    if corpse is None:
        return None

    corpse_payload = next(
        (
            entry
            for entry in corpses
            if isinstance(entry.get("id"), str) and entry.get("id") == corpse["id"]
        ),
        None,
    )
    if corpse_payload is None:
        return None
    inventory = dict_entries(corpse_payload.get("inventory"))
    item = named_entry(player_input, inventory)
    if item is None and len(inventory) == 1:
        item = entry_ref(inventory[0])
    player_ref = player(surroundings)
    if item is None or player_ref is None:
        return None
    return Action(
        verb="transfer",
        what=item["id"],
        from_=corpse["id"],
        to=player_ref["id"],
        how="free",
    )
