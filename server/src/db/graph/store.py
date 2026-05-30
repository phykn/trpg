import asyncio
import os
from collections.abc import Callable
from pathlib import Path

from pydantic import TypeAdapter, ValidationError

from src.game.domain.errors import PersistenceFailed
from src.game.domain.memory import (
    ExchangePair,
    LogEntry,
    Memory,
    TurnLogEntry,
)
from src.game.domain.story_patch_ledger import StoryPatchLedgerEntry

# Per-game write serialization. A single global lock would funnel unrelated
# game writes through one queue and — worse — let two requests for the same
# game_id race on overlapping reads-then-writes if the lock were ever dropped.
_save_locks: dict[str, asyncio.Lock] = {}


def _lock_for(game_id: str) -> asyncio.Lock:
    lock = _save_locks.get(game_id)
    if lock is None:
        lock = asyncio.Lock()
        _save_locks[game_id] = lock
    return lock


def _game_dir(saves_dir: str, game_id: str) -> Path:
    return Path(saves_dir) / "games" / game_id


def _log_path(saves_dir: str, game_id: str) -> Path:
    return _game_dir(saves_dir, game_id) / "log.jsonl"


def _history_path(saves_dir: str, game_id: str) -> Path:
    return _game_dir(saves_dir, game_id) / "history.jsonl"


def _exchange_path(saves_dir: str, game_id: str) -> Path:
    return _game_dir(saves_dir, game_id) / "exchange.jsonl"


def _memory_path(saves_dir: str, game_id: str) -> Path:
    return _game_dir(saves_dir, game_id) / "memory.jsonl"


def _story_patch_path(saves_dir: str, game_id: str) -> Path:
    return _game_dir(saves_dir, game_id) / "world_patch.jsonl"


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


def _append_jsonl(path: Path, lines: list[str]) -> None:
    if not lines:
        return
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            for line in lines:
                f.write(line + "\n")
    except OSError as e:
        raise PersistenceFailed(str(e)) from e


async def _append_entries(game_id: str, path: Path, entries: list) -> None:
    if not entries:
        return
    lines = [e.model_dump_json() for e in entries]
    async with _lock_for(game_id):
        await asyncio.to_thread(_append_jsonl, path, lines)


async def append_log_entries(
    saves_dir: str, game_id: str, entries: list[LogEntry]
) -> None:
    await _append_entries(game_id, _log_path(saves_dir, game_id), entries)


async def append_history_entries(
    saves_dir: str, game_id: str, entries: list[TurnLogEntry]
) -> None:
    await _append_entries(game_id, _history_path(saves_dir, game_id), entries)


async def append_exchange_entries(
    saves_dir: str, game_id: str, entries: list[ExchangePair]
) -> None:
    await _append_entries(game_id, _exchange_path(saves_dir, game_id), entries)


async def append_memory_entries(
    saves_dir: str, game_id: str, entries: list[Memory]
) -> None:
    await _append_entries(game_id, _memory_path(saves_dir, game_id), entries)


async def append_story_patch_entries(
    saves_dir: str, game_id: str, entries: list[StoryPatchLedgerEntry]
) -> None:
    await _append_entries(game_id, _story_patch_path(saves_dir, game_id), entries)


def _load_jsonl_tail(
    path: Path,
    cap: int,
    parse: Callable[[str | bytes], object],
) -> list:
    """parse is the bound `validate_json` / `model_validate_json` from the
    caller's TypeAdapter or BaseModel — caller already knows which it has,
    so no isinstance dispatch here."""
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        text = ""
    except OSError as e:
        raise PersistenceFailed(str(e)) from e
    raw_lines = [ln for ln in text.splitlines() if ln.strip()]
    lines = raw_lines[-cap:] if cap > 0 else raw_lines
    out: list = []
    for line in lines:
        try:
            out.append(parse(line))
        except ValidationError as e:
            raise PersistenceFailed(f"{path}: {e}") from e
    return out


_LOG_ADAPTER: TypeAdapter[LogEntry] = TypeAdapter(LogEntry)
