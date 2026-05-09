import os
from pathlib import Path

from fastapi import APIRouter

router = APIRouter()


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


@router.get("/version")
async def version() -> dict:
    return {"sha": SHA}
