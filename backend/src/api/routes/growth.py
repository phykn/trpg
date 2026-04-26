"""Growth routes — level-up + learn-skill."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import ValidationError

from ...domain.errors import LevelUpInvalid, LLMUnavailable
from ...domain.state import GameState
from ...engines.growth import level_up
from ...flow.skill_recommend import recommend_skill_candidates
from ...llm.client import LLMClient
from ...mapping.to_front import to_front_state
from ...persistence.store import save_entity, save_meta
from ..deps import get_llm, get_saves_dir, get_state
from ..schema import LearnSkillRequest, LearnSkillResponse, LevelUpRequest, LevelUpResponse

router = APIRouter()


@router.post("/session/{game_id}/level-up", response_model=LevelUpResponse)
async def session_level_up(
    body: LevelUpRequest,
    state: GameState = Depends(get_state),
    llm: LLMClient = Depends(get_llm),
    saves_dir: str = Depends(get_saves_dir),
) -> LevelUpResponse:
    player = state.characters[state.player_id]
    try:
        level_up(player, body.stat_up, body.stat_down)  # type: ignore[arg-type]
    except LevelUpInvalid as e:
        raise HTTPException(status_code=422, detail=str(e))

    # §2.3 step 4 — LLM picks skill candidates. Failure is silent.
    try:
        state.pending_skill_candidates = await recommend_skill_candidates(llm, state)
    except (ValidationError, LLMUnavailable, OSError, TimeoutError):
        state.pending_skill_candidates = []

    await save_entity(state, saves_dir, "characters", state.player_id)
    await save_meta(state, saves_dir)
    return LevelUpResponse(
        game_id=state.game_id,
        state=to_front_state(state),
        skill_candidates=[s.model_dump() for s in state.pending_skill_candidates],
    )


@router.post("/session/{game_id}/learn-skill", response_model=LearnSkillResponse)
async def session_learn_skill(
    body: LearnSkillRequest,
    state: GameState = Depends(get_state),
    saves_dir: str = Depends(get_saves_dir),
) -> LearnSkillResponse:
    player = state.characters[state.player_id]
    candidates = list(state.pending_skill_candidates)
    learned_id: str | None = None
    if body.index is not None and 0 <= body.index < len(candidates):
        chosen = candidates[body.index]
        player.learned_skills.append(chosen)
        learned_id = chosen.id
    state.pending_skill_candidates = []
    await save_entity(state, saves_dir, "characters", state.player_id)
    await save_meta(state, saves_dir)
    return LearnSkillResponse(
        game_id=state.game_id,
        state=to_front_state(state),
        learned_skill_id=learned_id,
    )
