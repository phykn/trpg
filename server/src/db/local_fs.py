"""LocalFs SaveRepo / ScenarioRepo — sync IO wrapped in async to match the Protocol shared with Supabase."""

import json
from pathlib import Path
from typing import Type, TypeVar

from pydantic import BaseModel

from src.game.domain.memory import DialoguePair, LogEntry, TurnLogEntry
from src.game.domain.state import GameState
from . import store
from .repo import ScenarioRepo

T = TypeVar("T", bound=BaseModel)


class LocalFsSaveRepo:
    """Filesystem-backed SaveRepo. Delegates to `store.py` module functions."""

    def __init__(self, saves_dir: str) -> None:
        self.saves_dir = saves_dir

    async def save_meta(self, state: GameState) -> None:
        await store.save_meta(state, self.saves_dir)

    async def save_entity(self, state: GameState, kind: str, entity_id: str) -> None:
        await store.save_entity(state, self.saves_dir, kind, entity_id)

    async def append_log_entries(self, game_id: str, entries: list[LogEntry]) -> None:
        await store.append_log_entries(self.saves_dir, game_id, entries)

    async def append_history_entries(
        self, game_id: str, entries: list[TurnLogEntry]
    ) -> None:
        await store.append_history_entries(self.saves_dir, game_id, entries)

    async def append_dialogue_entries(
        self, game_id: str, entries: list[DialoguePair]
    ) -> None:
        await store.append_dialogue_entries(self.saves_dir, game_id, entries)

    async def load_game(self, game_id: str) -> GameState:
        return store.load_game(self.saves_dir, game_id)

    async def copy_seed_into_game(
        self, scenario_repo: ScenarioRepo, profile: str, game_id: str, player_id: str
    ) -> None:
        # player_id is unused here — LocalFs has no stub-meta hazard because meta
        # is only written by save_meta; entity files don't reference it.
        del player_id
        game_root = store._game_dir(self.saves_dir, game_id)
        game_root.mkdir(parents=True, exist_ok=True)
        for kind, model_cls in store._ENTITY_MODELS.items():
            seed = await scenario_repo.load_seed_entities(profile, kind, model_cls)
            if not seed:
                continue
            kind_dir = game_root / kind
            kind_dir.mkdir(parents=True, exist_ok=True)
            for ent_id, obj in seed.items():
                (kind_dir / f"{ent_id}.json").write_text(
                    obj.model_dump_json(), encoding="utf-8"
                )


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

    async def load_seed_entities(
        self, profile: str, kind: str, model_cls: Type[T]
    ) -> dict[str, T]:
        dirpath = self._root(profile) / kind
        result: dict[str, T] = {}
        if not dirpath.is_dir():
            return result
        for f in sorted(dirpath.glob("*.json")):
            obj = model_cls.model_validate_json(f.read_text(encoding="utf-8"))
            result[obj.id] = obj  # type: ignore[attr-defined]
        return result
