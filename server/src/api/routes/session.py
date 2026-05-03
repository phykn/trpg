"""Session lifecycle — init/state and the streaming entries
(turn / roll / intro)."""

import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import ValidationError

from ...domain.errors import (
    LLMUnavailable,
    ProfileMalformed,
    ProfileNotFound,
    RaceNotFound,
)
from ...domain.state import GameState
from ...flow.intro import run_intro
from ...flow.level_up import run_level_up
from ...flow.roll import run_roll
from ...flow.skill_recommend import recommend_skill_candidates
from ...flow.turn import run_turn
from ...llm.client import LLMClient, set_think_override
from ...mapping.to_front import to_front_state
from ...persistence.init import init_game
from ...persistence.repo import SaveRepo, ScenarioRepo
from ..deps import get_llm, get_save_repo, get_scenario_repo, get_state
from ..schema import (
    InitRequest,
    InitResponse,
    LevelUpPreviewResponse,
    LevelUpRequest,
    RollRequest,
    TurnRequest,
)
from ..sse import streaming_response

router = APIRouter()
_log = logging.getLogger(__name__)


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
        _log.warning(
            "recommend_skill_candidates failed: type=%s game_id=%s memories=%d turn_log=%d err=%s",
            type(e).__name__,
            state.game_id,
            len(state.characters[state.player_id].memories),
            len(state.turn_log),
            str(e)[:200],
        )
        candidates = []
    if 0 < len(candidates) < 3:
        _log.info(
            "recommend_skill_candidates returned %d (< 3): game_id=%s",
            len(candidates),
            state.game_id,
        )
    return LevelUpPreviewResponse(
        skill_candidates=[
            {
                "id": s.id,
                "name": s.name,
                "description": s.description,
                "type": s.type,
                "target": s.target,
                "primary_stat": s.primary_stat,
                "special_effect": s.special_effect,
            }
            for s in candidates
        ],
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
