from __future__ import annotations

from typing import Any

from .types import SeedRecords

LEGACY_KEY_RENAMES = {
    "action_category_id": "action",
    "action_id": "action",
    "dialogue_style_id": "dialogue_style",
    "effect_template": "effect",
    "faction_id": "faction",
    "giver_id": "giver",
    "inventory_ids": "inventory",
    "item_ids": "items",
    "knowledge_ids": "knowledge",
    "learned_skill_ids": "learned_skills",
    "location_id": "location",
    "prerequisite_ids": "prerequisites",
    "private_hint": "secrets",
    "quest_ids": "quests",
    "race_id": "race",
    "racial_skill_ids": "racial_skills",
    "slot_id": "slot",
    "support_action": "action",
}
FORBIDDEN_SEED_KEYS = {
    *LEGACY_KEY_RENAMES,
    "disposition",
    "hp",
    "job",
    "max_hp",
    "max_mp",
    "mp",
    "stats",
    "status_ids",
    "tags",
    "weather",
}


def check_key_id(kind: str, records: SeedRecords, out: list[str]) -> None:
    for key, record in records.items():
        if record.get("id") != key:
            out.append(f"{kind} key/id mismatch: {key}")


def check_forbidden_seed_shape(
    *,
    records: dict[str, SeedRecords],
    start: dict[str, Any],
    player: dict[str, Any] | None,
    out: list[str],
) -> None:
    for kind, by_id in records.items():
        for record_id, record in by_id.items():
            walk_forbidden_shape(record, f"{kind} {record_id}", out)
            if kind == "location" and "difficulty" in record:
                out.append(
                    f"location {record_id} difficulty is a connection field, "
                    "not a location field"
                )
    walk_forbidden_shape(start, "start", out)
    if player is not None:
        walk_forbidden_shape(player, "player", out)


def walk_forbidden_shape(value: object, path: str, out: list[str]) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}"
            if key in LEGACY_KEY_RENAMES:
                out.append(
                    f"{child_path} uses legacy key; use "
                    f"{LEGACY_KEY_RENAMES[key]!r}"
                )
            elif key in FORBIDDEN_SEED_KEYS:
                out.append(f"{child_path} is not allowed in seed data")
            elif key != "id" and (key.endswith("_id") or key.endswith("_ids")):
                out.append(f"{child_path} uses legacy *_id/*_ids naming")

            if key == "on_use" and child is None:
                out.append(f"{child_path} must be omitted when empty")
            if key in {"difficulty", "key_item"} and child is None:
                out.append(f"{child_path} must be omitted when empty")

            walk_forbidden_shape(child, child_path, out)
        return
    if isinstance(value, list):
        for index, child in enumerate(value):
            walk_forbidden_shape(child, f"{path}[{index}]", out)
