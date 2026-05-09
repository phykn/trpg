"""Profile listing — delegates to the ScenarioRepo."""

from fastapi import APIRouter, Depends

from src.db.repo import ScenarioRepo
from ..deps import get_scenario_repo
from ..schema import ProfileCard

router = APIRouter()


@router.get("/profiles", response_model=list[ProfileCard])
async def list_profiles(
    scenario_repo: ScenarioRepo = Depends(get_scenario_repo),
) -> list[dict]:
    return await scenario_repo.list_profiles()
