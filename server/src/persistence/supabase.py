"""Supabase adapters for SaveRepo / ScenarioRepo (Phase 2).

SaveRepo → Supabase Postgres via PostgREST. Five tables (see
`server/migrations/001_init.sql`):
    games            (game_id PK, meta jsonb, updated_at)
    entities         (game_id, kind, id, data jsonb) PK(game_id,kind,id)
    log_entries      (game_id, log_id, entry jsonb)  PK(game_id,log_id)
    history_entries  (game_id, seq bigserial, entry jsonb)
    dialogue_entries (game_id, seq bigserial, entry jsonb)

ScenarioRepo → Supabase Storage. Layout in the bucket mirrors the local
`scenarios/<profile>/...` tree 1:1. Per-process caches:
    - `world.md` content per profile
    - `local_profile_path` materialized tempdir per profile
    - any seed-entity dir we've already enumerated

The seed is read-only and the server is long-lived, so caching is safe and
cheap. Cache invalidation is process-restart only — re-deploy on seed
changes, same as it would be on local fs.
"""

from __future__ import annotations

import asyncio
import json
import tempfile
from pathlib import Path
from typing import Any, Type, TypeVar

from pydantic import BaseModel, TypeAdapter, ValidationError

from ..domain.errors import PersistenceFailed
from ..domain.memory import (
    DialoguePair,
    LogEntry,
    PendingCheck,
    TurnLogEntry,
)
from ..domain.entities import Skill
from ..domain.state import CombatState, GameState
from ..rules import RULES
from . import store
from ._supabase_http import _PostgREST, _Storage
from .repo import ScenarioRepo

T = TypeVar("T", bound=BaseModel)

# Reuse the meta schema from store.py — it's the canonical shape for the
# `games.meta` jsonb column.
_Meta = store._Meta
_meta_from_state = store._meta_from_state
_ENTITY_MODELS = store._ENTITY_MODELS

_LOG_ADAPTER: TypeAdapter[LogEntry] = TypeAdapter(LogEntry)


