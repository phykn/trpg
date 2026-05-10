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
