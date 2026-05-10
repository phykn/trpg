"""Local filesystem ScenarioRepo used by tests and local dev."""

import json
from pathlib import Path


class LocalFsScenarioRepo:
    """Filesystem-backed ScenarioRepo over a single `profile_dir` root."""

    def __init__(self, profile_dir: str) -> None:
        self.profile_dir = profile_dir

    def _root(self, profile: str) -> Path:
        return Path(self.profile_dir) / profile

    async def profile_exists(self, profile: str) -> bool:
        return self._root(profile).is_dir()

    async def list_profiles(self) -> list[dict]:
        pdir = Path(self.profile_dir)
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
                    if rd.get("playable", True) is False:
                        continue
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

    async def read_world_md(self, profile: str, *, missing_ok: bool = False) -> str:
        p = self._root(profile) / "world.md"
        if missing_ok and not p.exists():
            return ""
        return p.read_text(encoding="utf-8")

    async def read_start_json(self, profile: str) -> dict:
        return json.loads(
            (self._root(profile) / "start.json").read_text(encoding="utf-8")
        )

    async def read_player_template(self, profile: str) -> dict:
        return json.loads(
            (self._root(profile) / "player_template.json").read_text(encoding="utf-8")
        )

    async def load_seed_records(self, profile: str, kind: str) -> dict[str, dict]:
        dirpath = self._root(profile) / kind
        result: dict[str, dict] = {}
        if not dirpath.is_dir():
            return result
        for f in sorted(dirpath.glob("*.json")):
            obj = json.loads(f.read_text(encoding="utf-8"))
            record_id = obj.get("id")
            if isinstance(record_id, str):
                result[record_id] = obj
        return result
