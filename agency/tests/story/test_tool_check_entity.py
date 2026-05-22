"""check-entity subcommand — wraps spec.check_refs + entity invariants.

Per-entity check uses the on-disk pool from scenario_dir. With no flags, it
runs the same validation path used by generated entity checks.
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
                "racial_skills": ["barter"],
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
                "level": 1,
                "action": "talk",
                "bonus": 1,
                "mp_cost": 0,
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
                "level": 1,
                "action": "attack",
                "bonus": 1,
                "mp_cost": 1,
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
                "racial_skills": ["fire_breath"],  # not on disk
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
                "racial_skills": ["barter"],
                "is_humanoid": True,
            },
            {
                "id": "elf",
                "role": "엘프",
                "racial_skills": ["fire_breath"],
                "is_humanoid": True,
            },
        ],
        "skills": [
            {
                "id": "barter",
                "role": "흥정",
                "primary_stat": "presence",
                "type": "buff",
            },
            {
                "id": "fire_breath",
                "role": "화염숨결",
                "primary_stat": "mind",
                "type": "attack",
            },
        ],
        "locations": [{"id": "town", "role": "광장", "connections": []}],
        "start_location": "town",
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
                "racial_skills": ["fire_breath"],
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
                "racial_skills": ["barter"],
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
                "level": 1,
                "action": "talk",
                "bonus": 1,
                "mp_cost": 0,
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
                "mood": "조용합니다.",
                "traits": ["열린 공간입니다"],
                "connections": [],
                "items": [],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return sd


CHARACTER_WITH_FUTURE_INV = {
    "id": "villager_01",
    "name": "철수",
    "description": "마을 주민.",
    "race": "human",
    "location": "town",
    "level": 1,
    "alive": True,
    "learned_skills": [],
    "inventory": ["robe_99"],  # 디스크에 없음 — skeleton 모드에서 통과해야 함
    "equipment": {"weapon": None, "armor": None, "accessory": None},
    "gender": "male",
    "traits": ["차분합니다"],
    "mbti": "ISFJ",
    "relations": {},
    "xp_reward": 0,
    "protected": False,
    "gold": 0,
    "active_buffs": [],
    "memories": [],
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


def test_check_entity_character_rejects_npc_equipment(capsys, tmp_path):
    sd = _scaffold_for_character(tmp_path)
    char = dict(CHARACTER_WITH_FUTURE_INV)
    char["inventory"] = []
    char["equipment"] = {"weapon": "sword"}
    cp = tmp_path / "villager.json"
    cp.write_text(json.dumps(char, ensure_ascii=False), encoding="utf-8")

    rc = tool._main(["check-entity", "character", str(sd), str(cp)])

    assert rc == 1
    assert "character.equipment is player-only" in capsys.readouterr().err


def test_check_entity_quest_accepts_runtime_trigger_kinds(capsys, tmp_path):
    sd = _scaffold_for_character(tmp_path)
    (sd / "items").mkdir()
    (sd / "items" / "badge.json").write_text(
        json.dumps(
            {
                "id": "badge",
                "name": "배지",
                "description": "확인용 배지.",
                "price": 1,
                "consumable": False,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (sd / "characters").mkdir()
    (sd / "characters" / "villager_01.json").write_text(
        json.dumps(
            {
                "id": "villager_01",
                "name": "주민",
                "race": "human",
                "gender": "female",
                "location": "town",
                "level": 1,
                "alive": True,
                "inventory": [],
                "equipment": {},
                "learned_skills": [],
                "relations": {},
                "xp_reward": 0,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (sd / "quests").mkdir()
    qp = tmp_path / "quest.json"
    qp.write_text(
        json.dumps(
            {
                "id": "quest_01",
                "title": "확인",
                "description": "확인합니다.",
                "giver": "villager_01",
                "triggers": [
                    {"id": "got_badge", "type": "item_obtained", "target": "badge"},
                    {"id": "asked", "type": "social_check", "target": "villager_01"},
                ],
                "fail_triggers": [],
                "prerequisites": [],
                "status": "active",
                "required": True,
                "rewards": {"gold": 0, "exp": 0, "items": []},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    rc = tool._main(["check-entity", "quest", str(sd), str(qp)])

    assert rc == 0, capsys.readouterr().err
    assert capsys.readouterr().out.strip() == "OK"


def test_check_entity_chapter_uses_decomp_chapter_pool(capsys, tmp_path):
    sd = _scaffold_for_character(tmp_path)
    (sd / "quests").mkdir()
    (sd / "quests" / "quest_01.json").write_text(
        json.dumps(
            {
                "id": "quest_01",
                "title": "확인",
                "description": "확인합니다.",
                "giver": None,
                "triggers": [],
                "fail_triggers": [],
                "prerequisites": [],
                "status": "active",
                "required": True,
                "rewards": {"gold": 0, "exp": 0, "items": []},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (sd / "chapters").mkdir()
    decomp_dir = tmp_path / ".decomp"
    decomp_dir.mkdir()
    (decomp_dir / "arc.json").write_text(
        json.dumps(
            {
                "quests": [
                    {
                        "id": "quest_01",
                        "title": "확인",
                        "trigger_kind": "location_enter",
                        "target": "town",
                        "giver": "villager_01",
                        "role": "시작",
                        "prerequisites": [],
                        "required": True,
                    }
                ],
                "chapters": [
                    {
                        "id": "chapter_01",
                        "title": "1장",
                        "role": "시작",
                        "quests": ["quest_01"],
                        "prerequisites": [],
                    },
                    {
                        "id": "chapter_02",
                        "title": "2장",
                        "role": "후속",
                        "quests": [],
                        "prerequisites": ["chapter_01"],
                    },
                ],
                "start_quest": "quest_01",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    cp = tmp_path / "chapter_02.json"
    cp.write_text(
        json.dumps(
            {
                "id": "chapter_02",
                "title": "2장",
                "description": "후속 장입니다.",
                "quests": [],
                "prerequisites": ["chapter_01"],
                "status": "locked",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    rc = tool._main(
        ["check-entity", "chapter", str(sd), str(cp), "--decomp", str(decomp_dir)]
    )

    assert rc == 0, capsys.readouterr().err
    assert capsys.readouterr().out.strip() == "OK"


def test_check_entity_chapter_rejects_unknown_prerequisite(capsys, tmp_path):
    sd = _scaffold_for_character(tmp_path)
    (sd / "quests").mkdir()
    (sd / "quests" / "quest_01.json").write_text(
        json.dumps(
            {
                "id": "quest_01",
                "title": "확인",
                "description": "확인합니다.",
                "giver": None,
                "triggers": [],
                "fail_triggers": [],
                "prerequisites": [],
                "status": "active",
                "required": True,
                "rewards": {"gold": 0, "exp": 0, "items": []},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (sd / "chapters").mkdir()
    cp = tmp_path / "chapter_02.json"
    cp.write_text(
        json.dumps(
            {
                "id": "chapter_02",
                "title": "2장",
                "description": "후속 장입니다.",
                "quests": ["quest_01"],
                "prerequisites": ["missing_chapter"],
                "status": "locked",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    rc = tool._main(["check-entity", "chapter", str(sd), str(cp)])

    assert rc == 1
    assert "missing_chapter" in capsys.readouterr().err


def test_check_entity_rejects_forbidden_seed_shape(capsys, tmp_path):
    sd = _scaffold_for_character(tmp_path)
    item_path = tmp_path / "badge.json"
    item_path.write_text(
        json.dumps(
            {
                "id": "badge",
                "name": "배지",
                "description": "확인용 배지.",
                "price": 1,
                "consumable": False,
                "slot_id": "accessory",
                "required": None,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    rc = tool._main(["check-entity", "item", str(sd), str(item_path)])

    assert rc == 1
    err = capsys.readouterr().err
    assert "slot_id" in err
    assert "required" in err


def test_check_entity_item_checks_support_catalog_refs(capsys, tmp_path):
    sd = _scaffold_for_character(tmp_path)
    (sd / "slots.json").write_text(
        json.dumps({"accessory": {"id": "accessory", "name": "장신구"}}, ensure_ascii=False),
        encoding="utf-8",
    )
    (sd / "knowledge.json").write_text(
        json.dumps({"clue": {"id": "clue", "title": "단서"}}, ensure_ascii=False),
        encoding="utf-8",
    )
    item_path = tmp_path / "badge.json"
    item_path.write_text(
        json.dumps(
            {
                "id": "badge",
                "name": "배지",
                "description": "확인용 배지.",
                "price": 1,
                "consumable": False,
                "slot": "missing_slot",
                "knowledge": ["missing_clue"],
                "action": "dance",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    rc = tool._main(["check-entity", "item", str(sd), str(item_path)])

    assert rc == 1
    err = capsys.readouterr().err
    assert "missing_slot" in err
    assert "missing_clue" in err
    assert "dance" in err


def test_check_entity_location_checks_knowledge_catalog(capsys, tmp_path):
    sd = _scaffold_for_character(tmp_path)
    (sd / "knowledge.json").write_text(
        json.dumps({"clue": {"id": "clue", "title": "단서"}}, ensure_ascii=False),
        encoding="utf-8",
    )
    lp = tmp_path / "town_square.json"
    lp.write_text(
        json.dumps(
            {
                "id": "town_square",
                "name": "광장",
                "description": "작은 광장입니다.",
                "mood": "조용합니다.",
                "traits": ["열린 공간입니다"],
                "knowledge": ["missing_clue"],
                "connections": [{"target": "town"}],
                "items": [],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    rc = tool._main(["check-entity", "location", str(sd), str(lp)])

    assert rc == 1
    assert "missing_clue" in capsys.readouterr().err


def test_check_entity_quest_checks_reward_items(capsys, tmp_path):
    sd = _scaffold_for_character(tmp_path)
    (sd / "characters").mkdir()
    (sd / "characters" / "villager_01.json").write_text(
        json.dumps(
            {
                "id": "villager_01",
                "name": "주민",
                "race": "human",
                "gender": "female",
                "location": "town",
                "level": 1,
                "alive": True,
                "inventory": [],
                "equipment": {},
                "learned_skills": [],
                "relations": {},
                "xp_reward": 0,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (sd / "items").mkdir()
    (sd / "quests").mkdir()
    qp = tmp_path / "quest.json"
    qp.write_text(
        json.dumps(
            {
                "id": "quest_01",
                "title": "확인",
                "description": "확인합니다.",
                "giver": "villager_01",
                "triggers": [],
                "fail_triggers": [],
                "prerequisites": [],
                "status": "active",
                "required": True,
                "rewards": {"gold": 0, "exp": 0, "items": ["missing_badge"]},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    rc = tool._main(["check-entity", "quest", str(sd), str(qp)])

    assert rc == 1
    assert "missing_badge" in capsys.readouterr().err
