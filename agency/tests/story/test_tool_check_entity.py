"""check-entity subcommand — wraps spec.check_refs + entity invariants.

Per-entity check uses the on-disk pool from scenario_dir. With no flags,
behaves identically to the legacy `_validate_entity_response`.
"""

import json
from pathlib import Path

from agency.story import tool


def _scaffold_minimal_scenario(tmp_path: Path) -> Path:
    """Create a tiny scenario dir with one race + one skill + world.md.
    Used as the on-disk pool for cross-ref checks."""
    sd = tmp_path / "tiny"
    sd.mkdir()
    (sd / "world.md").write_text("테스트", encoding="utf-8")
    (sd / "races").mkdir()
    (sd / "races" / "human.json").write_text(
        json.dumps(
            {
                "id": "human",
                "name": "인간",
                "description": "보통 사람.",
                "is_humanoid": True,
                "racial_skill_ids": ["barter"],
                "stat_modifiers": {},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (sd / "skills").mkdir()
    (sd / "skills" / "barter.json").write_text(
        json.dumps(
            {
                "id": "barter",
                "name": "흥정",
                "description": "값을 깎는 능력.",
                "type": "buff",
                "target": "single",
                "primary_stat": "CHA",
                "level": 1,
                "mp_cost": 0,
                "special_effect": "",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return sd


def test_check_entity_skill_ok(capsys, tmp_path):
    sd = _scaffold_minimal_scenario(tmp_path)
    skill_path = tmp_path / "new_skill.json"
    skill_path.write_text(
        json.dumps(
            {
                "id": "trip",
                "name": "발걸기",
                "description": "상대를 넘어뜨립니다.",
                "type": "debuff",
                "target": "single",
                "primary_stat": "DEX",
                "level": 1,
                "mp_cost": 1,
                "special_effect": "",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    rc = tool._main(["check-entity", "skill", str(sd), str(skill_path)])
    assert rc == 0
    assert capsys.readouterr().out.strip() == "OK"


def test_check_entity_race_unknown_skill(capsys, tmp_path):
    sd = _scaffold_minimal_scenario(tmp_path)
    race_path = tmp_path / "elf.json"
    race_path.write_text(
        json.dumps(
            {
                "id": "elf",
                "name": "엘프",
                "description": "긴 귀.",
                "is_humanoid": True,
                "racial_skill_ids": ["fire_breath"],  # not on disk
                "stat_modifiers": {},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    rc = tool._main(["check-entity", "race", str(sd), str(race_path)])
    assert rc == 1
    err = capsys.readouterr().err
    assert "fire_breath" in err


def test_check_entity_with_decomp_pool(capsys, tmp_path):
    """decompose 명단에 있는 ID는 디스크에 없어도 valid로 인정."""
    sd = _scaffold_minimal_scenario(tmp_path)
    # decompose 디렉토리: 'fire_breath' 스킬을 명단에 포함
    decomp_dir = tmp_path / ".decomp"
    decomp_dir.mkdir()
    setup = {
        "world_md": "테스트",
        "profile_name": "테스트",
        "profile_description": "테스트",
        "races": [
            {
                "id": "human",
                "role": "주민",
                "racial_skill_ids": ["barter"],
                "is_humanoid": True,
            },
            {
                "id": "elf",
                "role": "엘프",
                "racial_skill_ids": ["fire_breath"],
                "is_humanoid": True,
            },
        ],
        "skills": [
            {"id": "barter", "role": "흥정", "primary_stat": "CHA", "type": "buff"},
            {
                "id": "fire_breath",
                "role": "화염숨결",
                "primary_stat": "INT",
                "type": "attack",
            },
        ],
        "locations": [{"id": "town", "role": "광장", "connection_ids": []}],
        "start_location_id": "town",
    }
    (decomp_dir / "setup.json").write_text(
        json.dumps(setup, ensure_ascii=False), encoding="utf-8"
    )
    race_path = tmp_path / "elf.json"
    race_path.write_text(
        json.dumps(
            {
                "id": "elf",
                "name": "엘프",
                "description": "긴 귀.",
                "is_humanoid": True,
                "racial_skill_ids": ["fire_breath"],
                "stat_modifiers": {},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    rc = tool._main(
        [
            "check-entity",
            "race",
            str(sd),
            str(race_path),
            "--decomp",
            str(decomp_dir),
        ]
    )
    assert rc == 0, capsys.readouterr().err
    assert capsys.readouterr().out.strip() == "OK"


def _scaffold_for_character(tmp_path: Path) -> Path:
    """character 검사용 시나리오: race + skill + location 1개씩."""
    sd = tmp_path / "char_test"
    sd.mkdir()
    (sd / "world.md").write_text("테스트", encoding="utf-8")
    (sd / "races").mkdir()
    (sd / "races" / "human.json").write_text(
        json.dumps(
            {
                "id": "human",
                "name": "인간",
                "description": "보통 사람.",
                "is_humanoid": True,
                "racial_skill_ids": ["barter"],
                "stat_modifiers": {},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (sd / "skills").mkdir()
    (sd / "skills" / "barter.json").write_text(
        json.dumps(
            {
                "id": "barter",
                "name": "흥정",
                "description": "값을 깎는 능력.",
                "type": "buff",
                "primary_stat": "CHA",
                "level": 1,
                "mp_cost": 0,
                "cooldown": 0,
                "target": "single",
                "special_effect": "",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (sd / "locations").mkdir()
    (sd / "locations" / "town.json").write_text(
        json.dumps(
            {
                "id": "town",
                "name": "광장",
                "description": "마을 광장.",
                "connections": [],
                "item_ids": [],
                "props": [],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return sd


# HP/MP formula (server/src/engines/growth.py):
#   calc_max_hp(level, CON) = (10 + CON) + level * (5 + CON // 4)
#   calc_max_mp(level, INT) = (5  + INT) + level * (3 + INT // 4)
# For level=1, all stats=10:
#   max_hp = (10+10) + 1*(5 + 10//4) = 20 + 7 = 27
#   max_mp = (5+10)  + 1*(3 + 10//4) = 15 + 5 = 20
# The fixture must pass `check_character` (skeleton=True) but FAIL `check_seed_character`
# (skeleton=False) because robe_99 isn't in the items pool.
CHARACTER_WITH_FUTURE_INV = {
    "id": "villager_01",
    "name": "철수",
    "description": "마을 주민.",
    "race_id": "human",
    "location_id": "town",
    "level": 1,
    "stats": {"STR": 10, "DEX": 10, "CON": 10, "INT": 10, "WIS": 10, "CHA": 10},
    "hp": 27,
    "max_hp": 27,
    "mp": 20,
    "max_mp": 20,
    "racial_skill_ids": ["barter"],
    "learned_skill_ids": [],
    "inventory_ids": ["robe_99"],  # 디스크에 없음 — skeleton 모드에서 통과해야 함
    "equipment": {"weapon": None, "armor": None, "accessory": None},
    "job": "주민",
    "gender": "male",
    "alive": True,
    "xp_reward": 0,
}


def test_check_entity_character_skeleton_skips_inventory_pool(capsys, tmp_path):
    sd = _scaffold_for_character(tmp_path)
    cp = tmp_path / "villager.json"
    cp.write_text(
        json.dumps(CHARACTER_WITH_FUTURE_INV, ensure_ascii=False), encoding="utf-8"
    )
    rc = tool._main(
        [
            "check-entity",
            "character",
            str(sd),
            str(cp),
            "--skeleton",
        ]
    )
    assert rc == 0, capsys.readouterr().err
    assert capsys.readouterr().out.strip() == "OK"


def test_check_entity_character_full_catches_missing_inventory(capsys, tmp_path):
    sd = _scaffold_for_character(tmp_path)
    cp = tmp_path / "villager.json"
    cp.write_text(
        json.dumps(CHARACTER_WITH_FUTURE_INV, ensure_ascii=False), encoding="utf-8"
    )
    rc = tool._main(
        [
            "check-entity",
            "character",
            str(sd),
            str(cp),
        ]
    )
    assert rc == 1
    err = capsys.readouterr().err
    # 풀-의존 검사가 robe_99 누락을 잡아야 함
    assert "robe_99" in err or "inventory" in err.lower()
