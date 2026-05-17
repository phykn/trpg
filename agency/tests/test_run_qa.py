from pathlib import Path

from agency import run_qa
from agency.qa.harness import runner
from agency.qa.harness.transcript import append_transcript_block
from src.db.scenario.local_fs import LocalFsScenarioRepo


def test_qa_defaults_to_dev_test_and_isolated_output_root():
    parser = run_qa._build_parser()

    args = parser.parse_args([])

    assert args.profile == "dev_test"
    assert run_qa.QA_RUN_ROOT == run_qa.ROOT / "qa_test" / "agency"


def test_qa_scenario_repo_is_local_and_resolves_like_server(monkeypatch):
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_KEY", raising=False)
    monkeypatch.delenv("SUPABASE_SCENARIO_BUCKET", raising=False)
    monkeypatch.setenv("SCENARIO_DIR", "../scenarios")

    repo = runner._build_scenario_repo()

    assert isinstance(repo, LocalFsScenarioRepo)
    assert Path(repo.profile_dir) == (runner.ROOT / "server" / "../scenarios").resolve()


def test_qa_runner_builds_roll_request_for_public_pending_roll():
    request = runner._pending_resolution_request(
        "game-1",
        {
            "pendingConfirmation": None,
            "pendingRoll": {
                "id": "roll-1",
                "kind": "perceive",
                "title": "지력 판정이 필요합니다",
                "stat": "mind",
                "statLabel": "지력",
                "requiredRoll": 13,
            },
        },
    )

    assert request == (
        "roll",
        "/session/game-1/graph/roll",
        {"roll_id": "roll-1"},
        {
            "id": "roll-1",
            "kind": "perceive",
            "title": "지력 판정이 필요합니다",
            "stat": "mind",
            "statLabel": "지력",
            "requiredRoll": 13,
        },
    )


def test_qa_transcript_formats_public_pending_roll(tmp_path):
    transcript_path = tmp_path / "transcript.md"

    append_transcript_block(
        transcript_path,
        turn_no=1,
        kind="roll",
        pending={
            "id": "roll-1",
            "kind": "perceive",
            "title": "지력 판정이 필요합니다",
            "body": "자세히 살펴보려면 집중해야 합니다.",
            "stat": "mind",
            "statLabel": "지력",
            "requiredRoll": 13,
        },
    )

    text = transcript_path.read_text(encoding="utf-8")
    assert "**굴림 대기**: 지력 (13+ 필요)" in text
    assert "자세히 살펴보려면 집중해야 합니다." in text
