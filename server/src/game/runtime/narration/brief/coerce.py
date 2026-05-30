"""Small payload coercion helpers for narration briefs."""

from typing import Any


def as_dict(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_dicts(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def as_strings(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str) and item]


def dedupe(values: list[str]) -> list[str]:
    out = []
    seen = set()
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        out.append(value)
    return out


def clip(value: str) -> str:
    return " ".join(value.split())
