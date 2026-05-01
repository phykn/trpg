"""Profile listing — scans <profile_dir>/<id>/profile.json + races/."""

import json
from pathlib import Path

from fastapi import APIRouter, Depends

from ..deps import get_profile_dir
from ..schema import ProfileCard

router = APIRouter()


def _scan_profiles(profile_dir: str) -> list[dict]:
    pdir = Path(profile_dir)
    out: list[dict] = []
    if not pdir.is_dir():
        return out
    for sub in sorted(pdir.iterdir()):
        meta_file = sub / "profile.json"
        if not sub.is_dir() or not meta_file.exists():
            continue
        meta = json.loads(meta_file.read_text(encoding="utf-8"))
        races: list[dict] = []
        races_dir = sub / "races"
        if races_dir.is_dir():
            for rf in sorted(races_dir.glob("*.json")):
                rd = json.loads(rf.read_text(encoding="utf-8"))
                races.append(
                    {
                        "id": rd.get("id"),
                        "name": rd.get("name"),
                        "description": rd.get("description", ""),
                    }
                )
        out.append(
            {
                "id": meta.get("id", sub.name),
                "name": meta.get("name", sub.name),
                "description": meta.get("description", ""),
                "races": races,
            }
        )
    return out


@router.get("/profiles", response_model=list[ProfileCard])
async def list_profiles(profile_dir: str = Depends(get_profile_dir)) -> list[dict]:
    return _scan_profiles(profile_dir)
