import json
import shutil

import pytest
from conftest import TEMPLATE, FakeKev, FakeQwen
from fastapi.testclient import TestClient
from run_api import build_app, load_stories
from src.models.kev import ModelUnavailable
from src.service import GameService
from src.store import SaveStore

AUTH = ("u", "p")


@pytest.fixture
def stories(tmp_path):
    root = tmp_path / "scenarios"
    shutil.copytree(TEMPLATE, root / "lighthouse")
    return load_stories(root)


def client(stories, tmp_path, kev=None, qwen=None, check=True):
    service = GameService(stories, SaveStore(tmp_path / "saves"), kev or FakeKev(), qwen or FakeQwen())
    app = build_app(service=service, basic_auth_user="u", basic_auth_pass="p", cors_origins=[], check_models=check)
    return TestClient(app)


def test_health_is_public_and_the_rest_needs_auth(stories, tmp_path):
    with client(stories, tmp_path) as c:
        assert c.get("/health").json() == {"ok": True, "mode": "engine"}
        assert c.get("/catalog").status_code == 401
        assert c.get("/catalog", auth=("u", "x")).status_code == 401
        assert [s["id"] for s in c.get("/catalog", auth=AUTH).json()] == ["lighthouse"]


def test_start_act_and_stream(stories, tmp_path):
    with client(stories, tmp_path) as c:
        view = c.post("/games", json={"story": "lighthouse"}, auth=AUTH).json()
        gid = view["game_id"]
        lines = c.get(f"/games/{gid}/turns/0/narration", auth=AUTH).text.strip().splitlines()
        events = [json.loads(line) for line in lines]
        assert events[0]["type"] == "delta" and events[-1]["type"] == "done"
        r = c.post(f"/games/{gid}/act", json={"revision": 0, "request_id": "req_00001", "action_id": "move:base"},
                   auth=AUTH)
        assert r.status_code == 200 and r.json()["kind"] == "turn"
        assert c.get(f"/games/{gid}", auth=AUTH).json()["revision"] == 1
        stale = c.post(f"/games/{gid}/act", json={"revision": 0, "request_id": "req_00002", "action_id": "move:square"},
                       auth=AUTH)
        assert stale.status_code == 409


@pytest.mark.parametrize("body", [
    {"revision": 0, "request_id": "req_00003"},
    {"revision": 0, "request_id": "req_00003", "text": "  "},
    {"revision": 0, "request_id": "req_00003", "text": "가", "action_id": "move:base"},
    {"revision": 0, "request_id": "bad id!", "text": "가"},
    {"revision": 0, "request_id": "req_00003", "text": "가" * 201},
])
def test_bad_requests(stories, tmp_path, body):
    with client(stories, tmp_path) as c:
        gid = c.post("/games", json={"story": "lighthouse"}, auth=AUTH).json()["game_id"]
        assert c.post(f"/games/{gid}/act", json=body, auth=AUTH).status_code == 422


def test_errors_map_to_codes(stories, tmp_path):
    with client(stories, tmp_path, kev=FakeKev(error=ModelUnavailable("down")), check=False) as c:
        assert c.get("/games/g_" + "1" * 32, auth=AUTH).status_code == 404
        assert c.get("/games/nope", auth=AUTH).status_code == 404
        assert c.post("/games", json={"story": "nope"}, auth=AUTH).status_code == 422
        gid = c.post("/games", json={"story": "lighthouse"}, auth=AUTH).json()["game_id"]
        r = c.post(f"/games/{gid}/act", json={"revision": 0, "request_id": "req_00004", "text": "간다"}, auth=AUTH)
        assert r.status_code == 503


def test_startup_requires_both_models(stories, tmp_path):
    with pytest.raises(ModelUnavailable), client(stories, tmp_path, qwen=FakeQwen(error=ModelUnavailable("x"))):
        pass


def test_invalid_story_stops_startup(tmp_path):
    root = tmp_path / "scenarios"
    shutil.copytree(TEMPLATE, root / "broken")
    data = json.loads((root / "broken" / "scenario.json").read_text(encoding="utf-8"))
    data["obstacles"]["door"]["solutions"] = data["obstacles"]["door"]["solutions"][:1]
    (root / "broken" / "scenario.json").write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(SystemExit, match="needs 2 or more solutions"):
        load_stories(root)