class SupabaseSaveRepo:
    """SaveRepo over Supabase Postgres (PostgREST)."""

    def __init__(self, *, url: str, service_key: str) -> None:
        self._db = _PostgREST(url, service_key)

    async def save_meta(self, state: GameState) -> None:
        # _Meta dumps to a dict whose nested models (PendingCheck, Skill,
        # CombatState) are themselves jsonable — round-trip via JSON to
        # collapse to plain dict for the jsonb column.
        meta = json.loads(_meta_from_state(state).model_dump_json())
        await self._db.upsert(
            "games",
            [{"game_id": state.game_id, "meta": meta}],
            on_conflict="game_id",
        )

    async def save_entity(
        self, state: GameState, kind: str, entity_id: str
    ) -> None:
        container = getattr(state, kind)
        if entity_id not in container:
            raise PersistenceFailed(f"unknown {kind} id: {entity_id!r}")
        data = json.loads(container[entity_id].model_dump_json())
        await self._db.upsert(
            "entities",
            [
                {
                    "game_id": state.game_id,
                    "kind": kind,
                    "id": entity_id,
                    "data": data,
                }
            ],
            on_conflict="game_id,kind,id",
        )

    async def append_log_entries(
        self, game_id: str, entries: list[LogEntry]
    ) -> None:
        if not entries:
            return
        rows = [
            {
                "game_id": game_id,
                "log_id": e.id,
                "entry": json.loads(e.model_dump_json()),
            }
            for e in entries
        ]
        await self._db.insert("log_entries", rows)

    async def append_history_entries(
        self, game_id: str, entries: list[TurnLogEntry]
    ) -> None:
        if not entries:
            return
        rows = [
            {"game_id": game_id, "entry": json.loads(e.model_dump_json())}
            for e in entries
        ]
        await self._db.insert("history_entries", rows)

    async def append_dialogue_entries(
        self, game_id: str, entries: list[DialoguePair]
    ) -> None:
        if not entries:
            return
        rows = [
            {"game_id": game_id, "entry": json.loads(e.model_dump_json())}
            for e in entries
        ]
        await self._db.insert("dialogue_entries", rows)

    async def load_game(self, game_id: str) -> GameState:
        # Single round-trip per resource. Fan out via gather — PostgREST
        # accepts independent connections in parallel.
        meta_row, entity_rows, log_rows, hist_rows, dlg_rows = await asyncio.gather(
            self._db.select_one(
                "games", filters={"game_id": f"eq.{game_id}"}, select="meta"
            ),
            self._db.select(
                "entities",
                filters={"game_id": f"eq.{game_id}"},
                select="kind,id,data",
            ),
            self._db.select(
                "log_entries",
                filters={"game_id": f"eq.{game_id}"},
                select="entry",
                order="log_id.desc",
                limit=RULES.log.display_turns,
            ),
            self._db.select(
                "history_entries",
                filters={"game_id": f"eq.{game_id}"},
                select="entry",
                order="seq.desc",
                limit=RULES.memory.turn_log_size,
            ),
            self._db.select(
                "dialogue_entries",
                filters={"game_id": f"eq.{game_id}"},
                select="entry",
                order="seq.desc",
                limit=RULES.memory.recent_dialogue_turns,
            ),
        )

        if meta_row is None:
            raise FileNotFoundError(game_id)

        try:
            meta = _Meta.model_validate(meta_row["meta"])
        except ValidationError as e:
            raise PersistenceFailed(f"games.meta {game_id}: {e}") from e

        entities: dict[str, dict] = {kind: {} for kind in _ENTITY_MODELS}
        for row in entity_rows:
            kind = row["kind"]
            model_cls = _ENTITY_MODELS.get(kind)
            if model_cls is None:
                raise PersistenceFailed(f"unknown entity kind in db: {kind!r}")
            try:
                obj = model_cls.model_validate(row["data"])
            except ValidationError as e:
                raise PersistenceFailed(
                    f"entities {game_id}/{kind}/{row['id']}: {e}"
                ) from e
            entities[kind][row["id"]] = obj

        # Tail rows came back DESC — flip to chronological order.
        log_entries = [
            _LOG_ADAPTER.validate_python(r["entry"]) for r in reversed(log_rows)
        ]
        turn_log = [
            TurnLogEntry.model_validate(r["entry"]) for r in reversed(hist_rows)
        ]
        recent_dialogue = [
            DialoguePair.model_validate(r["entry"]) for r in reversed(dlg_rows)
        ]

        # next_log_id self-heal — same logic as store.load_game.
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
            turn_count=meta.turn_count,
            pending_check=meta.pending_check,
            pending_skill_candidates=meta.pending_skill_candidates,
            combat_state=meta.combat_state,
            previous_phase_signal=meta.previous_phase_signal,
            next_log_id=next_log_id,
            turn_log=turn_log,
            recent_dialogue=recent_dialogue,
            log_entries=log_entries,
            **entities,
        )

    async def copy_seed_into_game(
        self, scenario_repo: ScenarioRepo, profile: str, game_id: str
    ) -> None:
        """Read seed entities via scenario_repo and bulk-INSERT them as
        the new game's starting entity rows. Skipped: world.md / start.json /
        player_template.json / profile.json — those stay seed-only."""
        # The games row must exist first because entities has FK to games.
        # Caller (init_game → flush) writes meta separately; ensure a row
        # exists here so this method is independently consistent.
        await self._db.upsert(
            "games",
            [{"game_id": game_id, "meta": {"game_id": game_id, "profile": profile}}],
            on_conflict="game_id",
        )

        for kind, model_cls in _ENTITY_MODELS.items():
            seed = await scenario_repo.load_seed_entities(profile, kind, model_cls)
            if not seed:
                continue
            rows = [
                {
                    "game_id": game_id,
                    "kind": kind,
                    "id": ent_id,
                    "data": json.loads(obj.model_dump_json()),
                }
                for ent_id, obj in seed.items()
            ]
            await self._db.insert("entities", rows)


