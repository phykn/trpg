"""FastAPI dependency helpers — short aliases for app-state singletons and
the load-or-404 pattern that every game-scoped route needs."""

from fastapi import Depends, HTTPException, Request

from src.game.domain.state import GameState
from src.llm.client import LLMClient
from src.db.repo import GraphRepo, SaveRepo, ScenarioRepo


def get_save_repo(request: Request) -> SaveRepo:
    return request.app.state.save_repo


def get_scenario_repo(request: Request) -> ScenarioRepo:
    return request.app.state.scenario_repo


def get_graph_repo(request: Request) -> GraphRepo:
    repo = getattr(request.app.state, "graph_repo", None)
    if repo is None:
        raise HTTPException(status_code=503, detail="graph repo not configured")
    return repo


def get_llm(request: Request) -> LLMClient:
    return request.app.state.llm


async def get_state(
    game_id: str,
    save_repo: SaveRepo = Depends(get_save_repo),
) -> GameState:
    try:
        return await save_repo.load_game(game_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="game not found")
