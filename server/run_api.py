import os
from pathlib import Path

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.routes import router
from src.llm import LLMClient
from src.db.factory import build_graph_repo, build_scenario_repo
from src.db.repo import GraphRepo, ScenarioRepo

REPO_ROOT = Path(__file__).resolve().parent.parent
SERVER_DIR = Path(__file__).resolve().parent

_TRUE_ENV_VALUES = {"1", "true", "yes", "on"}
_FALSE_ENV_VALUES = {"", "0", "false", "no", "off"}


def _load_env() -> None:
    """Load .env.<APP_ENV> if present (default 'dev'). Missing file is OK — OS env vars (e.g. Render dashboard) suffice; per-key fail-fast still happens at downstream os.environ[...] reads."""
    app_env = os.environ.get("APP_ENV", "dev")
    env_path = SERVER_DIR / f".env.{app_env}"
    if env_path.is_file():
        load_dotenv(env_path)
    _normalize_local_paths()


def _normalize_local_paths() -> None:
    for key in ("SCENARIO_DIR", "GRAPH_SAVE_DIR"):
        value = os.environ.get(key)
        if not value:
            continue
        path = Path(value)
        if path.is_absolute():
            continue
        os.environ[key] = str((SERVER_DIR / path).resolve())


def _env_flag(name: str) -> bool:
    value = os.environ.get(name)
    if value is None:
        return False
    normalized = value.strip().lower()
    if normalized in _TRUE_ENV_VALUES:
        return True
    if normalized in _FALSE_ENV_VALUES:
        return False
    raise ValueError(f"{name} must be one of 1/0, true/false, yes/no, on/off")


def build_app(
    llm: LLMClient,
    basic_auth_user: str,
    basic_auth_pass: str,
    scenario_repo: ScenarioRepo,
    cors_origins: list[str],
    graph_repo: GraphRepo | None = None,
) -> FastAPI:
    app = FastAPI(title="TRPG Server API")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=[
            "Authorization",
            "Content-Type",
            "Accept",
            "bypass-tunnel-reminder",
        ],
    )
    app.state.llm = llm
    app.state.basic_auth_user = basic_auth_user
    app.state.basic_auth_pass = basic_auth_pass
    app.state.scenario_repo = scenario_repo
    app.state.graph_repo = graph_repo
    app.include_router(router)
    return app


def create_app() -> FastAPI:
    _load_env()

    basic_auth_user = os.environ["BASIC_AUTH_USER"]
    basic_auth_pass = os.environ["BASIC_AUTH_PASS"]
    cors_origins = [
        s.strip() for s in os.environ["CORS_ORIGINS"].split(",") if s.strip()
    ]

    scenario_repo = build_scenario_repo()
    graph_repo = build_graph_repo()

    llm = LLMClient.from_env(log_dir=REPO_ROOT / "logs")
    return build_app(
        llm=llm,
        basic_auth_user=basic_auth_user,
        basic_auth_pass=basic_auth_pass,
        scenario_repo=scenario_repo,
        cors_origins=cors_origins,
        graph_repo=graph_repo,
    )


def main() -> None:
    _load_env()
    host = os.environ["HOST"]
    port = int(os.environ["PORT"])
    reload = _env_flag("RELOAD")

    if reload:
        uvicorn.run(
            "run_api:create_app",
            host=host,
            port=port,
            factory=True,
            reload=True,
            reload_dirs=[str(SERVER_DIR)],
            reload_includes=["*.py", "*.toml", "*.md"],
        )
    else:
        uvicorn.run(create_app(), host=host, port=port)


if __name__ == "__main__":
    main()
