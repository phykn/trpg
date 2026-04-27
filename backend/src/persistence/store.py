import asyncio
import os
import shutil
from pathlib import Path

from pydantic import BaseModel, TypeAdapter, ValidationError

from ..domain.entities import (
    Campaign,
    Chapter,
    Character,
    Item,
    Location,
    Quest,
    Race,
    Skill,
)
from ..domain.memory import (
    DialoguePair,
    LogEntry,
    PendingCheck,
    TurnLogEntry,
)
from ..domain.errors import PersistenceFailed
from ..rules import RULES
from ..domain.state import CombatState, GameState

_save_lock = asyncio.Lock()


# --- entity kind registry --------------------------------------------------

_ENTITY_MODELS: dict[str, type[BaseModel]] = {
    "characters": Character,
    "items": Item,
    "locations": Location,
    "races": Race,
    "skills": Skill,
    "quests": Quest,
    "chapters": Chapter,
    "campaigns": Campaign,
}


# --- paths -----------------------------------------------------------------


def _game_dir(saves_dir: str, game_id: str) -> Path:
    return Path(saves_dir) / "games" / game_id


def _meta_path(saves_dir: str, game_id: str) -> Path:
    return _game_dir(saves_dir, game_id) / "meta.json"


def _entity_path(saves_dir: str, game_id: str, kind: str, entity_id: str) -> Path:
    return _game_dir(saves_dir, game_id) / kind / f"{entity_id}.json"


def _log_path(saves_dir: str, game_id: str) -> Path:
    return _game_dir(saves_dir, game_id) / "log.jsonl"


def _history_path(saves_dir: str, game_id: str) -> Path:
    return _game_dir(saves_dir, game_id) / "history.jsonl"


def _dialogue_path(saves_dir: str, game_id: str) -> Path:
    return _game_dir(saves_dir, game_id) / "dialogue.jsonl"


def _current_path(saves_dir: str) -> Path:
    return Path(saves_dir) / ".current"


# --- IO primitives ---------------------------------------------------------


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


def _read_jsonl_tail(path: Path, cap: int) -> list[str]:
    """Read last `cap` non-empty lines from a jsonl file. Missing file → []."""
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return []
    except OSError as e:
        raise PersistenceFailed(str(e)) from e
    lines = [ln for ln in text.splitlines() if ln.strip()]
    return lines[-cap:] if cap > 0 else lines


# --- meta schema -----------------------------------------------------------


class _Meta(BaseModel):
    game_id: str
    profile: str
    player_id: str
    active_subject_id: str | None = None
    active_quest_id: str | None = None
    world_time: str
    turn_count: int = 0
    pending_check: PendingCheck | None = None
    pending_skill_candidates: list[Skill] = []
    combat_state: CombatState | None = None
    next_log_id: int = 1


def _meta_from_state(state: GameState) -> _Meta:
    return _Meta(
        game_id=state.game_id,
        profile=state.profile,
        player_id=state.player_id,
        active_subject_id=state.active_subject_id,
        active_quest_id=state.active_quest_id,
        world_time=state.world_time,
        turn_count=state.turn_count,
        pending_check=state.pending_check,
        pending_skill_candidates=list(state.pending_skill_candidates),
        combat_state=state.combat_state,
        next_log_id=state.next_log_id,
    )


# --- save (granular) -------------------------------------------------------


async def save_meta(state: GameState, saves_dir: str) -> None:
    payload = _meta_from_state(state).model_dump_json(indent=2)
    path = _meta_path(saves_dir, state.game_id)
    async with _save_lock:
        await asyncio.to_thread(_atomic_write, path, payload)


async def save_entity(
    state: GameState, saves_dir: str, kind: str, entity_id: str
) -> None:
    container = getattr(state, kind)
    if entity_id not in container:
        raise PersistenceFailed(f"unknown {kind} id: {entity_id!r}")
    payload = container[entity_id].model_dump_json(indent=2)
    path = _entity_path(saves_dir, state.game_id, kind, entity_id)
    async with _save_lock:
        await asyncio.to_thread(_atomic_write, path, payload)


async def append_log_entries(
    saves_dir: str, game_id: str, entries: list[LogEntry]
) -> None:
    if not entries:
        return
    lines = [e.model_dump_json() for e in entries]
    path = _log_path(saves_dir, game_id)
    async with _save_lock:
        await asyncio.to_thread(_append_jsonl, path, lines)


async def append_history_entries(
    saves_dir: str, game_id: str, entries: list[TurnLogEntry]
) -> None:
    if not entries:
        return
    lines = [e.model_dump_json() for e in entries]
    path = _history_path(saves_dir, game_id)
    async with _save_lock:
        await asyncio.to_thread(_append_jsonl, path, lines)


async def append_dialogue_entries(
    saves_dir: str, game_id: str, entries: list[DialoguePair]
) -> None:
    if not entries:
        return
    lines = [e.model_dump_json() for e in entries]
    path = _dialogue_path(saves_dir, game_id)
    async with _save_lock:
        await asyncio.to_thread(_append_jsonl, path, lines)


# --- save (bulk: initial / fallback) ---------------------------------------


