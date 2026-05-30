from __future__ import annotations

from typing import Any

from .types import SeedRecord


def record_id(record: SeedRecord) -> str:
    value = record.get("id")
    if not isinstance(value, str) or not value:
        raise ValueError("seed record requires a non-empty id")
    return value


def graph_stats(value: object) -> dict[str, int]:
    raw = mapping(value)
    defaults = {"body": 10, "agility": 10, "mind": 10, "presence": 10}
    return {key: int_value(raw.get(key), default) for key, default in defaults.items()}


def equipped_items(equipment: dict[str, Any]) -> list[tuple[str, str]]:
    return [
        (slot, item_id)
        for slot, item_id in equipment.items()
        if isinstance(slot, str) and isinstance(item_id, str) and item_id
    ]


def mapping(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def dict_list(value: object) -> list[SeedRecord]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def str_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]


def optional_str(value: object) -> str | None:
    return value if isinstance(value, str) and value else None


def int_value(value: object, default: int) -> int:
    return value if isinstance(value, int) else default
