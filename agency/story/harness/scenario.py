"""character.equipment slot derivation helper.

Build pipeline (build_scenario / write_entity / _patch_*) was removed —
agency/story/SKILL.md + tool.py replace it. This file now contains only
the deterministic equipment-slot derivation that runs at the equip-fill
step of the workflow.
"""

import json
from pathlib import Path


def fill_equipment(scenario_dir: Path) -> None:
    chars_dir = scenario_dir / "characters"
    items_dir = scenario_dir / "items"
    if not chars_dir.exists() or not items_dir.exists():
        return
    items: dict[str, dict] = {}
    for path in items_dir.glob("*.json"):
        item = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(item.get("id"), str):
            items[item["id"]] = item
    for char_path in chars_dir.glob("*.json"):
        char = json.loads(char_path.read_text(encoding="utf-8"))
        equipment = char.setdefault(
            "equipment", {"weapon": None, "armor": None, "accessory": None}
        )
        for item_id in char.get("inventory_ids", []):
            if not isinstance(item_id, str):
                continue
            item = items.get(item_id)
            if item is None:
                continue
            effect = item.get("effects")
            effect_type = effect.get("type") if isinstance(effect, dict) else None
            if effect_type == "weapon":
                if equipment.get("weapon") is None:
                    equipment["weapon"] = item_id
            elif effect_type == "armor":
                if equipment.get("armor") is None:
                    equipment["armor"] = item_id
                elif equipment.get("accessory") is None:
                    equipment["accessory"] = item_id
            elif effect is None and equipment.get("accessory") is None:
                equipment["accessory"] = item_id
        char_path.write_text(
            json.dumps(char, ensure_ascii=False, indent=2), encoding="utf-8"
        )
