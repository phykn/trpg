"""equip-fill subcommand — derives character.equipment slots from inventory."""

import json
from pathlib import Path

from agency.story import tool


def _scaffold_with_inventory(tmp_path: Path) -> Path:
    sd = tmp_path / "scen"
    sd.mkdir()
    (sd / "world.md").write_text("테스트", encoding="utf-8")
    (sd / "items").mkdir()
    (sd / "items" / "sword.json").write_text(
        json.dumps(
            {
                "id": "sword",
                "name": "철검",
                "description": "쇠로 만든 검.",
                "weight": 3,
                "effects": {"type": "weapon", "weapon_dice": "1d6"},
                "required": None,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (sd / "items" / "leather.json").write_text(
        json.dumps(
            {
                "id": "leather",
                "name": "가죽 갑옷",
                "description": "낡은 가죽.",
                "weight": 5,
                "effects": {"type": "armor", "defense": 2},
                "required": None,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (sd / "characters").mkdir()
    (sd / "characters" / "fighter.json").write_text(
        json.dumps(
            {
                "id": "fighter",
                "name": "검사",
                "description": "전사.",
                "race_id": "human",
                "location_id": "town",
                "level": 1,
                "stats": {
                    "body": 10,
                    "agility": 10,
                    "mind": 10,
                    "presence": 10,
                },
                "hp": 27,
                "max_hp": 27,
                "mp": 20,
                "max_mp": 20,
                "racial_skill_ids": [],
                "learned_skill_ids": [],
                "inventory_ids": ["sword", "leather"],
                "equipment": {"weapon": None, "armor": None, "accessory": None},
                "job": "전사",
                "gender": "male",
                "alive": True,
                "xp_reward": 0,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return sd


def test_equip_fill_assigns_weapon_and_armor(capsys, tmp_path):
    sd = _scaffold_with_inventory(tmp_path)
    rc = tool._main(["equip-fill", str(sd)])
    assert rc == 0, capsys.readouterr().err
    assert capsys.readouterr().out.strip() == "OK"
    char = json.loads((sd / "characters" / "fighter.json").read_text(encoding="utf-8"))
    assert char["equipment"]["weapon"] == "sword"
    assert char["equipment"]["armor"] == "leather"
    assert char["equipment"]["accessory"] is None
