"""Supabase adapters: SaveRepo → PostgREST (5 tables keyed on game_id), ScenarioRepo → Storage (bucket mirrors local scenarios/ tree). Read-only seed cached process-wide; restart to invalidate."""

from __future__ import annotations

import asyncio
import json
from typing import Type, TypeVar

from pydantic import BaseModel, TypeAdapter, ValidationError

from src.game.domain.errors import PersistenceFailed
from src.game.domain.memory import (
    DialoguePair,
    LogEntry,
    TurnLogEntry,
)
from src.game.domain.state import GameState
from src.game.rules import RULES
from . import store
from ._supabase_http import _PostgREST, _Storage
from .repo import ScenarioRepo

T = TypeVar("T", bound=BaseModel)

# Canonical meta shape lives in store.py; reused for the `games.meta` jsonb column.
_Meta = store._Meta
_meta_from_state = store._meta_from_state
_ENTITY_MODELS = store._ENTITY_MODELS

_LOG_ADAPTER: TypeAdapter[LogEntry] = TypeAdapter(LogEntry)


class SupabaseSaveRepo:
    """SaveRepo over Supabase Postgres (PostgREST)."""

    def __init__(self, *, url: str, service_key: str) -> None:
        self._db = _PostgREST(url, service_key)

    async def save_meta(self, state: GameState) -> None:
        # JSON round-trip collapses nested Pydantic models to a plain dict for the jsonb column.
        meta = json.loads(_meta_from_state(state).model_dump_json())
        await self._db.upsert(
            "games",
            [{"game_id": state.game_id, "meta": meta}],
            on_conflict="game_id",
        )

    async def save_entity(self, state: GameState, kind: str, entity_id: str) -> None:
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

    async def append_log_entries(self, game_id: str, entries: list[LogEntry]) -> None:
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

    async def _append_seq_rows(
        self, table: str, game_id: str, entries: list[BaseModel]
    ) -> None:
        if not entries:
            return
        rows = [
            {"game_id": game_id, "entry": json.loads(e.model_dump_json())}
            for e in entries
        ]
        await self._db.insert(table, rows)

    async def append_history_entries(
        self, game_id: str, entries: list[TurnLogEntry]
    ) -> None:
        await self._append_seq_rows("history_entries", game_id, list(entries))

    async def append_dialogue_entries(
        self, game_id: str, entries: list[DialoguePair]
    ) -> None:
        await self._append_seq_rows("dialogue_entries", game_id, list(entries))

    async def load_game(self, game_id: str) -> GameState:
        # PostgREST accepts independent connections in parallel; fan out via gather.
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

        # Tail rows came back DESC; flip to chronological order.
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
            locale=meta.locale,
            player_id=meta.player_id,
            active_subject_id=meta.active_subject_id,
            active_quest_id=meta.active_quest_id,
            turn_count=meta.turn_count,
            pending_check=meta.pending_check,
            combat_state=meta.combat_state,
            previous_phase_signal=meta.previous_phase_signal,
            next_log_id=next_log_id,
            turn_log=turn_log,
            recent_dialogue=recent_dialogue,
            log_entries=log_entries,
            **entities,
        )

    async def copy_seed_into_game(
        self, scenario_repo: ScenarioRepo, profile: str, game_id: str, player_id: str
    ) -> None:
        """Bulk-INSERT seed entities as the new game's starting rows. world.md / start.json / player_template / profile stay seed-only."""
        # entities has FK → games, so create the games row first; this keeps the method independently consistent.
        # Stub meta must validate against _Meta in case init crashes before save_meta lands;
        # otherwise load_game would raise PersistenceFailed and the game_id would be permanently unrecoverable.
        stub_meta = _Meta(
            game_id=game_id, profile=profile, player_id=player_id
        ).model_dump(mode="json")
        await self._db.upsert(
            "games",
            [{"game_id": game_id, "meta": stub_meta}],
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
    """ScenarioRepo over a Supabase Storage bucket. Per-process caches are process-lifetime; restart to reload."""

    def __init__(self, *, url: str, service_key: str, bucket: str) -> None:
        self._fs = _Storage(url, service_key, bucket)
        self._object_cache: dict[str, bytes] = {}
        self._listing_cache: dict[str, list[str]] = {}

    async def _get_bytes_cached(self, path: str) -> bytes:
        if path in self._object_cache:
            return self._object_cache[path]
        blob = await self._fs.get_bytes(path)
        self._object_cache[path] = blob
        return blob

    async def _list_prefix_cached(self, prefix: str) -> list[str]:
        if prefix in self._listing_cache:
            return self._listing_cache[prefix]
        files = await self._fs.list_prefix(prefix)
        self._listing_cache[prefix] = files
        return files

    async def profile_exists(self, profile: str) -> bool:
        try:
            await self._get_bytes_cached(f"{profile}/profile.json")
            return True
        except FileNotFoundError:
            return False

    async def list_profiles(self) -> list[dict]:
        profile_ids = await self._fs.list_dirs("")

        async def _build_one(pid: str) -> dict | None:
            try:
                meta_blob = await self._get_bytes_cached(f"{pid}/profile.json")
            except FileNotFoundError:
                return None
            meta = json.loads(meta_blob.decode("utf-8"))
            race_files = await self._list_prefix_cached(f"{pid}/races")
            json_races = sorted(f for f in race_files if f.endswith(".json"))
            race_blobs = await asyncio.gather(
                *(self._get_bytes_cached(f"{pid}/races/{rf}") for rf in json_races)
            )
            races: list[dict] = []
            for blob in race_blobs:
                rd = json.loads(blob.decode("utf-8"))
                if rd.get("playable", True) is False:
                    continue
                races.append(
                    {
                        "id": rd.get("id"),
                        "name": rd.get("name"),
                        "description": rd.get("description", ""),
                    }
                )
            return {
                "id": meta.get("id", pid),
                "name": meta.get("name", pid),
                "description": meta.get("description", ""),
                "races": races,
            }

        results = await asyncio.gather(
            *(_build_one(pid) for pid in sorted(profile_ids))
        )
        return [r for r in results if r is not None]

    async def read_world_md(self, profile: str, *, missing_ok: bool = False) -> str:
        try:
            blob = await self._get_bytes_cached(f"{profile}/world.md")
        except FileNotFoundError:
            if missing_ok:
                return ""
            raise
        return blob.decode("utf-8")

    async def read_start_json(self, profile: str) -> dict:
        blob = await self._get_bytes_cached(f"{profile}/start.json")
        return json.loads(blob.decode("utf-8"))

    async def read_player_template(self, profile: str) -> dict:
        blob = await self._get_bytes_cached(f"{profile}/player_template.json")
        return json.loads(blob.decode("utf-8"))

    async def load_seed_entities(
        self, profile: str, kind: str, model_cls: Type[T]
    ) -> dict[str, T]:
        files = await self._list_prefix_cached(f"{profile}/{kind}")
        json_files = sorted(f for f in files if f.endswith(".json"))

        async def _load_one(name: str) -> T:
            blob = await self._get_bytes_cached(f"{profile}/{kind}/{name}")
            return model_cls.model_validate_json(blob)

        objs = await asyncio.gather(*(_load_one(f) for f in json_files))
        return {obj.id: obj for obj in objs}  # type: ignore[attr-defined]
