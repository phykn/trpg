"""Create the API and run the server. Both models must answer before it starts."""

import argparse
import os
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from src.api import router
from src.config import Settings, load_server_env, settings
from src.content.load import Loaded, load_story, story_folders
from src.content.validate import validate
from src.models.kev import KevClient
from src.models.qwen import QwenClient
from src.service import GameService
from src.store import SaveStore

SERVER_DIR = Path(__file__).resolve().parent


def load_stories(root: Path) -> dict[str, Loaded]:
    stories, problems = {}, []
    for folder in story_folders(root):
        loaded = load_story(folder)
        problems += [f"{folder.name}: {e}" for e in validate(loaded.story)]
        if loaded.story.id in stories:
            problems.append(f"{folder.name}: duplicate story id {loaded.story.id}")
        stories[loaded.story.id] = loaded
    if problems:
        raise SystemExit("invalid stories:\n" + "\n".join(problems))
    return stories


def build_app(*, service: GameService, basic_auth_user: str, basic_auth_pass: str,
              cors_origins: list[str], check_models: bool = True) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if check_models:
            await service.check_models()
        yield

    app = FastAPI(title="TRPG engine", version="1.0.0", lifespan=lifespan)
    app.add_middleware(CORSMiddleware, allow_origins=cors_origins, allow_methods=["GET", "POST", "OPTIONS"],
                       allow_headers=["Authorization", "Content-Type", "Accept"])
    app.state.basic_auth_user = basic_auth_user
    app.state.basic_auth_pass = basic_auth_pass
    app.state.service = service
    app.include_router(router)

    @app.get("/health")
    async def health():
        return {"ok": True, "mode": "engine"}

    return app


def local_settings() -> Settings:
    """Loopback defaults for `--local`; only the model URLs may come from the process environment."""
    return Settings(
        host="127.0.0.1", port=8000, basic_auth_user="local", basic_auth_pass="local",
        cors_origins=["http://localhost:8090", "http://127.0.0.1:8090"],
        scenario_dir=SERVER_DIR.parent / "scenarios", save_dir=SERVER_DIR.parent / "saves" / "engine",
        kev_base_url=os.environ.get("KEV_BASE_URL", "http://127.0.0.1:8081"), kev_min_confidence=0.5,
        kev_api_key=os.environ.get("KEV_API_KEY", ""),
        qwen_base_url=os.environ.get("QWEN_BASE_URL", "http://127.0.0.1:8082/v1"), qwen_model="auto",
        qwen_sampling=None,
    )


def create_app(local: bool = False) -> tuple[FastAPI, str, int]:
    if local:
        cfg = local_settings()
    else:
        load_server_env(SERVER_DIR)
        cfg = settings(SERVER_DIR)
    service = GameService(
        load_stories(cfg.scenario_dir),
        SaveStore(cfg.save_dir),
        KevClient(cfg.kev_base_url, min_confidence=cfg.kev_min_confidence, api_key=cfg.kev_api_key),
        QwenClient(cfg.qwen_base_url, model=cfg.qwen_model, sampling=cfg.qwen_sampling),
    )
    app = build_app(service=service, basic_auth_user=cfg.basic_auth_user, basic_auth_pass=cfg.basic_auth_pass,
                    cors_origins=cfg.cors_origins)
    return app, cfg.host, cfg.port


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--local", action="store_true", help="loopback defaults on 127.0.0.1:8000, no dotenv")
    app, host, port = create_app(local=parser.parse_args().local)
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()
