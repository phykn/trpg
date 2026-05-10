"""FastAPI dependency helpers for app-state singletons."""

from fastapi import HTTPException, Request

from src.llm.client import LLMClient
from src.db.repo import GraphRepo, ScenarioRepo


def get_scenario_repo(request: Request) -> ScenarioRepo:
    return request.app.state.scenario_repo


def get_graph_repo(request: Request) -> GraphRepo:
    repo = getattr(request.app.state, "graph_repo", None)
    if repo is None:
        raise HTTPException(status_code=503, detail="graph repo not configured")
    return repo


def get_llm(request: Request) -> LLMClient:
    return request.app.state.llm
