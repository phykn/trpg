"""Session lifecycle — init/state and the streaming entries
(turn / roll / intro)."""
from fastapi import APIRouter, Depends, HTTPException

from ...domain.errors import ProfileMalformed, ProfileNotFound, RaceNotFound
from ...domain.state import GameState
from ...flow.intro import run_intro
from ...flow.roll import run_roll
from ...flow.turn import run_turn
from ...llm.client import LLMClient
from ...mapping.to_front import to_front_state
from ...persistence.init import init_game
from ..deps import get_llm, get_profile_dir, get_saves_dir, get_state
from ..schema import InitRequest, InitResponse, TurnRequest
from ..sse import streaming_response

router = APIRouter()


@router.post("/session/init", response_model=InitResponse)
async def session_init(
    body: InitRequest,
    saves_dir: str = Depends(get_saves_dir),
    profile_dir: str = Depends(get_profile_dir),
) -> InitResponse:
    try:
        state = await init_game(body.profile, body.player, saves_dir, profile_dir)
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


@router.post("/session/{game_id}/turn")
async def session_turn(
    body: TurnRequest,
    state: GameState = Depends(get_state),
    llm: LLMClient = Depends(get_llm),
    saves_dir: str = Depends(get_saves_dir),
    profile_dir: str = Depends(get_profile_dir),
):
    return streaming_response(
        run_turn(
            llm, state, profile_dir, saves_dir, body.player_input,
            to_front_fn=to_front_state,
        )
    )


@router.post("/session/{game_id}/roll")
async def session_roll(
    state: GameState = Depends(get_state),
    llm: LLMClient = Depends(get_llm),
    saves_dir: str = Depends(get_saves_dir),
    profile_dir: str = Depends(get_profile_dir),
):
    return streaming_response(
        run_roll(
            llm, state, profile_dir, saves_dir, to_front_fn=to_front_state,
        )
    )


@router.post("/session/{game_id}/intro")
async def session_intro(
    state: GameState = Depends(get_state),
    llm: LLMClient = Depends(get_llm),
    saves_dir: str = Depends(get_saves_dir),
    profile_dir: str = Depends(get_profile_dir),
):
    return streaming_response(
        run_intro(
            llm, state, profile_dir, saves_dir, to_front_fn=to_front_state,
        )
    )
