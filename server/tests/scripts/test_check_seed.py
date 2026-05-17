from pathlib import Path

from server.scripts.check_seed import main


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_check_seed_prints_warnings_without_failing(tmp_path, capsys):
    scenario = tmp_path / "demo"
    _write(scenario / "profile.json", '{"id":"demo","name":"Demo"}')
    _write(
        scenario / "start.json",
        '{"start_location_id":"town","active_subject_id":null,"active_quest_id":null}',
    )
    _write(scenario / "races" / "human.json", '{"id":"human"}')
    _write(scenario / "locations" / "town.json", '{"id":"town"}')
    _write(scenario / "items" / "badge.json", '{"id":"badge"}')
    _write(
        scenario / "characters" / "guard_01.json",
        '{"id":"guard_01","race_id":"human","location_id":"town"}',
    )

    assert main(["check_seed", str(scenario)]) == 0

    out = capsys.readouterr().out
    assert "OK:" in out
    assert "0 violations" in out
    assert "warnings" in out
    assert "character guard_01 missing recommended field: traits" in out
    assert "missing recommended field: speech_style" not in out
