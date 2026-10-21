import argparse
import os
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from src.api import add_error_handlers, router
from src.config import Settings, load_server_env, settings
from src.interpret import Interpreter
from src.models.decision import DecisionClient
from src.models.llm import LLMClient
from src.narrate import Narrator
from src.service import GameService
from src.story.load import StoryError
from src.story.validate import load_all

SERVER_DIR = Path(__file__).resolve().parent


def load_stories(root: Path):
    try:
        return load_all(root)
    except StoryError as e:
        raise SystemExit(f"invalid story: {e}") from None


async def check_models(decision: DecisionClient, llm: LLMClient) -> None:
    """The models run outside this repo, so startup only checks them (engine.md 8)."""
    await decision.check()
    await llm.resolve_model()


def build_app(*, service: GameService, basic_auth_user: str, basic_auth_pass: str,
              cors_origins: list[str], models: tuple[DecisionClient, LLMClient] | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if models is not None:
            await check_models(*models)
        yield

    app = FastAPI(title="TRPG engine", version="1.0.0", lifespan=lifespan)
    app.add_middleware(CORSMiddleware, allow_origins=cors_origins, allow_methods=["GET", "POST", "OPTIONS"],
                       allow_headers=["Authorization", "Content-Type", "Accept"])
    app.state.basic_auth_user = basic_auth_user
    app.state.basic_auth_pass = basic_auth_pass
    app.state.service = service
    app.include_router(router)
    add_error_handlers(app)

    @app.get("/health")
    async def health():
        return {"ok": True, "mode": "engine"}

    return app


def local_settings() -> Settings:
    """Under `--local` only the models and their URLs may come from the process environment."""
    return Settings(
        host="127.0.0.1", port=8000, basic_auth_user="local", basic_auth_pass="local",
        cors_origins=["http://localhost:8090", "http://127.0.0.1:8090"],
        scenario_dir=SERVER_DIR.parent / "scenarios", save_dir=SERVER_DIR.parent / "saves" / "engine",
        decision_model=os.environ.get("DECISION_MODEL", "malkuth"),
        decision_base_url=os.environ.get("DECISION_BASE_URL", "http://127.0.0.1:8081"),
        decision_min_confidence=None, decision_api_key=os.environ.get("DECISION_API_KEY", ""),
        llm_model=os.environ.get("LLM_MODEL", "gemma4"),
        llm_base_url=os.environ.get("LLM_BASE_URL", "http://127.0.0.1:8082/v1"), llm_sampling=None,
    )


def create_app(local: bool = False) -> tuple[FastAPI, str, int]:
    if local:
        cfg = local_settings()
    else:
        load_server_env(SERVER_DIR)
        cfg = settings(SERVER_DIR)
    decision = DecisionClient(cfg.decision_base_url, model=cfg.decision_model,
                              min_confidence=cfg.decision_min_confidence, api_key=cfg.decision_api_key)
    llm = LLMClient(cfg.llm_base_url, model=cfg.llm_model, sampling=cfg.llm_sampling)
    service = GameService(load_stories(cfg.scenario_dir), cfg.save_dir, Interpreter(decision, llm),
                          Narrator(llm, decision))
    app = build_app(service=service, basic_auth_user=cfg.basic_auth_user, basic_auth_pass=cfg.basic_auth_pass,
                    cors_origins=cfg.cors_origins, models=(decision, llm))
    return app, cfg.host, cfg.port


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the TRPG engine API. Both models must answer before it starts.")
    parser.add_argument("--local", action="store_true", help="loopback defaults on 127.0.0.1:8000, no dotenv")
    app, host, port = create_app(local=parser.parse_args().local)
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()
