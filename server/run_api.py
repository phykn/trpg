import argparse
import os
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from src.api import add_error_handlers, router
from src.config import Settings, load_server_env, settings
from src.service import GameService
from src.story.check import load_stories
from src.story.load import StoryError

SERVER_DIR = Path(__file__).resolve().parent


def build_app(cfg, service):
    app = FastAPI(title="TRPG")
    app.state.service = service
    app.state.basic_auth_user = cfg.basic_auth_user
    app.state.basic_auth_pass = cfg.basic_auth_pass
    app.add_middleware(CORSMiddleware, allow_origins=cfg.cors_origins, allow_methods=["GET", "POST", "OPTIONS"],
                       allow_headers=["Authorization", "Content-Type", "Accept"])

    @app.get("/health")
    async def health():
        return {"ok": True}

    app.include_router(router)
    add_error_handlers(app)
    return app


def local_settings():
    """Under `--local` only the models and their URLs may come from the process environment."""
    return Settings(
        host="127.0.0.1", port=8000, basic_auth_user="local", basic_auth_pass="local",
        cors_origins=["http://localhost:8090", "http://127.0.0.1:8090"],
        scenario_dir=SERVER_DIR.parent / "scenarios", save_dir=SERVER_DIR.parent / "saves" / "game",
        decision_model=os.environ.get("DECISION_MODEL", "kanana"),
        decision_base_url=os.environ.get("DECISION_BASE_URL", "http://127.0.0.1:8081"),
        llm_model=os.environ.get("LLM_MODEL", "gemma4"),
        llm_base_url=os.environ.get("LLM_BASE_URL", "http://127.0.0.1:8082/v1"),
    )


def main():
    parser = argparse.ArgumentParser(description="Run the TRPG API.")
    parser.add_argument("--local", action="store_true", help="loopback defaults on 127.0.0.1:8000, no dotenv")
    if parser.parse_args().local:
        cfg = local_settings()
    else:
        load_server_env(SERVER_DIR)
        cfg = settings(SERVER_DIR)
    try:
        stories = load_stories(cfg.scenario_dir)
    except StoryError as exc:
        raise SystemExit(f"invalid story: {exc}") from None
    uvicorn.run(build_app(cfg, GameService(stories, cfg.save_dir, None)), host=cfg.host, port=cfg.port)


if __name__ == "__main__":
    main()
