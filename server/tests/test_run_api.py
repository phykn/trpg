import run_api
import pytest
from httpx import ASGITransport, AsyncClient
from src.env import load_server_env


def _set_required_env(monkeypatch, *, reload_value: str | None) -> None:
    monkeypatch.setenv("HOST", "127.0.0.1")
    monkeypatch.setenv("PORT", "8123")
    if reload_value is None:
        monkeypatch.delenv("RELOAD", raising=False)
    else:
        monkeypatch.setenv("RELOAD", reload_value)


def test_main_enables_reload_and_watches_server_entrypoint(monkeypatch):
    _set_required_env(monkeypatch, reload_value="1")
    monkeypatch.setattr(run_api, "_load_env", lambda: None)
    calls = []
    monkeypatch.setattr(
        run_api.uvicorn, "run", lambda *args, **kwargs: calls.append((args, kwargs))
    )

    run_api.main()

    assert len(calls) == 1
    args, kwargs = calls[0]
    assert args == ("run_api:create_app",)
    assert kwargs["host"] == "127.0.0.1"
    assert kwargs["port"] == 8123
    assert kwargs["factory"] is True
    assert kwargs["reload"] is True
    assert str(run_api.SERVER_DIR) in kwargs["reload_dirs"]
    assert kwargs["reload_includes"] == ["*.py", "*.toml", "*.md"]


def test_main_treats_reload_zero_as_disabled(monkeypatch):
    _set_required_env(monkeypatch, reload_value="0")
    monkeypatch.setattr(run_api, "_load_env", lambda: None)
    monkeypatch.setattr(run_api, "create_app", lambda: "app")
    calls = []
    monkeypatch.setattr(
        run_api.uvicorn, "run", lambda *args, **kwargs: calls.append((args, kwargs))
    )

    run_api.main()

    assert len(calls) == 1
    args, kwargs = calls[0]
    assert args == ("app",)
    assert kwargs == {"host": "127.0.0.1", "port": 8123}


def test_load_env_normalizes_local_repo_paths(monkeypatch):
    monkeypatch.setenv("SCENARIO_DIR", "../scenarios")
    monkeypatch.setenv("GRAPH_SAVE_DIR", "../qa_test/dev_graph_saves")

    run_api._normalize_local_paths()

    assert run_api.os.environ["SCENARIO_DIR"] == str(
        (run_api.SERVER_DIR / "../scenarios").resolve()
    )
    assert run_api.os.environ["GRAPH_SAVE_DIR"] == str(
        (run_api.SERVER_DIR / "../qa_test/dev_graph_saves").resolve()
    )


def test_load_env_leaves_absolute_local_repo_paths(monkeypatch, tmp_path):
    scenario_dir = tmp_path / "scenarios"
    graph_dir = tmp_path / "saves"
    monkeypatch.setenv("SCENARIO_DIR", str(scenario_dir))
    monkeypatch.setenv("GRAPH_SAVE_DIR", str(graph_dir))

    run_api._normalize_local_paths()

    assert run_api.os.environ["SCENARIO_DIR"] == str(scenario_dir)
    assert run_api.os.environ["GRAPH_SAVE_DIR"] == str(graph_dir)


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

    assert run_api.os.environ["SHARED_ONLY"] == "shared"
    assert run_api.os.environ["OVERRIDDEN"] == "dev"
    assert run_api.os.environ["OS_ONLY"] == "from-os"


@pytest.mark.asyncio
async def test_build_app_allows_localtunnel_bypass_cors_header():
    app = run_api.build_app(
        llm=object(),
        basic_auth_user="tester",
        basic_auth_pass="secret",
        scenario_repo=object(),
        cors_origins=["https://trpg.example.test"],
    )

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.options(
            "/profiles",
            headers={
                "Origin": "https://trpg.example.test",
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": (
                    "authorization,bypass-tunnel-reminder"
                ),
            },
        )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == (
        "https://trpg.example.test"
    )
    assert (
        "bypass-tunnel-reminder"
        in response.headers["access-control-allow-headers"].lower()
    )
