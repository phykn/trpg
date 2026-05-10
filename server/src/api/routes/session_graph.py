"""Graph session REST routes."""

from fastapi import APIRouter, Depends, HTTPException

from src.db.repo import GraphRepo, ScenarioRepo
from src.game.domain.errors import (
    ProfileMalformed,
    ProfileNotFound,
    RaceNotFound,
)
from src.game.runtime.confirmation import (
    GraphConfirmationActive,
    GraphConfirmationError,
    GraphConfirmationExpected,
    run_graph_action_request,
    run_graph_confirm,
)
from src.game.runtime.input import GraphInputError, run_graph_input_turn
from src.game.runtime.level_up import GraphLevelUpError, run_graph_level_up
from src.game.runtime.roll import GraphRollError, GraphRollExpected, run_graph_roll
from src.game.runtime.session import (
    initialize_graph_session,
    load_graph_session_state,
    run_graph_intro_request,
)
from src.game.runtime.turn import GraphActionTurnError
from src.llm.client import LLMClient, force_think

from ..deps import get_graph_repo, get_llm, get_scenario_repo
from ..schema import (
    ConfirmRequest,
    GraphActionResponse,
    GraphInputRequest,
    GraphLevelUpRequest,
    GraphRollRequest,
    GraphTurnRequest,
    InitRequest,
    InitResponse,
)

router = APIRouter()


def _request_thinking(enabled: bool) -> bool | None:
    return True if enabled else None


@router.post("/session/graph/init", response_model=InitResponse)
async def session_graph_init(
    body: InitRequest,
    graph_repo: GraphRepo = Depends(get_graph_repo),
    scenario_repo: ScenarioRepo = Depends(get_scenario_repo),
) -> InitResponse:
    try:
        result = await initialize_graph_session(
            body.profile, body.player, graph_repo, scenario_repo, locale=body.locale
        )
    except ProfileNotFound as e:
        raise HTTPException(status_code=422, detail=f"profile not found: {e}")
    except RaceNotFound as e:
        raise HTTPException(status_code=422, detail=f"race not found: {e}")
    except ProfileMalformed as e:
        raise HTTPException(status_code=422, detail=f"profile malformed: {e}")
    return InitResponse(
        game_id=result.game_id,
        state=result.front_state.model_dump(mode="json", by_alias=True),
    )


@router.post("/session/{game_id}/graph/intro", response_model=GraphActionResponse)
async def session_graph_intro(
    game_id: str,
    llm: LLMClient = Depends(get_llm),
    graph_repo: GraphRepo = Depends(get_graph_repo),
    scenario_repo: ScenarioRepo = Depends(get_scenario_repo),
) -> GraphActionResponse:
    try:
        result = await run_graph_intro_request(llm, graph_repo, game_id, scenario_repo)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="game not found")
    return GraphActionResponse(
        game_id=game_id,
        state=result.front_state.model_dump(mode="json", by_alias=True),
        status=result.status,
        message=result.message,
    )


@router.get("/session/{game_id}/graph/state", response_model=InitResponse)
async def get_graph_state_route(
    game_id: str,
    graph_repo: GraphRepo = Depends(get_graph_repo),
    scenario_repo: ScenarioRepo = Depends(get_scenario_repo),
) -> InitResponse:
    try:
        result = await load_graph_session_state(graph_repo, game_id, scenario_repo)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="game not found")
    return InitResponse(
        game_id=result.game_id,
        state=result.front_state.model_dump(mode="json", by_alias=True),
    )


@router.post("/session/{game_id}/graph/turn", response_model=GraphActionResponse)
async def session_graph_turn(
    game_id: str,
    body: GraphTurnRequest,
    llm: LLMClient = Depends(get_llm),
    graph_repo: GraphRepo = Depends(get_graph_repo),
    scenario_repo: ScenarioRepo = Depends(get_scenario_repo),
) -> GraphActionResponse:
    try:
        with force_think(_request_thinking(body.think)):
            result = await run_graph_action_request(
                graph_repo,
                game_id,
                body.action,
                llm=llm,
                scenario_repo=scenario_repo,
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
    scenario_repo: ScenarioRepo = Depends(get_scenario_repo),
) -> GraphActionResponse:
    try:
        with force_think(_request_thinking(body.think)):
            result = await run_graph_confirm(
                graph_repo,
                game_id,
                body.confirmation_id,
                body.decision,
                llm=llm,
                scenario_repo=scenario_repo,
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


@router.post("/session/{game_id}/graph/roll", response_model=GraphActionResponse)
async def session_graph_roll(
    game_id: str,
    body: GraphRollRequest,
    graph_repo: GraphRepo = Depends(get_graph_repo),
    scenario_repo: ScenarioRepo = Depends(get_scenario_repo),
) -> GraphActionResponse:
    try:
        result = await run_graph_roll(
            graph_repo,
            game_id,
            body.roll_id,
            scenario_repo=scenario_repo,
        )
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="game not found")
    except GraphRollExpected as e:
        raise HTTPException(status_code=422, detail=str(e))
    except GraphRollError as e:
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
    scenario_repo: ScenarioRepo = Depends(get_scenario_repo),
) -> GraphActionResponse:
    try:
        with force_think(_request_thinking(body.think)):
            result = await run_graph_input_turn(
                llm,
                graph_repo,
                game_id,
                body.player_input,
                scenario_repo=scenario_repo,
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
    scenario_repo: ScenarioRepo = Depends(get_scenario_repo),
) -> GraphActionResponse:
    try:
        result = await run_graph_level_up(
            graph_repo,
            game_id,
            stat_up=body.stat_up,
            skill_id=body.skill_id,
            scenario_repo=scenario_repo,
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
