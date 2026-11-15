from pathlib import Path

from src.story.check import report_checks

SCENARIOS = Path(__file__).resolve().parents[2] / "scenarios"


def test_report_prints_each_check_and_fails_on_a_broken_story(tmp_path, capsys):
    for folder in ("skeleton", "dawn"):
        assert report_checks(SCENARIOS / folder) == 0
        assert capsys.readouterr().out == "통과  가리키는 것이 있다\n"
    assert report_checks(tmp_path) == 1
    assert capsys.readouterr().out.startswith("떨어짐  읽기  ")
