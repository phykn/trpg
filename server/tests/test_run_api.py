import run_api
import pytest
from httpx import ASGITransport, AsyncClient


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
    assert "bypass-tunnel-reminder" in response.headers[
        "access-control-allow-headers"
    ].lower()
