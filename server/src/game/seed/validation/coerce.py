from __future__ import annotations

from typing import Any


def mapping(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def dict_list(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def str_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]
