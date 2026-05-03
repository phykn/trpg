"""sweep subcommand — runs engines.invariants.check_scenario on the assembled directory."""
import json
from pathlib import Path

from agency.story import tool


def _scaffold_minimal_passable(tmp_path: Path) -> Path:
    """check_scenario를 통과하는 최소 시나리오. 빈 디렉토리 + 기본 메타만 있으면
    check_scenario가 빈 풀로도 OK를 내는지 확인 — 만약 NPC ≥1 같은 invariant이 있으면
    이 fixture를 확장. 일단 schema 단위에서 통과 가능한 구조부터."""
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
    (sd / "profile.json").write_text(json.dumps({
        "id": "swept", "name": "테스트", "description": "테스트 프로필",
    }, ensure_ascii=False), encoding="utf-8")
    return sd


def test_sweep_passes_on_empty_scaffold_or_reports_missing(capsys, tmp_path):
    """check_scenario는 빈 시나리오에 대해 PASS이거나 NPC/start 등 누락을 보고함.
    구체 invariant 동작은 server.engines.invariants 책임 — 여기선 wiring만 검증."""
    sd = _scaffold_minimal_passable(tmp_path)
    rc = tool._main(["sweep", str(sd)])
    out = capsys.readouterr()
    if rc == 0:
        assert out.out.strip() == "OK"
    else:
        # invariant이 빈 시나리오를 거부하면 메시지가 와야 함
        assert out.err.strip()
