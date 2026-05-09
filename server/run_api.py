import os
from pathlib import Path

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.routes import router
from src.llm import LLMClient
from src.db.factory import build_graph_repo, build_save_repo, build_scenario_repo
from src.db.repo import GraphRepo, SaveRepo, ScenarioRepo

REPO_ROOT = Path(__file__).resolve().parent.parent
SERVER_DIR = Path(__file__).resolve().parent


def _load_env() -> None:
    """Load .env.<APP_ENV> if present (default 'dev'). Missing file is OK — OS env vars (e.g. Render dashboard) suffice; per-key fail-fast still happens at downstream os.environ[...] reads."""
    app_env = os.environ.get("APP_ENV", "dev")
    env_path = SERVER_DIR / f".env.{app_env}"
    if env_path.is_file():
        load_dotenv(env_path)


def build_app(
    llm: LLMClient,
    basic_auth_user: str,
    basic_auth_pass: str,
    save_repo: SaveRepo,
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
        allow_headers=["Authorization", "Content-Type", "Accept"],
    )
    app.state.llm = llm
    app.state.basic_auth_user = basic_auth_user
    app.state.basic_auth_pass = basic_auth_pass
    app.state.save_repo = save_repo
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

    # Build repo adapters via factory — APP_ENV=release fails fast here
    # because the Supabase stubs raise at __init__ until Phase 2.
    save_repo = build_save_repo()
    scenario_repo = build_scenario_repo()
    graph_repo = build_graph_repo()

    llm = LLMClient.from_env(log_dir=REPO_ROOT / "logs")
    return build_app(
        llm=llm,
        basic_auth_user=basic_auth_user,
        basic_auth_pass=basic_auth_pass,
        save_repo=save_repo,
        scenario_repo=scenario_repo,
        cors_origins=cors_origins,
        graph_repo=graph_repo,
    )


def main() -> None:
    _load_env()
    host = os.environ["HOST"]
    port = int(os.environ["PORT"])
    reload = bool(os.environ.get("RELOAD"))

    if reload:
        uvicorn.run(
            "run_api:create_app",
            host=host,
            port=port,
            factory=True,
            reload=True,
            reload_dirs=[str(Path(__file__).resolve().parent / "src")],
        )
    else:
        uvicorn.run(create_app(), host=host, port=port)


if __name__ == "__main__":
    main()