async def save_full(state: GameState, saves_dir: str) -> None:
    """Persist every entity + meta. Used on game init.

    Does NOT create log.jsonl / history.jsonl / dialogue.jsonl — those are
    created lazily on first append.
    """
    gdir = _game_dir(saves_dir, state.game_id)
    gdir.mkdir(parents=True, exist_ok=True)
    await save_meta(state, saves_dir)
    for kind in _ENTITY_MODELS:
        for entity_id in getattr(state, kind):
            await save_entity(state, saves_dir, kind, entity_id)


# --- load ------------------------------------------------------------------


def _scan_entity_dir(
    saves_dir: str, game_id: str, kind: str, model_cls: type[BaseModel]
) -> dict:
    dir_ = _game_dir(saves_dir, game_id) / kind
    result: dict[str, BaseModel] = {}
    if not dir_.is_dir():
        return result
    for f in sorted(dir_.glob("*.json")):
        try:
            obj = model_cls.model_validate_json(f.read_text(encoding="utf-8"))
        except (ValidationError, OSError) as e:
            raise PersistenceFailed(f"{f}: {e}") from e
        result[obj.id] = obj  # type: ignore[attr-defined]
    return result


def _load_jsonl_tail(
    path: Path,
    cap: int,
    validator: TypeAdapter | type[BaseModel],
) -> list:
    """If validator is a BaseModel use model_validate_json; if TypeAdapter use validate_json."""
    lines = _read_jsonl_tail(path, cap)
    parse = (
        validator.validate_json
        if isinstance(validator, TypeAdapter)
        else validator.model_validate_json
    )
    out: list = []
    for line in lines:
        try:
            out.append(parse(line))
        except ValidationError as e:
            raise PersistenceFailed(f"{path}: {e}") from e
    return out


_LOG_ADAPTER: TypeAdapter[LogEntry] = TypeAdapter(LogEntry)


def load_game(saves_dir: str, game_id: str) -> GameState:
    gdir = _game_dir(saves_dir, game_id)
    if not gdir.is_dir():
        raise FileNotFoundError(str(gdir))

    meta_path = _meta_path(saves_dir, game_id)
    try:
        meta = _Meta.model_validate_json(meta_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise FileNotFoundError(str(meta_path))
    except (ValidationError, OSError) as e:
        raise PersistenceFailed(str(e)) from e

    entities: dict[str, dict] = {}
    for kind, model_cls in _ENTITY_MODELS.items():
        entities[kind] = _scan_entity_dir(saves_dir, game_id, kind, model_cls)

    log_entries = _load_jsonl_tail(
        _log_path(saves_dir, game_id), RULES.log.display_turns, _LOG_ADAPTER
    )
    turn_log = _load_jsonl_tail(
        _history_path(saves_dir, game_id),
        RULES.memory.turn_log_size,
        TurnLogEntry,
    )
    recent_dialogue = _load_jsonl_tail(
        _dialogue_path(saves_dir, game_id),
        RULES.memory.recent_dialogue_turns,
        DialoguePair,
    )

    # next_log_id self-heal: a mid-flush crash can leave meta.json stale while
    # log.jsonl already has new entries. Bumping past the largest id we've
    # actually loaded prevents id collisions on the next turn.
    next_log_id = meta.next_log_id
    if log_entries:
        max_disk_id = max(e.id for e in log_entries)
        if max_disk_id >= next_log_id:
            next_log_id = max_disk_id + 1

    return GameState(
        game_id=meta.game_id,
        profile=meta.profile,
        player_id=meta.player_id,
        active_subject_id=meta.active_subject_id,
        active_quest_id=meta.active_quest_id,
        world_time=meta.world_time,
        turn_count=meta.turn_count,
        pending_check=meta.pending_check,
        pending_skill_candidates=meta.pending_skill_candidates,
        combat_state=meta.combat_state,
        next_log_id=next_log_id,
        turn_log=turn_log,
        recent_dialogue=recent_dialogue,
        log_entries=log_entries,
        **entities,
    )


# --- .current pointer ------------------------------------------------------


def read_current_game_id(saves_dir: str) -> str | None:
    path = _current_path(saves_dir)
    try:
        text = path.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        return None
    except OSError as e:
        raise PersistenceFailed(str(e)) from e
    return text or None


async def write_current_game_id(saves_dir: str, game_id: str) -> None:
    path = _current_path(saves_dir)
    async with _save_lock:
        await asyncio.to_thread(_atomic_write, path, game_id)


# --- seed copy (for init_game) --------------------------------------------


def copy_seed_into_game(
    profile_dir: str, profile: str, saves_dir: str, game_id: str
) -> None:
    """Copy seed entity directories from profile into the game's save dir.

    Skipped: world.md, start.json, player_template.json, profile.json — those
    stay read-only in the profile.
    """
    src_root = Path(profile_dir) / profile
    if not src_root.is_dir():
        raise PersistenceFailed(f"profile dir not found: {src_root}")
    dst_root = _game_dir(saves_dir, game_id)
    dst_root.mkdir(parents=True, exist_ok=True)
    for kind in _ENTITY_MODELS:
        src = src_root / kind
        if not src.is_dir():
            continue
        dst = dst_root / kind
        dst.mkdir(parents=True, exist_ok=True)
        for f in src.glob("*.json"):
            shutil.copy2(f, dst / f.name)
