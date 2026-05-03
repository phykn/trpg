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
    (sd / "races" / "human.json").write_text(json.dumps({
        "id": "human",
        "name": "인간",
        "description": "보통 사람.",
        "is_humanoid": True,
        "racial_skill_ids": ["barter"],
        "stat_modifiers": {},
    }, ensure_ascii=False), encoding="utf-8")
    (sd / "skills").mkdir()
    (sd / "skills" / "barter.json").write_text(json.dumps({
        "id": "barter",
        "name": "흥정",
        "description": "값을 깎는 능력.",
        "type": "buff",
        "target": "single",
        "primary_stat": "CHA",
        "level": 1,
        "mp_cost": 0,
        "special_effect": "",
    }, ensure_ascii=False), encoding="utf-8")
    return sd


def test_check_entity_skill_ok(capsys, tmp_path):
    sd = _scaffold_minimal_scenario(tmp_path)
    skill_path = tmp_path / "new_skill.json"
    skill_path.write_text(json.dumps({
        "id": "trip",
        "name": "발걸기",
        "description": "상대를 넘어뜨립니다.",
        "type": "debuff",
        "target": "single",
        "primary_stat": "DEX",
        "level": 1,
        "mp_cost": 1,
        "special_effect": "",
    }, ensure_ascii=False), encoding="utf-8")
    rc = tool._main(["check-entity", "skill", str(sd), str(skill_path)])
    assert rc == 0
    assert capsys.readouterr().out.strip() == "OK"


def test_check_entity_race_unknown_skill(capsys, tmp_path):
    sd = _scaffold_minimal_scenario(tmp_path)
    race_path = tmp_path / "elf.json"
    race_path.write_text(json.dumps({
        "id": "elf",
        "name": "엘프",
        "description": "긴 귀.",
        "is_humanoid": True,
        "racial_skill_ids": ["fire_breath"],  # not on disk
        "stat_modifiers": {},
    }, ensure_ascii=False), encoding="utf-8")
    rc = tool._main(["check-entity", "race", str(sd), str(race_path)])
    assert rc == 1
    err = capsys.readouterr().err
    assert "fire_breath" in err
