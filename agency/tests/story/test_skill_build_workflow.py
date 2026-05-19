"""Smoke-test the agency/story/SKILL.md build order against the real CLI."""

import json
from pathlib import Path

from agency.story import tool


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def _run_ok(capsys, *args: str) -> None:
    rc = tool._main(list(args))
    out = capsys.readouterr()
    assert rc == 0, out.err
    assert out.out.strip() == "OK"


def test_story_skill_build_order_produces_sweepable_seed(capsys, tmp_path):
    scenario = tmp_path / "scenarios" / "skill_smoke"
    decomp = scenario / ".decomp"
    for dirname in [
        "races",
        "locations",
        "characters",
        "skills",
        "items",
        "quests",
        "chapters",
    ]:
        (scenario / dirname).mkdir(parents=True)

    setup = {
        "world_md": "작은 마을의 낡은 표지판에는 오래된 길의 단서가 남아 있습니다.",
        "profile_name": "기술 검증 마을",
        "profile_description": "story skill 절차 검증용 작은 시나리오입니다.",
        "races": [
            {
                "id": "human",
                "role": "마을 사람",
                "racial_skills": ["barter"],
                "is_humanoid": True,
            }
        ],
        "skills": [
            {
                "id": "barter",
                "role": "침착한 설득",
                "primary_stat": "presence",
                "type": "buff",
            }
        ],
        "locations": [
            {"id": "town_square", "role": "마을 광장", "connections": []}
        ],
        "start_location": "town_square",
    }
    cast = {
        "characters": [
            {
                "id": "guide",
                "role": "안내자",
                "is_enemy": False,
                "location": "town_square",
                "race": "human",
                "learned_skills": [],
            }
        ],
        "items": [
            {
                "id": "iron_armor",
                "kind": "armor",
                "role": "안내자의 낡은 갑옷",
                "owner_character": "guide",
            },
            {
                "id": "old_map",
                "kind": "key",
                "role": "플레이어가 가진 낡은 지도",
                "for_player": True,
            },
        ],
        "start_subject": "guide",
    }
    arc = {
        "quests": [
            {
                "id": "read_sign",
                "title": "표지판 읽기",
                "trigger_kind": "location_enter",
                "target": "town_square",
                "giver": "guide",
                "role": "광장의 단서를 확인합니다.",
                "prerequisites": [],
                "required": True,
            }
        ],
        "chapters": [
            {
                "id": "chapter_01",
                "title": "첫 단서",
                "role": "마을 광장에서 시작합니다.",
                "quests": ["read_sign"],
                "prerequisites": [],
            }
        ],
        "start_quest": "read_sign",
    }
    _write_json(decomp / "setup.json", setup)
    _write_json(decomp / "cast.json", cast)
    _write_json(decomp / "arc.json", arc)

    _run_ok(capsys, "decompose-setup", str(decomp / "setup.json"))
    _run_ok(
        capsys,
        "decompose-cast",
        str(decomp / "setup.json"),
        str(decomp / "cast.json"),
    )
    _run_ok(
        capsys,
        "decompose-arc",
        str(decomp / "setup.json"),
        str(decomp / "cast.json"),
        str(decomp / "arc.json"),
    )

    (scenario / "world.md").write_text(setup["world_md"], encoding="utf-8")
    _write_json(
        scenario / "races" / "human.json",
        {
            "id": "human",
            "name": "인간",
            "description": "평범한 마을 사람입니다.",
            "is_humanoid": True,
            "racial_skills": ["barter"],
        },
    )
    _run_ok(
        capsys,
        "check-entity",
        "race",
        str(scenario),
        str(scenario / "races" / "human.json"),
        "--decomp",
        str(decomp),
    )

    _write_json(
        scenario / "locations" / "town_square.json",
        {
            "id": "town_square",
            "name": "마을 광장",
            "description": "낡은 표지판이 서 있는 작은 광장입니다.",
            "mood": "조용합니다.",
            "traits": ["표지판이 길의 단서를 품고 있습니다."],
            "knowledge": ["old_sign"],
            "connections": [],
            "items": [],
        },
    )
    _run_ok(
        capsys,
        "check-entity",
        "location",
        str(scenario),
        str(scenario / "locations" / "town_square.json"),
        "--decomp",
        str(decomp),
    )

    _write_json(
        scenario / "characters" / "guide.json",
        {
            "id": "guide",
            "name": "안내자",
            "race": "human",
            "gender": "female",
            "mbti": "ISTJ",
            "role": "길을 안내하는 주민",
            "background": "광장의 표지판을 오래 지켜봤습니다.",
            "appearance": "낡은 갑옷을 단정히 걸치고 있습니다.",
            "traits": ["침착합니다"],
            "knowledge": ["old_sign"],
            "level": 1,
            "location": "town_square",
            "alive": True,
            "inventory": ["iron_armor"],
            "equipment": {},
            "learned_skills": [],
            "relations": {"player_01": 0},
            "xp_reward": 0,
            "protected": True,
            "gold": 0,
            "active_buffs": [],
            "memories": [],
        },
    )
    _run_ok(
        capsys,
        "check-entity",
        "character",
        str(scenario),
        str(scenario / "characters" / "guide.json"),
        "--decomp",
        str(decomp),
        "--skeleton",
    )

    _write_json(
        scenario / "skills" / "barter.json",
        {
            "id": "barter",
            "name": "흥정",
            "description": "당신은 차분한 대화로 작은 도움을 얻습니다.",
            "level": 1,
            "action": "social",
            "bonus": 1,
            "mp_cost": 0,
        },
    )
    _run_ok(
        capsys,
        "check-entity",
        "skill",
        str(scenario),
        str(scenario / "skills" / "barter.json"),
        "--decomp",
        str(decomp),
    )

    _write_json(
        scenario / "effects.json",
        {
            "sturdy_guard": {
                "id": "sturdy_guard",
                "name": "단단한 방어",
                "kind": "defense_boost",
            }
        },
    )
    _write_json(
        scenario / "items" / "iron_armor.json",
        {
            "id": "iron_armor",
            "name": "낡은 철갑",
            "description": "안내자가 몸을 보호하려고 입은 낡은 갑옷입니다.",
            "price": 8,
            "consumable": False,
            "slot": "armor",
            "action": "defend",
            "bonus": 1,
            "effect": "sturdy_guard",
        },
    )
    _run_ok(
        capsys,
        "check-entity",
        "item",
        str(scenario),
        str(scenario / "items" / "iron_armor.json"),
        "--decomp",
        str(decomp),
    )
    _write_json(
        scenario / "items" / "old_map.json",
        {
            "id": "old_map",
            "name": "낡은 지도",
            "description": "당신이 처음부터 지닌 낡은 지도입니다.",
            "price": 0,
            "consumable": False,
            "knowledge": ["old_sign"],
        },
    )
    _run_ok(
        capsys,
        "check-entity",
        "item",
        str(scenario),
        str(scenario / "items" / "old_map.json"),
        "--decomp",
        str(decomp),
    )

    _run_ok(capsys, "equip-fill", str(scenario))

    _write_json(
        scenario / "quests" / "read_sign.json",
        {
            "id": "read_sign",
            "title": "표지판 읽기",
            "description": "마을 광장에서 오래된 표지판의 단서를 확인합니다.",
            "giver": "guide",
            "triggers": [
                {
                    "id": "enter_square",
                    "type": "location_enter",
                    "target": "town_square",
                }
            ],
            "fail_triggers": [],
            "prerequisites": [],
            "status": "active",
            "required": True,
            "rewards": {"gold": 0, "exp": 0, "items": []},
        },
    )
    _run_ok(
        capsys,
        "check-entity",
        "quest",
        str(scenario),
        str(scenario / "quests" / "read_sign.json"),
        "--decomp",
        str(decomp),
    )

    _write_json(
        scenario / "chapters" / "chapter_01.json",
        {
            "id": "chapter_01",
            "title": "첫 단서",
            "description": "당신은 광장에서 첫 단서를 확인합니다.",
            "quests": ["read_sign"],
            "prerequisites": [],
            "status": "active",
        },
    )
    _run_ok(
        capsys,
        "check-entity",
        "chapter",
        str(scenario),
        str(scenario / "chapters" / "chapter_01.json"),
        "--decomp",
        str(decomp),
    )

    _write_json(
        scenario / "profile.json",
        {
            "id": "skill_smoke",
            "name": setup["profile_name"],
            "description": setup["profile_description"],
        },
    )
    _write_json(
        scenario / "start.json",
        {
            "start_location": setup["start_location"],
            "active_subject": cast["start_subject"],
            "active_quest": arc["start_quest"],
        },
    )
    _write_json(
        scenario / "player.json",
        {
            "id": "player_01",
            "level": 1,
            "equipment": {},
            "inventory": ["old_map"],
            "companions": [],
            "gold": 0,
            "xp_pool": 0,
        },
    )
    _write_json(
        scenario / "slots.json",
        {"armor": {"id": "armor", "name": "갑옷"}},
    )
    _write_json(
        scenario / "knowledge.json",
        {
            "old_sign": {
                "id": "old_sign",
                "title": "낡은 표지판",
                "summary": "표지판은 북쪽 길이 오래전에 막혔다고 알려 줍니다.",
                "visibility": "public",
            }
        },
    )
    _write_json(scenario / "mbti.json", {"ISTJ": {"id": "ISTJ", "name": "ISTJ"}})

    _run_ok(capsys, "sweep", str(scenario))
