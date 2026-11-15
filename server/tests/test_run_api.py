from dataclasses import replace

import pytest
import run_api
from fastapi.testclient import TestClient
from run_api import build_app, local_settings


def test_health_answers_without_auth():
    response = TestClient(build_app(local_settings())).get("/health")
    assert response.status_code == 200
    assert response.json() == {"ok": True}


def test_a_broken_story_stops_startup(tmp_path, monkeypatch):
    (tmp_path / "bad").mkdir()
    (tmp_path / "bad" / "story.yaml").write_text("머리: {}", encoding="utf-8")
    monkeypatch.setattr("sys.argv", ["run_api.py", "--local"])
    monkeypatch.setattr(run_api, "local_settings", lambda: replace(local_settings(), scenario_dir=tmp_path))
    monkeypatch.setattr(run_api.uvicorn, "run", lambda *a, **k: pytest.fail("the server started"))
    with pytest.raises(SystemExit, match="invalid story"):
        run_api.main()
