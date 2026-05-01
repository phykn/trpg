"""Session lifecycle — init/state and the streaming entries
(turn / roll / intro)."""

from fastapi import APIRouter, Depends, HTTPException

from ...domain.errors import ProfileMalformed, ProfileNotFound, RaceNotFound
from ...domain.state import GameState
from ...flow.intro import run_intro
from ...flow.roll import run_roll
from ...flow.turn import run_turn
from ...llm.client import LLMClient, set_think_override
from ...mapping.to_front import to_front_state, to_story_graph
from ...persistence.init import init_game
from ...persistence.repo import SaveRepo, ScenarioRepo
from ..deps import get_llm, get_save_repo, get_scenario_repo, get_state
from ..schema import (
    InitRequest,
    InitResponse,
    RollRequest,
    StoryGraphResponse,
    TurnRequest,
)
from ..sse import streaming_response

router = APIRouter()


@router.post("/session/init", response_model=InitResponse)
async def session_init(
    body: InitRequest,
    save_repo: SaveRepo = Depends(get_save_repo),
    scenario_repo: ScenarioRepo = Depends(get_scenario_repo),
) -> InitResponse:
    try:
        state = await init_game(body.profile, body.player, save_repo, scenario_repo)
    except ProfileNotFound as e:
        raise HTTPException(status_code=422, detail=f"profile not found: {e}")
    except RaceNotFound as e:
        raise HTTPException(status_code=422, detail=f"race not found: {e}")
    except ProfileMalformed as e:
        raise HTTPException(status_code=422, detail=f"profile malformed: {e}")
    return InitResponse(game_id=state.game_id, state=to_front_state(state))


@router.get("/session/{game_id}/state")
async def get_state_route(state: GameState = Depends(get_state)) -> dict:
    return {"game_id": state.game_id, "state": to_front_state(state)}


@router.get("/session/{game_id}/graph", response_model=StoryGraphResponse)
async def get_graph_route(state: GameState = Depends(get_state)) -> StoryGraphResponse:
    return StoryGraphResponse(**to_story_graph(state))


@router.post("/session/{game_id}/turn")
async def session_turn(
    body: TurnRequest,
    state: GameState = Depends(get_state),
    llm: LLMClient = Depends(get_llm),
    save_repo: SaveRepo = Depends(get_save_repo),
    scenario_repo: ScenarioRepo = Depends(get_scenario_repo),
):
    set_think_override(body.think)
    return streaming_response(
        run_turn(
            llm,
            state,
            scenario_repo,
            save_repo,
            body.player_input,
            to_front_fn=to_front_state,
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
