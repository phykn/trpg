"""character.equipment 슬롯 자동 배치 헬퍼.

Build pipeline (build_scenario / write_entity / _patch_*) was removed —
agency/story/SKILL.md + tool.py replace it. This file now contains only
the deterministic equipment-slot derivation that runs at the equip-fill
step of the workflow.
"""

from pathlib import Path

from src.domain.entities import (
    ArmorEffect,
    Character,
    Item,
    WeaponEffect,
)


def fill_equipment(scenario_dir: Path) -> None:
    """character.equipment 슬롯을 inventory 아이템 effect 보고 자동 배치.

    Slot rules (first wins per slot):
      WeaponEffect → weapon
      ArmorEffect  → armor; 이미 차 있으면 accessory로 흘림
      effects=None (장식품) → accessory

    Pre-existing equipment 값은 보존 (None인 슬롯만 채움).
    """
    chars_dir = scenario_dir / "characters"
    items_dir = scenario_dir / "items"
    if not chars_dir.exists() or not items_dir.exists():
        return
    items: dict[str, Item] = {}
    for path in items_dir.glob("*.json"):
        items[path.stem] = Item.model_validate_json(path.read_text(encoding="utf-8"))
    for char_path in chars_dir.glob("*.json"):
        char = Character.model_validate_json(char_path.read_text(encoding="utf-8"))
        for iid in char.inventory_ids:
            it = items.get(iid)
            if it is None:
                continue
            eff = it.effects
            if isinstance(eff, WeaponEffect):
                if char.equipment.weapon is None:
                    char.equipment.weapon = it.id
            elif isinstance(eff, ArmorEffect):
                if char.equipment.armor is None:
                    char.equipment.armor = it.id
                elif char.equipment.accessory is None:
                    char.equipment.accessory = it.id
            elif eff is None:
                if char.equipment.accessory is None:
                    char.equipment.accessory = it.id
        char_path.write_text(char.model_dump_json(indent=2), encoding="utf-8")
