import os

import run_api
from src.env import load_server_env


def test_load_server_env_layers_shared_then_app_env(monkeypatch, tmp_path):
    monkeypatch.delenv("APP_ENV", raising=False)
    monkeypatch.delenv("SHARED_ONLY", raising=False)
    monkeypatch.delenv("OVERRIDDEN", raising=False)
    monkeypatch.delenv("OS_ONLY", raising=False)
    monkeypatch.setenv("OS_ONLY", "from-os")

    (tmp_path / ".env.shared").write_text(
        "SHARED_ONLY=shared\nOVERRIDDEN=shared\nOS_ONLY=from-shared\n",
        encoding="utf-8",
    )
    (tmp_path / ".env.dev").write_text(
        "OVERRIDDEN=dev\nOS_ONLY=from-dev\n",
        encoding="utf-8",
    )

    load_server_env(tmp_path)

    assert os.environ["SHARED_ONLY"] == "shared"
    assert os.environ["OVERRIDDEN"] == "dev"
    assert os.environ["OS_ONLY"] == "from-os"


def test_local_startup_ignores_personal_connection_settings(monkeypatch, tmp_path):
    monkeypatch.setenv("BASIC_AUTH_USER", "different-user")
    monkeypatch.setenv("BASIC_AUTH_PASS", "different-pass")
    monkeypatch.setenv("ADVENTURE_SAVE_DIR", str(tmp_path))
    app = run_api.create_local_app()
    assert app.state.basic_auth_user == "local"
    assert app.state.basic_auth_pass == "local"
    assert app.state.adventure.store.root == run_api.REPO_ROOT / "saves/adventure"


def test_configured_save_path_is_relative_to_server_not_working_directory(
    monkeypatch, tmp_path
):
    monkeypatch.setattr(run_api, "SERVER_DIR", tmp_path / "server")
    monkeypatch.setenv("ADVENTURE_SAVE_DIR", "../saves")
    monkeypatch.setenv("BASIC_AUTH_USER", "tester")
    monkeypatch.setenv("BASIC_AUTH_PASS", "secret")
    monkeypatch.setenv("CORS_ORIGINS", "http://localhost:8081")
    monkeypatch.chdir(tmp_path)
    app = run_api.create_app()
    assert app.state.adventure.store.root == tmp_path / "saves"
