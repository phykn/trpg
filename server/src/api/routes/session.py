"""Session lifecycle — init/state and the streaming entries
(turn / roll / intro)."""

import asyncio

from fastapi import APIRouter, Depends, HTTPException
from pydantic import ValidationError

from src.game.domain.errors import (
    LLMUnavailable,
    ProfileMalformed,
    ProfileNotFound,
    RaceNotFound,
)
from src.game.domain.state import GameState
from src.game.flow._diag import diag
from src.game.flow.init_graph import init_graph_game
from src.game.flow.intro import run_intro
from src.game.flow.confirmation import run_confirm
from src.game.flow.level_up import run_level_up
from src.game.flow.roll import run_roll
from src.game.flow.skill_recommend import recommend_skill_candidates
from src.game.flow.turn import run_turn
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
from src.wire.to_front import to_front_state
from src.game.flow.init import init_game
from src.db.repo import GraphRepo, SaveRepo, ScenarioRepo
from ..deps import (
    get_graph_repo,
    get_llm,
    get_save_repo,
    get_scenario_repo,
    get_state,
)
from ..schema import (
    GraphActionResponse,
    GraphInputRequest,
    GraphLevelUpRequest,
    GraphTurnRequest,
    InitRequest,
    InitResponse,
    ConfirmRequest,
    LevelUpPreviewResponse,
    LevelUpRequest,
    RollRequest,
    TurnRequest,
)
from ..sse import streaming_response

router = APIRouter()

_GRAPH_INIT_NARRATION_TIMEOUT_SECONDS = 6.0


@router.post("/session/init", response_model=InitResponse)
async def session_init(
    body: InitRequest,
    save_repo: SaveRepo = Depends(get_save_repo),
    scenario_repo: ScenarioRepo = Depends(get_scenario_repo),
) -> InitResponse:
    try:
        state = await init_game(
            body.profile, body.player, save_repo, scenario_repo, locale=body.locale
        )
    except ProfileNotFound as e:
        raise HTTPException(status_code=422, detail=f"profile not found: {e}")
    except RaceNotFound as e:
        raise HTTPException(status_code=422, detail=f"race not found: {e}")
    except ProfileMalformed as e:
        raise HTTPException(status_code=422, detail=f"profile malformed: {e}")
    return InitResponse(game_id=state.game_id, state=to_front_state(state))


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


@router.get("/session/{game_id}/state")
async def get_state_route(state: GameState = Depends(get_state)) -> dict:
    return {"game_id": state.game_id, "state": to_front_state(state)}


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


@router.post("/session/{game_id}/turn")
async def session_turn(
    body: TurnRequest,
    state: GameState = Depends(get_state),
    llm: LLMClient = Depends(get_llm),
    save_repo: SaveRepo = Depends(get_save_repo),
    scenario_repo: ScenarioRepo = Depends(get_scenario_repo),
):
    set_think_override(body.think)
    quest_action = (
        (body.quest_action.kind, body.quest_action.quest_id)
        if body.quest_action is not None
        else None
    )
    return streaming_response(
        run_turn(
            llm,
            state,
            scenario_repo,
            save_repo,
            body.player_input,
            to_front_fn=to_front_state,
            quest_action=quest_action,
        )
    )


@router.post("/session/{game_id}/roll")
async def session_roll(
    body: RollRequest,
    state: GameState = Depends(get_state),
    llm: LLMClient = Depends(get_llm),
    save_repo: SaveRepo = Depends(get_save_repo),
    scenario_repo: ScenarioRepo = Depends(get_scenario_repo),
):
    set_think_override(body.think)
    return streaming_response(
        run_roll(
            llm,
            state,
            scenario_repo,
            save_repo,
            to_front_fn=to_front_state,
        )
    )


@router.post("/session/{game_id}/confirm")
async def session_confirm(
    body: ConfirmRequest,
    state: GameState = Depends(get_state),
    llm: LLMClient = Depends(get_llm),
    save_repo: SaveRepo = Depends(get_save_repo),
    scenario_repo: ScenarioRepo = Depends(get_scenario_repo),
):
    set_think_override(body.think)
    return streaming_response(
        run_confirm(
            llm,
            state,
            scenario_repo,
            save_repo,
            body.confirmation_id,
            body.decision,
            to_front_fn=to_front_state,
        )
    )


@router.post("/session/{game_id}/intro")
async def session_intro(
    state: GameState = Depends(get_state),
    llm: LLMClient = Depends(get_llm),
    save_repo: SaveRepo = Depends(get_save_repo),
    scenario_repo: ScenarioRepo = Depends(get_scenario_repo),
):
    return streaming_response(
        run_intro(
            llm,
            state,
            scenario_repo,
            save_repo,
            to_front_fn=to_front_state,
        )
    )


@router.get(
    "/session/{game_id}/level_up_preview", response_model=LevelUpPreviewResponse
)
async def session_level_up_preview(
    state: GameState = Depends(get_state),
    llm: LLMClient = Depends(get_llm),
) -> LevelUpPreviewResponse:
    try:
        candidates = await recommend_skill_candidates(llm, state)
    except (ValidationError, LLMUnavailable, OSError, TimeoutError) as e:
        # LLM failure → empty list (client treats this as 'no skill choice required').
        diag(
            state.game_id, state.turn_count, "recommend:failed",
            err=type(e).__name__,
            memories=len(state.characters[state.player_id].memories),
            turn_log=len(state.turn_log),
            msg=str(e)[:200],
        )
        candidates = []
    if 0 < len(candidates) < 3:
        diag(
            state.game_id, state.turn_count, "recommend:short",
            n=len(candidates),
        )
    return LevelUpPreviewResponse(
        skill_candidates=[s.model_dump() for s in candidates],
    )


@router.post("/session/{game_id}/level_up")
async def session_level_up(
    body: LevelUpRequest,
    state: GameState = Depends(get_state),
    llm: LLMClient = Depends(get_llm),
    save_repo: SaveRepo = Depends(get_save_repo),
    scenario_repo: ScenarioRepo = Depends(get_scenario_repo),
):
    set_think_override(body.think)
    return streaming_response(
        run_level_up(
            llm,
            state,
            scenario_repo,
            save_repo,
            stat_up=body.stat_up,
            skill_id=body.skill_id,
            to_front_fn=to_front_state,
        )
    )
