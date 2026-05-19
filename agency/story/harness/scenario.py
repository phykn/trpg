"""NPC equipment normalization helper.

Build pipeline (build_scenario / write_entity / _patch_*) was removed —
agency/story/SKILL.md + tool.py replace it. This file now contains the
server-compatible normalization that runs at the equip-fill step.
"""

import json
from pathlib import Path

FIXED_CATALOG_NAMES = ("actions", "effects", "mbti", "slots")


def fill_equipment(scenario_dir: Path) -> None:
    chars_dir = scenario_dir / "characters"
    chars_file = scenario_dir / "characters.json"
    if chars_file.is_file():
        records = _records_from_json(json.loads(chars_file.read_text(encoding="utf-8")))
        changed = False
        for char in records.values():
            if char.get("equipment") == {}:
                continue
            char["equipment"] = {}
            changed = True
        if changed:
            chars_file.write_text(
                json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        return
    if not chars_dir.exists():
        return
    for char_path in sorted(chars_dir.glob("*.json")):
        char = json.loads(char_path.read_text(encoding="utf-8"))
        if char.get("equipment") == {}:
            continue
        char["equipment"] = {}
        char_path.write_text(
            json.dumps(char, ensure_ascii=False, indent=2), encoding="utf-8"
        )


def copy_fixed_catalogs(scenario_dir: Path, catalog_dir: Path) -> None:
    for name in FIXED_CATALOG_NAMES:
        src = catalog_dir / f"{name}.json"
        dst = scenario_dir / f"{name}.json"
        fixed = _records_from_json(json.loads(src.read_text(encoding="utf-8")))
        existing = {}
        if dst.is_file():
            existing = _records_from_json(json.loads(dst.read_text(encoding="utf-8")))
        merged = {**fixed, **existing}
        for record_id, record in fixed.items():
            merged[record_id] = record
        dst.write_text(
            json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8"
        )


def _records_from_json(value: object) -> dict[str, dict]:
    if isinstance(value, dict):
        candidates = value.values()
    elif isinstance(value, list):
        candidates = value
    else:
        return {}
    records: dict[str, dict] = {}
    for obj in candidates:
        if not isinstance(obj, dict):
            continue
        record_id = obj.get("id")
        if isinstance(record_id, str):
            records[record_id] = obj
    return records
