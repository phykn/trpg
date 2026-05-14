import os
from pathlib import Path

from fastapi import APIRouter, Depends

from src.db.repo import ScenarioRepo

from .deps import get_scenario_repo
from .schema import ProfileCard

public_router = APIRouter()
protected_router = APIRouter()


def _resolve_sha() -> str:
    rendered = os.environ.get("RENDER_GIT_COMMIT")
    if rendered:
        return rendered[:7]
    git_dir = Path(__file__).resolve().parents[4] / ".git"
    head = git_dir / "HEAD"
    if not head.is_file():
        return "local"
    ref = head.read_text().strip()
    if ref.startswith("ref: "):
        ref_path = git_dir / ref[5:]
        if ref_path.is_file():
            return ref_path.read_text().strip()[:7]
    return ref[:7]


SHA = _resolve_sha()


@public_router.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@public_router.get("/version")
async def version() -> dict:
    return {"sha": SHA}


@protected_router.get("/profiles", response_model=list[ProfileCard])
async def list_profiles(
    scenario_repo: ScenarioRepo = Depends(get_scenario_repo),
) -> list[dict]:
    return await scenario_repo.list_profiles()
