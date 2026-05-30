from __future__ import annotations

from typing import Any


def dict_entries(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [entry for entry in value if isinstance(entry, dict)]


def str_value(value: object) -> str | None:
    return value if isinstance(value, str) and value else None


def single_value(value: object) -> str | None:
    if isinstance(value, str):
        return value
    if isinstance(value, list) and value and isinstance(value[0], str):
        return value[0]
    return None


def str_list(value: object) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [item for item in value if isinstance(item, str)]
    return []


def ids_from_list(value: object) -> set[str]:
    return {
        entry_id
        for entry_id in (str_value(entry.get("id")) for entry in dict_entries(value))
        if entry_id
    }


def quest_choice_ids(quests: list[dict[str, Any]]) -> set[str]:
    choice_ids: set[str] = set()
    for quest in quests:
        choice_ids |= ids_from_list(quest.get("choices"))
    return choice_ids


def equipment_item_ids(value: object) -> set[str]:
    if not isinstance(value, dict):
        return set()
    ids: set[str] = set()
    for item in value.values():
        if isinstance(item, dict):
            item_id = str_value(item.get("id"))
            if item_id is not None:
                ids.add(item_id)
    return ids


def merchant_ids(value: object) -> tuple[set[str], set[str]]:
    merchants: set[str] = set()
    item_ids: set[str] = set()
    for merchant in dict_entries(value):
        merchant_id = str_value(merchant.get("id"))
        if merchant_id is not None:
            merchants.add(merchant_id)
        item_ids |= ids_from_list(merchant.get("stock"))
    return merchants, item_ids


def corpse_ids(value: object) -> tuple[set[str], set[str], dict[str, set[str]]]:
    corpses: set[str] = set()
    item_ids: set[str] = set()
    by_corpse: dict[str, set[str]] = {}
    for corpse in dict_entries(value):
        corpse_id = str_value(corpse.get("id"))
        corpse_item_ids = ids_from_list(corpse.get("inventory"))
        if corpse_id is not None:
            corpses.add(corpse_id)
            by_corpse[corpse_id] = corpse_item_ids
        item_ids |= corpse_item_ids
    return corpses, item_ids, by_corpse


def self_refs(player_ids: set[str]) -> set[str]:
    refs = {"<self>.inventory", "<self>.equipped"}
    for slot in ("weapon", "armor", "accessory"):
        refs.add(f"<self>.equipped.{slot}")
    for player_id in player_ids:
        refs.add(player_id)
        refs.add(f"{player_id}.inventory")
        refs.add(f"{player_id}.equipped")
        for slot in ("weapon", "armor", "accessory"):
            refs.add(f"{player_id}.equipped.{slot}")
    return refs
