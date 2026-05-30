from __future__ import annotations

from typing import Any

from .types import SeedRecords

RECOMMENDED_FIELDS = {
    "location": ("mood", "traits"),
    "item": ("traits",),
    "character": ("mbti", "traits"),
}


def seed_warnings(
    *,
    races: SeedRecords,
    locations: SeedRecords,
    items: SeedRecords,
    skills: SeedRecords,
    npcs: SeedRecords,
    quests: SeedRecords,
    chapters: SeedRecords,
    start: dict[str, Any],
    effects: SeedRecords | None = None,
    statuses: SeedRecords | None = None,
    slots: SeedRecords | None = None,
    factions: SeedRecords | None = None,
    actions: SeedRecords | None = None,
    knowledge: SeedRecords | None = None,
    dialogue_styles: SeedRecords | None = None,
    mbti: SeedRecords | None = None,
    player: dict[str, Any] | None = None,
) -> list[str]:
    del (
        races,
        skills,
        effects,
        statuses,
        slots,
        factions,
        actions,
        knowledge,
        dialogue_styles,
        mbti,
        quests,
        chapters,
        start,
        player,
    )
    out: list[str] = []
    check_recommended_fields("location", locations, out)
    check_recommended_fields("item", items, out)
    check_recommended_fields("character", npcs, out)
    return out


def check_recommended_fields(
    kind: str,
    records: SeedRecords,
    out: list[str],
) -> None:
    for record_id, record in records.items():
        for field in RECOMMENDED_FIELDS[kind]:
            if has_recommended_value(record.get(field)):
                continue
            out.append(f"{kind} {record_id} missing recommended field: {field}")


def has_recommended_value(value: object) -> bool:
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, list):
        return any(isinstance(item, str) and item.strip() for item in value)
    return value is not None
