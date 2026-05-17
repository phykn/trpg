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
        '{"start_location":"town","active_subject":null,"active_quest":null}',
    )
    _write(scenario / "races" / "human.json", '{"id":"human"}')
    _write(scenario / "locations" / "town.json", '{"id":"town"}')
    _write(scenario / "items" / "badge.json", '{"id":"badge"}')
    _write(
        scenario / "characters" / "guard_01.json",
        '{"id":"guard_01","race":"human","location":"town"}',
    )

    assert main(["check_seed", str(scenario)]) == 0

    out = capsys.readouterr().out
    assert "OK:" in out
    assert "0 violations" in out
    assert "warnings" in out
    assert "character guard_01 missing recommended field: traits" in out
    assert "missing recommended field: speech_style" not in out


def test_check_seed_validates_player_json(tmp_path, capsys):
    scenario = tmp_path / "demo"
    _write(scenario / "profile.json", '{"id":"demo","name":"Demo"}')
    _write(
        scenario / "start.json",
        '{"start_location":"town","active_subject":null,"active_quest":null}',
    )
    _write(scenario / "player.json", '{"id":"player_01","inventory_ids":[]}')
    _write(scenario / "races" / "human.json", '{"id":"human"}')
    _write(
        scenario / "locations" / "town.json",
        '{"id":"town","mood":"quiet","traits":["safe"]}',
    )
    _write(scenario / "items" / "badge.json", '{"id":"badge","traits":["metal"]}')
    _write(
        scenario / "characters" / "guard_01.json",
        '{"id":"guard_01","race":"human","location":"town","mbti":"ISTJ","traits":["watchful"]}',
    )

    assert main(["check_seed", str(scenario)]) == 1

    out = capsys.readouterr().out
    assert "player.inventory_ids uses legacy key; use 'inventory'" in out
