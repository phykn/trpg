"""FastAPI dependency helpers — short aliases for app-state singletons and
the load-or-404 pattern that every game-scoped route needs."""

from fastapi import Depends, HTTPException, Request

from ..domain.state import GameState
from ..llm.client import LLMClient
from ..persistence.store import load_game


def get_saves_dir(request: Request) -> str:
    return request.app.state.saves_dir


def get_profile_dir(request: Request) -> str:
    return request.app.state.profile_dir


def get_llm(request: Request) -> LLMClient:
    return request.app.state.llm


def get_state(
    game_id: str,
    saves_dir: str = Depends(get_saves_dir),
) -> GameState:
    try:
        return load_game(saves_dir, game_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="game not found")
