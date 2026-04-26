import asyncio
import os
from pathlib import Path

from pydantic import ValidationError

from ..errors import PersistenceFailed
from .models import GameState

_save_lock = asyncio.Lock()


def _games_dir(data_dir: str) -> Path:
    return Path(data_dir) / "games"


def _game_path(data_dir: str, game_id: str) -> Path:
    return _games_dir(data_dir) / f"{game_id}.json"


def _current_path(data_dir: str) -> Path:
    return Path(data_dir) / ".current"


def _atomic_write(path: Path, data: str) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp.write_text(data, encoding="utf-8")
        os.replace(tmp, path)
    except OSError as e:
        if tmp.exists():
            try:
                tmp.unlink()
            except OSError:
                pass
        raise PersistenceFailed(str(e)) from e


def load_game(data_dir: str, game_id: str) -> GameState:
    path = _game_path(data_dir, game_id)
    try:
        data = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise
    except OSError as e:
        raise PersistenceFailed(str(e)) from e
    try:
        return GameState.model_validate_json(data)
    except ValidationError as e:
        raise PersistenceFailed(str(e)) from e


async def save_game(state: GameState, data_dir: str) -> None:
    payload = state.model_dump_json(indent=2)
    path = _game_path(data_dir, state.game_id)
    async with _save_lock:
        await asyncio.to_thread(_atomic_write, path, payload)


def read_current_game_id(data_dir: str) -> str | None:
    path = _current_path(data_dir)
    try:
        text = path.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        return None
    except OSError as e:
        raise PersistenceFailed(str(e)) from e
    return text or None


async def write_current_game_id(data_dir: str, game_id: str) -> None:
    path = _current_path(data_dir)
    async with _save_lock:
        await asyncio.to_thread(_atomic_write, path, game_id)
