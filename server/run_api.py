"""Create the API and run the local development server."""

import argparse
import os
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from src.api import router
from src.content import load_story
from src.env import load_server_env
from src.service import GameService
from src.store import SaveStore

SERVER_DIR = Path(__file__).resolve().parent
REPO_ROOT = SERVER_DIR.parent


def build_app(
    *,
    save_dir: Path,
    basic_auth_user: str,
    basic_auth_pass: str,
    cors_origins: list[str],
) -> FastAPI:
    story = load_story(REPO_ROOT / "scenarios/harbor/adventure.json")
    app = FastAPI(title="Harbor Adventure API", version="1.0.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "Accept"],
    )
    app.state.basic_auth_user = basic_auth_user
    app.state.basic_auth_pass = basic_auth_pass
    app.state.adventure = GameService(story, SaveStore(save_dir))
    app.include_router(router)

    @app.get("/health")
    async def health():
        return {"status": "ok", "mode": "adventure", "content_version": story.version}

    return app


def create_local_app() -> FastAPI:
    return build_app(
        save_dir=REPO_ROOT / "saves/adventure",
        basic_auth_user="local",
        basic_auth_pass="local",
        cors_origins=["http://localhost:8081", "http://127.0.0.1:8081"],
    )


def create_app() -> FastAPI:
    load_server_env(SERVER_DIR)
    save_dir = Path(os.environ["ADVENTURE_SAVE_DIR"])
    if not save_dir.is_absolute():
        save_dir = (SERVER_DIR / save_dir).resolve()
    return build_app(
        save_dir=save_dir,
        basic_auth_user=os.environ["BASIC_AUTH_USER"],
        basic_auth_pass=os.environ["BASIC_AUTH_PASS"],
        cors_origins=[
            origin.strip()
            for origin in os.environ["CORS_ORIGINS"].split(",")
            if origin.strip()
        ],
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--local", action="store_true", help="Run on 127.0.0.1:8000")
    args = parser.parse_args()
    app = create_local_app() if args.local else create_app()
    host = "127.0.0.1" if args.local else os.environ["HOST"]
    port = 8000 if args.local else int(os.environ["PORT"])
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()
