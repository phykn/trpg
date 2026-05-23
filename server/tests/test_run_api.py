import run_api
import pytest
from httpx import ASGITransport, AsyncClient
from src.env import load_server_env


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
