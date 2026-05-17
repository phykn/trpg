from src.db.factory import build_graph_repo, build_scenario_repo
from src.db.graph.local_fs import LocalFsGraphRepo
from src.db.graph.supabase import SupabaseGraphRepo
from src.db.scenario.local_fs import LocalFsScenarioRepo
from src.db.scenario.supabase import SupabaseStorageScenarioRepo


def test_build_scenario_repo_can_use_local_fs_for_dev(monkeypatch, tmp_path):
    monkeypatch.setenv("SCENARIO_REPO", "local")
    monkeypatch.setenv("SCENARIO_DIR", str(tmp_path))

    repo = build_scenario_repo()

    assert isinstance(repo, LocalFsScenarioRepo)
    assert repo.profile_dir == str(tmp_path)


def test_build_scenario_repo_defaults_to_supabase(monkeypatch):
    monkeypatch.delenv("SCENARIO_REPO", raising=False)
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_KEY", "secret")
    monkeypatch.setenv("SUPABASE_SCENARIO_BUCKET", "scenarios")

    repo = build_scenario_repo()

    assert isinstance(repo, SupabaseStorageScenarioRepo)


def test_build_graph_repo_can_use_local_fs_for_dev(monkeypatch, tmp_path):
    monkeypatch.setenv("GRAPH_REPO", "local")
    monkeypatch.setenv("GRAPH_SAVE_DIR", str(tmp_path))

    repo = build_graph_repo()

    assert isinstance(repo, LocalFsGraphRepo)
    assert repo.saves_dir == str(tmp_path)


def test_build_graph_repo_defaults_to_supabase(monkeypatch):
    monkeypatch.delenv("GRAPH_REPO", raising=False)
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_KEY", "secret")

    repo = build_graph_repo()

    assert isinstance(repo, SupabaseGraphRepo)
