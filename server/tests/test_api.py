import asyncio
import json
import subprocess
import sys
from pathlib import Path

import pytest
import run_api
from httpx import ASGITransport, AsyncClient


def make_app(root):
    return run_api.build_app(
        save_dir=root,
        basic_auth_user="tester",
        basic_auth_pass="secret",
        cors_origins=["http://localhost:8081"],
    )


def client_for(app):
    return AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        auth=("tester", "secret"),
    )


async def start(client):
    response = await client.post(
        "/adventure/start", json={"name": "Tester", "role": "listener"}
    )
    assert response.status_code == 200, response.text
    return response.json()


def command(action, revision=0, request_id="request_0001"):
    return {"option_id": action, "revision": revision, "request_id": request_id}


@pytest.mark.asyncio
async def test_default_mode_auth_and_routes(tmp_path):
    app = make_app(tmp_path)
    async with client_for(app) as client:
        assert (await client.get("/health", auth=None)).json()["mode"] == "adventure"
        assert (await client.get("/adventure/catalog", auth=None)).status_code == 401
        catalog = (await client.get("/adventure/catalog")).json()
        assert len(catalog["roles"]) == 3
        assert (await client.post("/graph/init", json={})).status_code == 404
        preflight = await client.options(
            "/adventure/start",
            headers={
                "Origin": "http://localhost:8081",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "authorization,content-type",
            },
        )
        assert preflight.status_code == 200


@pytest.mark.asyncio
async def test_retry_and_stale_revision_cannot_duplicate_a_turn(tmp_path):
    async with client_for(make_app(tmp_path)) as client:
        view = await start(client)
        url = f"/adventure/{view['game_id']}/choose"
        body = command("move:tavern")
        first = await client.post(url, json=body)
        duplicate = await client.post(url, json=body)
        assert first.status_code == duplicate.status_code == 200
        assert first.json() == duplicate.json()
        assert duplicate.json()["revision"] == 1
        assert duplicate.json()["remaining"] == 23
        assert (
            await client.post(url, json=command("move:warehouse"))
        ).status_code == 409
        assert (
            await client.post(
                url, json=command("move:warehouse", request_id="another_0001")
            )
        ).status_code == 409


@pytest.mark.asyncio
async def test_concurrent_choices_serialize_whole_turn(tmp_path):
    app = make_app(tmp_path)
    async with client_for(app) as client:
        view = await start(client)
        url = f"/adventure/{view['game_id']}/choose"
        responses = await asyncio.gather(
            client.post(url, json=command("move:tavern")),
            client.post(url, json=command("move:warehouse", request_id="another_0001")),
        )
        assert sorted(r.status_code for r in responses) == [200, 409]
        saved = (await client.get(f"/adventure/{view['game_id']}")).json()
        assert saved["revision"] == 1
        assert saved["remaining"] == 23


@pytest.mark.asyncio
async def test_failed_atomic_replace_leaves_previous_snapshot_and_is_retryable(
    tmp_path, monkeypatch
):
    from src import store

    async with client_for(make_app(tmp_path)) as client:
        view = await start(client)
        path = tmp_path / f"{view['game_id']}.json"
        original = path.read_bytes()
        real_replace = store.os.replace

        def fail_replace(*args):
            raise OSError("simulated disk failure")

        monkeypatch.setattr(store.os, "replace", fail_replace)
        url = f"/adventure/{view['game_id']}/choose"
        body = command("move:warehouse")
        assert (await client.post(url, json=body)).status_code == 503
        assert path.read_bytes() == original
        assert not list(tmp_path.glob("*.tmp"))
        monkeypatch.setattr(store.os, "replace", real_replace)
        assert (await client.post(url, json=body)).json()["revision"] == 1


@pytest.mark.asyncio
async def test_combat_restore_and_idempotency_survive_runtime_restart(tmp_path):
    async with client_for(make_app(tmp_path)) as client:
        view = await start(client)
        url = f"/adventure/{view['game_id']}/choose"
        for index, action in enumerate(["move:prison", "guard.fight", "combat.listen"]):
            body = command(action, index, f"command_{index}")
            response = await client.post(url, json=body)
            assert response.status_code == 200, response.text
        before = response.json()
    async with client_for(make_app(tmp_path)) as client:
        restored = (await client.get(f"/adventure/{view['game_id']}")).json()
        assert restored == before
        assert restored["combat"]["understanding"] == 1
        assert "guard_fear" in [item["id"] for item in restored["knowledge"]]
        assert (await client.post(url, json=body)).json() == restored
        assert (
            await client.post(url, json=command("combat.mercy", 3))
        ).status_code == 422


@pytest.mark.asyncio
@pytest.mark.parametrize("field", ["content_version", "schema_version"])
async def test_incompatible_saves_are_rejected_without_overwriting(tmp_path, field):
    async with client_for(make_app(tmp_path)) as client:
        view = await start(client)
        path = tmp_path / f"{view['game_id']}.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        data[field] = 999
        path.write_text(json.dumps(data), encoding="utf-8")
        original = path.read_bytes()
        assert (await client.get(f"/adventure/{view['game_id']}")).status_code == 409
        assert path.read_bytes() == original


@pytest.mark.asyncio
async def test_invalid_inputs_and_remote_actions_do_not_change_state(tmp_path):
    async with client_for(make_app(tmp_path)) as client:
        for body in [
            {"name": " ", "role": "listener"},
            {"name": "T", "role": "unknown"},
            {"name": "T", "role": "listener", "seed": 42},
        ]:
            assert (await client.post("/adventure/start", json=body)).status_code == 422
        view = await start(client)
        response = await client.post(
            f"/adventure/{view['game_id']}/choose", json=command("ledger.take")
        )
        assert response.status_code == 422
        assert (await client.get(f"/adventure/{view['game_id']}")).json() == view
        assert (await client.get("/adventure/not-a-game")).status_code == 404


def test_start_and_play_in_a_fresh_process():
    script = """
import asyncio, tempfile
from pathlib import Path
from run_api import build_app
async def play():
    with tempfile.TemporaryDirectory() as directory:
        app = build_app(save_dir=Path(directory), basic_auth_user='u', basic_auth_pass='p', cors_origins=[])
        runtime = app.state.adventure
        view = await runtime.start('Tester', 'listener')
        for action in ['move:prison', 'guard.fight', 'combat.listen', 'combat.reassure', 'combat.mercy', 'sailor.rescue', 'move:square', 'escape']:
            view = await runtime.act(view.game_id, action, view.revision, 'request_' + str(view.revision))
        assert view.ending.id == 'quiet'
asyncio.run(play())
"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    assert result.returncode == 0, result.stderr
