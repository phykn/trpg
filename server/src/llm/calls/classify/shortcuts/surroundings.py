from __future__ import annotations

from typing import Any


def player_id(surroundings: dict[str, Any]) -> str | None:
    player_ref = player(surroundings)
    return player_ref["id"] if player_ref is not None else None


def player(surroundings: dict[str, Any]) -> dict[str, str] | None:
    for entry in dict_entries(surroundings.get("entities")):
        if entry.get("type") != "player":
            continue
        entry_id = entry.get("id")
        if isinstance(entry_id, str):
            return {"id": entry_id}
    return None


def named_entry(
    player_input: str,
    entries: list[dict[str, Any]],
) -> dict[str, str] | None:
    for entry in entries:
        entry_id = entry.get("id")
        name = entry.get("name")
        if isinstance(entry_id, str) and isinstance(name, str) and name in player_input:
            return {"id": entry_id, "name": name}
    return None


def entry_ref(entry: dict[str, Any]) -> dict[str, str] | None:
    entry_id = entry.get("id")
    name = entry.get("name")
    if isinstance(entry_id, str) and isinstance(name, str):
        return {"id": entry_id, "name": name}
    return None


def has_any(player_input: str, terms: tuple[str, ...]) -> bool:
    return any(term in player_input for term in terms)


def dict_entries(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [entry for entry in value if isinstance(entry, dict)]
