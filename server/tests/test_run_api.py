from dataclasses import replace

import pytest
import run_api
from src.config import local_settings


def start(monkeypatch, **changes):
    monkeypatch.setattr("sys.argv", ["run_api.py", "--local"])
    monkeypatch.setattr(run_api, "local_settings", lambda: replace(local_settings(), **changes))
    monkeypatch.setattr(run_api.uvicorn, "run", lambda *_args, **_kw: pytest.fail("the server started"))
    run_api.main()


def test_a_broken_story_stops_startup(tmp_path, monkeypatch):
    (tmp_path / "bad").mkdir()
    (tmp_path / "bad" / "story.yaml").write_text("머리: {}", encoding="utf-8")
    with pytest.raises(SystemExit, match="invalid story"):
        start(monkeypatch, scenario_dir=tmp_path)


def test_local_takes_the_model_from_the_environment_and_refuses_an_unknown_one(monkeypatch):
    monkeypatch.setenv("DECISION_MODEL", "malkuth")
    with pytest.raises(SystemExit, match="malkuth"):
        start(monkeypatch)