class SupabaseStorageScenarioRepo:
    """ScenarioRepo over a Supabase Storage bucket.

    Layout: <bucket>/<profile>/{world.md, start.json, player_template.json,
    profile.json, races/*.json, characters/*.json, items/*.json, ...}.

    Caches per profile: world.md content, materialized tempdir Path,
    enumerated seed entity dirs. Process-lifetime only — restart to reload.
    """

    def __init__(self, *, url: str, service_key: str, bucket: str) -> None:
        self._fs = _Storage(url, service_key, bucket)
        self._world_cache: dict[str, str] = {}
        self._tempdir_cache: dict[str, Path] = {}
        # Hold a reference to the TemporaryDirectory objects so they don't
        # clean up before process exit.
        self._tempdir_handles: list[tempfile.TemporaryDirectory] = []
        self._lock = asyncio.Lock()

    async def profile_exists(self, profile: str) -> bool:
        try:
            await self._fs.get_bytes(f"{profile}/profile.json")
            return True
        except FileNotFoundError:
            return False

    async def list_profiles(self) -> list[dict]:
        profile_ids = await self._fs.list_dirs("")
        out: list[dict] = []
        for pid in sorted(profile_ids):
            try:
                meta_text = await self._fs.get_text(f"{pid}/profile.json")
            except FileNotFoundError:
                continue
            meta = json.loads(meta_text)
            race_files = await self._fs.list_prefix(f"{pid}/races")
            races: list[dict] = []
            for rf in sorted(race_files):
                if not rf.endswith(".json"):
                    continue
                rd = json.loads(await self._fs.get_text(f"{pid}/races/{rf}"))
                races.append(
                    {
                        "id": rd.get("id"),
                        "name": rd.get("name"),
                        "description": rd.get("description", ""),
                    }
                )
            out.append(
                {
                    "id": meta.get("id", pid),
                    "name": meta.get("name", pid),
                    "description": meta.get("description", ""),
                    "races": races,
                }
            )
        return out

    async def read_world_md(
        self, profile: str, *, missing_ok: bool = False
    ) -> str:
        if profile in self._world_cache:
            return self._world_cache[profile]
        try:
            text = await self._fs.get_text(f"{profile}/world.md")
        except FileNotFoundError:
            if missing_ok:
                # Don't cache — a strict caller after this should still raise,
                # and we don't want a transient miss to mask a later upload.
                return ""
            raise
        self._world_cache[profile] = text
        return text

    async def read_start_json(self, profile: str) -> dict:
        return json.loads(await self._fs.get_text(f"{profile}/start.json"))

    async def read_player_template(self, profile: str) -> dict:
        return json.loads(
            await self._fs.get_text(f"{profile}/player_template.json")
        )

    async def load_seed_entities(
        self, profile: str, kind: str, model_cls: Type[T]
    ) -> dict[str, T]:
        files = await self._fs.list_prefix(f"{profile}/{kind}")
        result: dict[str, T] = {}
        for f in sorted(files):
            if not f.endswith(".json"):
                continue
            text = await self._fs.get_text(f"{profile}/{kind}/{f}")
            obj = model_cls.model_validate_json(text)
            result[obj.id] = obj  # type: ignore[attr-defined]
        return result

    async def local_profile_path(self, profile: str) -> Path:
        """Materialize the entire profile dir into a tempdir lazily, return
        its Path. `engines/invariants.Scenario.from_dir` walks a real fs tree
        and we don't want to fight that — easier to write the seed once."""
        async with self._lock:
            if profile in self._tempdir_cache:
                return self._tempdir_cache[profile]

            handle = tempfile.TemporaryDirectory(prefix=f"trpg-seed-{profile}-")
            self._tempdir_handles.append(handle)
            root = Path(handle.name) / profile
            root.mkdir(parents=True, exist_ok=True)

            # Top-level files.
            for fname in ("world.md", "start.json", "player_template.json", "profile.json"):
                try:
                    blob = await self._fs.get_bytes(f"{profile}/{fname}")
                except FileNotFoundError:
                    continue
                (root / fname).write_bytes(blob)

            # Per-kind subdirs.
            for kind in _ENTITY_MODELS:
                files = await self._fs.list_prefix(f"{profile}/{kind}")
                if not files:
                    continue
                kind_dir = root / kind
                kind_dir.mkdir(exist_ok=True)
                for f in files:
                    if not f.endswith(".json"):
                        continue
                    blob = await self._fs.get_bytes(f"{profile}/{kind}/{f}")
                    (kind_dir / f).write_bytes(blob)

            self._tempdir_cache[profile] = root
            return root
