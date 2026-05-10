from pathlib import Path

from agency import run_qa
from agency.qa.harness import runner
from src.db.local_fs import LocalFsScenarioRepo


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
