import argparse
import asyncio

import uvicorn
from src.ai import ModelUnavailable
from src.ai.decision import DecisionClient
from src.ai.interpret import Interpreter
from src.ai.llm import LLMClient
from src.ai.narrate import Narrator
from src.api import build_app
from src.config import env_settings, local_settings
from src.game.service import GameService
from src.story.check import load_stories
from src.story.load import StoryError


def main():
    parser = argparse.ArgumentParser(description="Run the TRPG API.")
    parser.add_argument("--local", action="store_true", help="loopback defaults on 127.0.0.1:8000, no dotenv")
    try:
        cfg = local_settings() if parser.parse_args().local else env_settings()
    except ValueError as exc:
        raise SystemExit(f"settings: {exc}") from None
    try:
        stories = load_stories(cfg.scenario_dir)
    except StoryError as exc:
        raise SystemExit(f"invalid story: {exc}") from None
    try:
        decision, llm = asyncio.run(check_models(cfg))
    except (ValueError, ModelUnavailable) as exc:
        raise SystemExit(f"models: {exc}") from None
    service = GameService(stories, cfg.save_dir, Interpreter(decision), Narrator(llm, decision))
    uvicorn.run(build_app(cfg, service), host=cfg.host, port=cfg.port)


async def check_models(cfg):
    decision = DecisionClient(cfg.decision_base_url, cfg.decision_model)
    llm = LLMClient(cfg.llm_base_url, cfg.llm_model)
    await decision.check()
    await llm.check()
    return decision, llm


if __name__ == "__main__":
    main()
