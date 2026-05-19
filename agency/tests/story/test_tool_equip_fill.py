"""equip-fill subcommand — normalizes NPC equipment for server graph seeding."""

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
                "traits": ["묵직합니다"],
                "price": 10,
                "consumable": False,
                "slot": "weapon",
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
                "traits": ["움직이기 쉽습니다"],
                "price": 8,
                "consumable": False,
                "slot": "armor",
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
                "race": "human",
                "gender": "male",
                "location": "town",
                "level": 1,
                "role": "전사",
                "background": "검술 훈련을 받았습니다.",
                "appearance": "검을 잡고 서 있습니다.",
                "traits": ["침착합니다"],
                "mbti": "ISTP",
                "learned_skills": [],
                "inventory": ["sword", "leather"],
                "equipment": {"weapon": "sword", "armor": "leather"},
                "alive": True,
                "relations": {},
                "xp_reward": 0,
                "protected": False,
                "gold": 0,
                "active_buffs": [],
                "memories": [],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return sd


def test_equip_fill_clears_npc_equipment_and_preserves_inventory(capsys, tmp_path):
    sd = _scaffold_with_inventory(tmp_path)
    rc = tool._main(["equip-fill", str(sd)])
    assert rc == 0, capsys.readouterr().err
    assert capsys.readouterr().out.strip() == "OK"
    char = json.loads((sd / "characters" / "fighter.json").read_text(encoding="utf-8"))
    assert char["inventory"] == ["sword", "leather"]
    assert char["equipment"] == {}


def test_equip_fill_clears_aggregate_characters(capsys, tmp_path):
    sd = tmp_path / "scen"
    sd.mkdir()
    (sd / "characters.json").write_text(
        json.dumps(
            {
                "fighter": {
                    "id": "fighter",
                    "inventory": ["sword"],
                    "equipment": {"weapon": "sword"},
                }
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    rc = tool._main(["equip-fill", str(sd)])

    assert rc == 0, capsys.readouterr().err
    chars = json.loads((sd / "characters.json").read_text(encoding="utf-8"))
    assert chars["fighter"]["inventory"] == ["sword"]
    assert chars["fighter"]["equipment"] == {}
