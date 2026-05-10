"""Graph session REST routes."""

import asyncio

from fastapi import APIRouter, Depends, HTTPException

from src.db.repo import GraphRepo, ScenarioRepo
from src.game.domain.errors import (
    LLMUnavailable,
    ProfileMalformed,
    ProfileNotFound,
    RaceNotFound,
)
from src.game.flow.init_graph import init_graph_game
from src.game.runtime.confirmation import (
    GraphConfirmationActive,
    GraphConfirmationError,
    GraphConfirmationExpected,
    run_graph_action_request,
    run_graph_confirm,
)
from src.game.runtime.input import GraphInputError, run_graph_input_turn
from src.game.runtime.intro import (
    run_graph_initial_fallback_narration,
    run_graph_initial_narration,
)
from src.game.runtime.level_up import GraphLevelUpError, run_graph_level_up
from src.game.runtime.load import load_runtime_state
from src.game.runtime.state import GameRuntimeState
from src.game.runtime.turn import GraphActionTurnError
from src.llm.client import LLMClient, set_think_override
from src.wire.graph_to_front import graph_to_front_state

from ..deps import get_graph_repo, get_llm, get_scenario_repo
from ..schema import (
    ConfirmRequest,
    GraphActionResponse,
    GraphInputRequest,
    GraphLevelUpRequest,
    GraphTurnRequest,
    InitRequest,
    InitResponse,
)

router = APIRouter()

_GRAPH_INIT_NARRATION_TIMEOUT_SECONDS = 6.0


@router.post("/session/graph/init", response_model=InitResponse)
async def session_graph_init(
    body: InitRequest,
    llm: LLMClient = Depends(get_llm),
    graph_repo: GraphRepo = Depends(get_graph_repo),
    scenario_repo: ScenarioRepo = Depends(get_scenario_repo),
) -> InitResponse:
    try:
        bundle = await init_graph_game(
            body.profile, body.player, graph_repo, scenario_repo, locale=body.locale
        )
    except ProfileNotFound as e:
        raise HTTPException(status_code=422, detail=f"profile not found: {e}")
    except RaceNotFound as e:
        raise HTTPException(status_code=422, detail=f"race not found: {e}")
    except ProfileMalformed as e:
        raise HTTPException(status_code=422, detail=f"profile malformed: {e}")
    runtime = GameRuntimeState(graph=bundle.graph, progress=bundle.progress)
    try:
        runtime = await asyncio.wait_for(
            run_graph_initial_narration(llm, graph_repo, runtime),
            timeout=_GRAPH_INIT_NARRATION_TIMEOUT_SECONDS,
        )
    except (LLMUnavailable, OSError, TimeoutError):
        runtime = await run_graph_initial_fallback_narration(graph_repo, runtime)
    return InitResponse(
        game_id=bundle.progress.game_id,
        state=graph_to_front_state(runtime).model_dump(mode="json", by_alias=True),
    )


@router.get("/session/{game_id}/graph/state", response_model=InitResponse)
async def get_graph_state_route(
    game_id: str,
    graph_repo: GraphRepo = Depends(get_graph_repo),
) -> InitResponse:
    try:
        runtime = await load_runtime_state(graph_repo, game_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="game not found")
    return InitResponse(
        game_id=game_id,
        state=graph_to_front_state(runtime).model_dump(mode="json", by_alias=True),
    )


@router.post("/session/{game_id}/graph/turn", response_model=GraphActionResponse)
async def session_graph_turn(
    game_id: str,
    body: GraphTurnRequest,
    llm: LLMClient = Depends(get_llm),
    graph_repo: GraphRepo = Depends(get_graph_repo),
) -> GraphActionResponse:
    try:
        result = await run_graph_action_request(
            graph_repo,
            game_id,
            body.action,
            llm=llm,
        )
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="game not found")
    except GraphConfirmationActive as e:
        raise HTTPException(status_code=409, detail=str(e))
    except GraphConfirmationError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except GraphActionTurnError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return GraphActionResponse(
        game_id=game_id,
        state=result.front_state.model_dump(mode="json", by_alias=True),
        status=result.status,
        message=result.message,
    )


@router.post("/session/{game_id}/graph/confirm", response_model=GraphActionResponse)
async def session_graph_confirm(
    game_id: str,
    body: ConfirmRequest,
    llm: LLMClient = Depends(get_llm),
    graph_repo: GraphRepo = Depends(get_graph_repo),
) -> GraphActionResponse:
    try:
        result = await run_graph_confirm(
            graph_repo,
            game_id,
            body.confirmation_id,
            body.decision,
            llm=llm,
        )
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="game not found")
    except GraphConfirmationExpected as e:
        raise HTTPException(status_code=422, detail=str(e))
    except GraphConfirmationError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return GraphActionResponse(
        game_id=game_id,
        state=result.front_state.model_dump(mode="json", by_alias=True),
        status=result.status,
        message=result.message,
    )


@router.post("/session/{game_id}/graph/input", response_model=GraphActionResponse)
async def session_graph_input(
    game_id: str,
    body: GraphInputRequest,
    llm: LLMClient = Depends(get_llm),
    graph_repo: GraphRepo = Depends(get_graph_repo),
) -> GraphActionResponse:
    try:
        result = await run_graph_input_turn(
            llm,
            graph_repo,
            game_id,
            body.player_input,
        )
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="game not found")
    except GraphConfirmationActive as e:
        raise HTTPException(status_code=409, detail=str(e))
    except (GraphInputError, GraphConfirmationError, GraphActionTurnError) as e:
        raise HTTPException(status_code=422, detail=str(e))
    return GraphActionResponse(
        game_id=game_id,
        state=result.front_state.model_dump(mode="json", by_alias=True),
        status=result.status,
        message=result.message,
    )


@router.post("/session/{game_id}/graph/level_up", response_model=GraphActionResponse)
async def session_graph_level_up(
    game_id: str,
    body: GraphLevelUpRequest,
    graph_repo: GraphRepo = Depends(get_graph_repo),
) -> GraphActionResponse:
    set_think_override(body.think)
    try:
        result = await run_graph_level_up(
            graph_repo,
            game_id,
            stat_up=body.stat_up,
            skill_id=body.skill_id,
        )
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="game not found")
    except GraphLevelUpError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return GraphActionResponse(
        game_id=game_id,
        state=result.front_state.model_dump(mode="json", by_alias=True),
        status=None,
        message=None,
    )
