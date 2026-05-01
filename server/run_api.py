import os
from pathlib import Path

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.routes import router
from src.llm import LLMClient

REPO_ROOT = Path(__file__).resolve().parent.parent


def build_app(
    llm: LLMClient,
    basic_auth_user: str,
    basic_auth_pass: str,
    saves_dir: str,
    profile_dir: str,
    cors_origins: list[str],
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
    app.state.saves_dir = saves_dir
    app.state.profile_dir = profile_dir
    app.include_router(router)
    return app


def create_app() -> FastAPI:
    load_dotenv()

    base_url = os.environ["BASE_URL"]
    basic_auth_user = os.environ["BASIC_AUTH_USER"]
    basic_auth_pass = os.environ["BASIC_AUTH_PASS"]
    saves_dir = os.environ["SAVES_DIR"]
    profile_dir = os.environ["PROFILE_DIR"]
    cors_origins = [
        s.strip() for s in os.environ["CORS_ORIGINS"].split(",") if s.strip()
    ]

    llm = LLMClient(
        base_url=base_url,
        model="local",
        api_key="none",
        log_dir=REPO_ROOT / "logs",
    )
    return build_app(
        llm=llm,
        basic_auth_user=basic_auth_user,
        basic_auth_pass=basic_auth_pass,
        saves_dir=saves_dir,
        profile_dir=profile_dir,
        cors_origins=cors_origins,
    )


def main() -> None:
    load_dotenv()
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
