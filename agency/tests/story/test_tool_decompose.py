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
            "primary_stat": "CHA",
            "type": "buff",
        }
    ],
    "locations": [
        {"id": "town", "role": "시작 광장", "connection_ids": []}
    ],
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
