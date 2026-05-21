"""sweep subcommand — runs seed record checks on the assembled directory."""

import json
from pathlib import Path

from agency.story import tool


def _scaffold_minimal_passable(tmp_path: Path) -> Path:
    sd = tmp_path / "swept"
    sd.mkdir()
    (sd / "world.md").write_text("테스트 세계.", encoding="utf-8")
    (sd / "races").mkdir()
    (sd / "skills").mkdir()
    (sd / "locations").mkdir()
    (sd / "items").mkdir()
    (sd / "characters").mkdir()
    (sd / "quests").mkdir()
    (sd / "chapters").mkdir()
    (sd / "profile.json").write_text(
        json.dumps(
            {
                "id": "swept",
                "name": "테스트",
                "description": "테스트 프로필",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return sd


def test_sweep_passes_on_empty_scaffold_or_reports_missing(capsys, tmp_path):
    sd = _scaffold_minimal_passable(tmp_path)
    rc = tool._main(["sweep", str(sd)])
    out = capsys.readouterr()
    if rc == 0:
        assert out.out.strip() == "OK"
    else:
        # invariant이 빈 시나리오를 거부하면 메시지가 와야 함
        assert out.err.strip()


def test_sweep_loads_runtime_catalog_records(capsys, tmp_path):
    sd = _scaffold_minimal_passable(tmp_path)
    (sd / "start.json").write_text(
        json.dumps(
            {
                "start_location": "town",
                "active_subject": "guide",
                "active_quest": "look_around",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (sd / "races" / "human.json").write_text(
        json.dumps(
            {
                "id": "human",
                "name": "인간",
                "description": "사람입니다.",
                "is_humanoid": True,
                "racial_skills": ["barter"],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (sd / "skills" / "barter.json").write_text(
        json.dumps(
            {
                "id": "barter",
                "name": "흥정",
                "description": "말로 상황을 풉니다.",
                "level": 1,
                "action": "talk",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (sd / "locations" / "town.json").write_text(
        json.dumps(
            {
                "id": "town",
                "name": "마을",
                "description": "작은 마을입니다.",
                "mood": "조용합니다.",
                "traits": ["단서가 있습니다"],
                "knowledge": ["town_clue"],
                "items": ["ring"],
                "connections": [],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (sd / "items" / "ring.json").write_text(
        json.dumps(
            {
                "id": "ring",
                "name": "반지",
                "description": "작은 반지입니다.",
                "traits": ["얇습니다"],
                "knowledge": ["town_clue"],
                "price": 1,
                "consumable": False,
                "slot": "accessory",
                "effect": "dc_down",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (sd / "characters" / "guide.json").write_text(
        json.dumps(
            {
                "id": "guide",
                "race": "human",
                "gender": "female",
                "name": "안내자",
                "mbti": "ISTJ",
                "role": "안내자",
                "background": "마을을 안내합니다.",
                "appearance": "반듯하게 서 있습니다.",
                "traits": ["침착합니다"],
                "knowledge": ["town_clue"],
                "level": 1,
                "alive": True,
                "active_buffs": [],
                "location": "town",
                "inventory": ["ring"],
                "equipment": {},
                "gold": 0,
                "learned_skills": [],
                "relations": {"player_01": 0},
                "xp_reward": 0,
                "protected": False,
                "memories": [],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (sd / "quests" / "look_around.json").write_text(
        json.dumps(
            {
                "id": "look_around",
                "title": "둘러보기",
                "description": "마을을 둘러봅니다.",
                "giver": "guide",
                "triggers": [
                    {"id": "enter_town", "type": "location_enter", "target": "town"}
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
    (sd / "chapters" / "chapter_01.json").write_text(
        json.dumps(
            {
                "id": "chapter_01",
                "title": "시작",
                "description": "시작 장입니다.",
                "quests": ["look_around"],
                "prerequisites": [],
                "status": "active",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (sd / "effects.json").write_text(
        json.dumps({"dc_down": {"id": "dc_down", "name": "난이도 감소"}}, ensure_ascii=False),
        encoding="utf-8",
    )
    (sd / "slots.json").write_text(
        json.dumps({"accessory": {"id": "accessory", "name": "장신구"}}, ensure_ascii=False),
        encoding="utf-8",
    )
    (sd / "actions.json").write_text(
        json.dumps({"talk": {"id": "talk", "name": "대화"}}, ensure_ascii=False),
        encoding="utf-8",
    )
    (sd / "knowledge.json").write_text(
        json.dumps(
            {"town_clue": {"id": "town_clue", "title": "마을 단서", "visibility": "public"}},
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (sd / "mbti.json").write_text(
        json.dumps({"ISTJ": {"id": "ISTJ", "name": "ISTJ"}}, ensure_ascii=False),
        encoding="utf-8",
    )

    rc = tool._main(["sweep", str(sd)])

    assert rc == 0, capsys.readouterr().err
    assert capsys.readouterr().out.strip() == "OK"


def test_sweep_rejects_unassigned_quest(capsys, tmp_path):
    sd = _scaffold_minimal_passable(tmp_path)
    (sd / "start.json").write_text(
        json.dumps({"start_location": "town", "active_quest": "look_around"}),
        encoding="utf-8",
    )
    (sd / "races" / "human.json").write_text(
        json.dumps({"id": "human", "name": "인간", "description": ""}),
        encoding="utf-8",
    )
    (sd / "locations" / "town.json").write_text(
        json.dumps({"id": "town", "name": "마을"}),
        encoding="utf-8",
    )
    (sd / "quests" / "look_around.json").write_text(
        json.dumps(
            {
                "id": "look_around",
                "title": "둘러보기",
                "giver": None,
                "triggers": [],
                "fail_triggers": [],
                "prerequisites": [],
                "status": "active",
                "required": True,
                "rewards": {"gold": 0, "exp": 0, "items": []},
            }
        ),
        encoding="utf-8",
    )
    (sd / "chapters" / "chapter_01.json").write_text(
        json.dumps(
            {
                "id": "chapter_01",
                "title": "시작",
                "quests": [],
                "prerequisites": [],
                "status": "active",
            }
        ),
        encoding="utf-8",
    )

    rc = tool._main(["sweep", str(sd)])

    assert rc == 1
    err = capsys.readouterr().err
    assert "look_around" in err
    assert "not assigned to any chapter" in err


def test_sweep_rejects_active_quest_in_locked_chapter(capsys, tmp_path):
    sd = _scaffold_minimal_passable(tmp_path)
    (sd / "start.json").write_text(
        json.dumps({"start_location": "town", "active_quest": "look_around"}),
        encoding="utf-8",
    )
    (sd / "races" / "human.json").write_text(
        json.dumps({"id": "human", "name": "인간", "description": ""}),
        encoding="utf-8",
    )
    (sd / "locations" / "town.json").write_text(
        json.dumps({"id": "town", "name": "마을"}),
        encoding="utf-8",
    )
    (sd / "quests" / "look_around.json").write_text(
        json.dumps(
            {
                "id": "look_around",
                "title": "둘러보기",
                "giver": None,
                "triggers": [],
                "fail_triggers": [],
                "prerequisites": [],
                "status": "active",
                "required": True,
                "rewards": {"gold": 0, "exp": 0, "items": []},
            }
        ),
        encoding="utf-8",
    )
    (sd / "chapters" / "chapter_01.json").write_text(
        json.dumps(
            {
                "id": "chapter_01",
                "title": "시작",
                "quests": ["look_around"],
                "prerequisites": ["chapter_00"],
                "status": "locked",
            }
        ),
        encoding="utf-8",
    )
    (sd / "chapters" / "chapter_00.json").write_text(
        json.dumps(
            {
                "id": "chapter_00",
                "title": "이전",
                "quests": [],
                "prerequisites": [],
                "status": "completed",
            }
        ),
        encoding="utf-8",
    )

    rc = tool._main(["sweep", str(sd)])

    assert rc == 1
    assert "must belong to an active chapter" in capsys.readouterr().err
