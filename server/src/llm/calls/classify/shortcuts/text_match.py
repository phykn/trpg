from __future__ import annotations

import re
from typing import Any

from src.locale.terms import DIALOGUE_TARGET_PARTICLES

from .surroundings import has_any


def has_localized_target_names(entries: list[dict[str, Any]]) -> bool:
    return any(
        isinstance(entry.get("name"), str) and has_hangul(entry["name"])
        for entry in entries
    )


def has_hangul(text: str) -> bool:
    return any(0xAC00 <= ord(char) <= 0xD7A3 for char in text)


def dialogue_target_phrases(player_input: str) -> list[str]:
    particle = "|".join(re.escape(term) for term in DIALOGUE_TARGET_PARTICLES)
    hangul_range = f"{chr(0xAC00)}-{chr(0xD7A3)}"
    return [
        match.group(1).strip()
        for match in re.finditer(
            rf"([0-9A-Za-z{hangul_range} ]{{1,32}})(?:{particle})",
            player_input,
        )
        if match.group(1).strip()
    ]


__all__ = [
    "dialogue_target_phrases",
    "has_any",
    "has_hangul",
    "has_localized_target_names",
]
