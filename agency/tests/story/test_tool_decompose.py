"""decompose-{setup,cast,arc} subcommands.

Each subcommand reads JSON file(s), validates against the matching Pydantic
model + _check_* function, prints OK or a one-paragraph error.
"""

import json

from agency.story import tool


VALID_SETUP = {
    "world_md": "테스트 세계.",
    "profile_name": "테스트",
    "profile_description": "유닛 테스트용 미니 시나리오.",
    "races": [
        {
            "id": "human",
            "role": "마을 주민",
            "racial_skill_ids": ["barter"],
            "is_humanoid": True,
        }
    ],
    "skills": [
        {
            "id": "barter",
            "role": "흥정 능력",
            "primary_stat": "presence",
            "type": "buff",
        }
    ],
    "locations": [{"id": "town", "role": "시작 광장", "connection_ids": []}],
    "start_location_id": "town",
}


def test_decompose_setup_ok(capsys, tmp_path):
    p = tmp_path / "setup.json"
    p.write_text(json.dumps(VALID_SETUP, ensure_ascii=False), encoding="utf-8")
    rc = tool._main(["decompose-setup", str(p)])
    assert rc == 0
    assert capsys.readouterr().out.strip() == "OK"


def test_decompose_setup_missing_skill_in_pool(capsys, tmp_path):
    bad = json.loads(json.dumps(VALID_SETUP))
    bad["races"][0]["racial_skill_ids"] = ["nonexistent_skill"]
    p = tmp_path / "setup.json"
    p.write_text(json.dumps(bad, ensure_ascii=False), encoding="utf-8")
    rc = tool._main(["decompose-setup", str(p)])
    assert rc == 1
    err = capsys.readouterr().err
    assert "nonexistent_skill" in err


VALID_CAST = {
    "characters": [
        {
            "id": "villager_01",
            "role": "마을 주민",
            "is_enemy": False,
            "location_id": "town",
            "race_id": "human",
            "learned_skill_ids": [],
        }
    ],
    "items": [
        {
            "id": "robe_01",
            "kind": "armor",
            "role": "주민 평상복",
            "owner_character_id": "villager_01",
        }
    ],
    "start_subject_id": "villager_01",
}


def test_decompose_cast_ok(capsys, tmp_path):
    sp = tmp_path / "setup.json"
    sp.write_text(json.dumps(VALID_SETUP, ensure_ascii=False), encoding="utf-8")
    cp = tmp_path / "cast.json"
    cp.write_text(json.dumps(VALID_CAST, ensure_ascii=False), encoding="utf-8")
    rc = tool._main(["decompose-cast", str(sp), str(cp)])
    assert rc == 0
    assert capsys.readouterr().out.strip() == "OK"


def test_decompose_cast_bad_race_id(capsys, tmp_path):
    bad = json.loads(json.dumps(VALID_CAST))
    bad["characters"][0]["race_id"] = "elf"  # not in setup
    sp = tmp_path / "setup.json"
    sp.write_text(json.dumps(VALID_SETUP, ensure_ascii=False), encoding="utf-8")
    cp = tmp_path / "cast.json"
    cp.write_text(json.dumps(bad, ensure_ascii=False), encoding="utf-8")
    rc = tool._main(["decompose-cast", str(sp), str(cp)])
    assert rc == 1
    assert "elf" in capsys.readouterr().err


# Arc 테스트는 enemy character가 필요 (character_death trigger의 target).
# VALID_CAST에 적군 추가한 변형 사용.
ENEMY_CAST = json.loads(json.dumps(VALID_CAST))
ENEMY_CAST["characters"].append(
    {
        "id": "bandit_01",
        "role": "산적",
        "is_enemy": True,
        "location_id": "town",
        "race_id": "human",
        "learned_skill_ids": [],
    }
)
ENEMY_CAST["items"].append(
    {
        "id": "robe_02",
        "kind": "armor",
        "role": "산적 옷",
        "owner_character_id": "bandit_01",
    }
)
ENEMY_CAST["items"].append(
    {
        "id": "blade_01",
        "kind": "weapon",
        "role": "산적 단검",
        "owner_character_id": "bandit_01",
    }
)


VALID_ARC = {
    "quests": [
        {
            "id": "quest_01",
            "title": "산적 처치",
            "trigger_kind": "character_death",
            "target_id": "bandit_01",
            "giver_id": "villager_01",
            "role": "시작 퀘스트",
            "prerequisite_ids": [],
            "required": True,
        }
    ],
    "chapters": [
        {
            "id": "chapter_01",
            "title": "1장",
            "role": "오프닝",
            "quest_ids": ["quest_01"],
            "prerequisite_ids": [],
        }
    ],
    "start_quest_id": "quest_01",
}


def test_decompose_arc_ok(capsys, tmp_path):
    sp = tmp_path / "setup.json"
    cp = tmp_path / "cast.json"
    ap = tmp_path / "arc.json"
    sp.write_text(json.dumps(VALID_SETUP, ensure_ascii=False), encoding="utf-8")
    cp.write_text(json.dumps(ENEMY_CAST, ensure_ascii=False), encoding="utf-8")
    ap.write_text(json.dumps(VALID_ARC, ensure_ascii=False), encoding="utf-8")
    rc = tool._main(["decompose-arc", str(sp), str(cp), str(ap)])
    assert rc == 0
    assert capsys.readouterr().out.strip() == "OK"


def test_decompose_arc_unknown_target(capsys, tmp_path):
    bad = json.loads(json.dumps(VALID_ARC))
    bad["quests"][0]["target_id"] = "phantom_01"
    sp = tmp_path / "setup.json"
    cp = tmp_path / "cast.json"
    ap = tmp_path / "arc.json"
    sp.write_text(json.dumps(VALID_SETUP, ensure_ascii=False), encoding="utf-8")
    cp.write_text(json.dumps(ENEMY_CAST, ensure_ascii=False), encoding="utf-8")
    ap.write_text(json.dumps(bad, ensure_ascii=False), encoding="utf-8")
    rc = tool._main(["decompose-arc", str(sp), str(cp), str(ap)])
    assert rc == 1
    assert "phantom_01" in capsys.readouterr().err
