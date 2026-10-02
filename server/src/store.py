"""Save complete game snapshots with one atomic file replacement."""

import asyncio
import json
import os
import re
from pathlib import Path

from src.game.models import GameState, IncompatibleSave


class SaveError(RuntimeError):
    pass


def _atomic_write(path: Path, data: str) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp.write_text(data, encoding="utf-8")
        os.replace(tmp, path)
    except OSError as exc:
        try:
            tmp.unlink(missing_ok=True)
        except OSError:
            pass
        raise SaveError(str(exc)) from exc


class SaveStore:
    def __init__(self, root: Path):
        self.root = root
        self._locks: dict[str, asyncio.Lock] = {}

    def _path(self, game_id: str) -> Path:
        if not re.fullmatch(r"adv_[a-f0-9]{32}", game_id):
            raise FileNotFoundError(game_id)
        return self.root / f"{game_id}.json"

    def lock(self, game_id: str) -> asyncio.Lock:
        self._path(game_id)
        return self._locks.setdefault(game_id, asyncio.Lock())

    async def load(self, game_id: str) -> GameState:
        try:
            content = await asyncio.to_thread(
                self._path(game_id).read_text, encoding="utf-8"
            )
        except FileNotFoundError:
            raise
        except OSError as exc:
            raise SaveError(str(exc)) from exc
        raw = json.loads(content)
        if not isinstance(raw, dict):
            raise IncompatibleSave("unsupported snapshot structure")
        if raw.get("schema_version") != 1:
            raise IncompatibleSave("snapshot schema version mismatch")
        return GameState.model_validate_json(content)

    async def save(self, state: GameState) -> None:
        write = asyncio.create_task(
            asyncio.to_thread(
                _atomic_write, self._path(state.game_id), state.model_dump_json()
            )
        )
        try:
            await asyncio.shield(write)
        except asyncio.CancelledError:
            # Keep the command lock until the write finishes, even on disconnect.
            await write
            raise
