"""Test-only in-memory fakes for the Supabase HTTP layer.

The Supabase adapter (`SupabaseSaveRepo`, `SupabaseStorageScenarioRepo`)
talks to two transports — `_PostgREST` and `_Storage` — both of which we
replace with these fakes in tests. Result: tests exercise the real
adapter logic (row shaping, cache behavior, ordering, FK ordering)
without any network IO, credentials, or real DB pollution.

`make_default_storage()` returns a FakeStorage pre-loaded with a
minimal-but-valid `default` scenario seed (1 race, 1 location, 1 NPC,
1 skill) — enough to satisfy `check_scenario` invariants and let
/session/init succeed end-to-end.
"""

from __future__ import annotations

import json
from typing import Any

from src.game.domain.entities import (
    Character,
    Location,
    Race,
    Skill,
    Stats,
)
from src.game.engines.growth import calc_max_hp, calc_max_mp
from src.db.supabase import (
    SupabaseSaveRepo,
    SupabaseStorageScenarioRepo,
)


# ---------------------------------------------------------------------------
# In-memory PostgREST


class FakePostgREST:
    """In-memory PostgREST. Tracks rows per table; mimics filter/order/limit."""

    def __init__(self) -> None:
        self.rows: dict[str, list[dict]] = {}
        self.calls: list[tuple] = []

    async def upsert(self, table: str, rows: list[dict], *, on_conflict: str) -> None:
        self.calls.append(("upsert", table, rows, on_conflict))
        keys = on_conflict.split(",")
        store_ = self.rows.setdefault(table, [])
        for new in rows:
            for i, existing in enumerate(store_):
                if all(existing.get(k) == new.get(k) for k in keys):
                    store_[i] = new
                    break
            else:
                store_.append(new)

    async def insert(self, table: str, rows: list[dict]) -> None:
        self.calls.append(("insert", table, rows))
        store_ = self.rows.setdefault(table, [])
        for offset, r in enumerate(rows, start=1):
            if table in ("history_entries", "dialogue_entries") and "seq" not in r:
                r["seq"] = len(store_) + offset
        store_.extend(rows)

    async def delete(self, table: str, *, filters: dict[str, str]) -> None:
        self.calls.append(("delete", table, filters))
        store_ = self.rows.get(table, [])

        def _matches(row: dict) -> bool:
            for col, expr in filters.items():
                assert expr.startswith("eq."), f"only eq supported in fake: {expr}"
                if str(row.get(col)) != expr[3:]:
                    return False
            return True

        self.rows[table] = [row for row in store_ if not _matches(row)]

    async def select(
        self,
        table: str,
        *,
        filters: dict[str, str],
        select: str = "*",
        order: str | None = None,
        limit: int | None = None,
    ) -> list[dict]:
        store_ = self.rows.get(table, [])
        out = list(store_)
        for col, expr in filters.items():
            assert expr.startswith("eq."), f"only eq supported in fake: {expr}"
            val = expr[3:]
            out = [r for r in out if str(r.get(col)) == val]
        if order:
            col, _, dir_ = order.partition(".")
            out.sort(key=lambda r: r.get(col, 0), reverse=(dir_ == "desc"))
        if limit is not None:
            out = out[:limit]
        return out

    async def select_one(
        self, table: str, *, filters: dict[str, str], select: str = "*"
    ) -> dict | None:
        rows = await self.select(table, filters=filters, select=select, limit=1)
        return rows[0] if rows else None


# ---------------------------------------------------------------------------
# In-memory Storage


class FakeStorage:
    """In-memory bucket. paths -> bytes."""

    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    async def get_bytes(self, path: str) -> bytes:
        if path not in self.objects:
            raise FileNotFoundError(path)
        return self.objects[path]

    async def get_text(self, path: str) -> str:
        return (await self.get_bytes(path)).decode("utf-8")

    async def list_prefix(self, prefix: str) -> list[str]:
        head = prefix.rstrip("/") + "/"
        names: set[str] = set()
        for p in self.objects:
            if not p.startswith(head):
                continue
            tail = p[len(head) :]
            if "/" in tail:
                continue
            names.add(tail)
        return sorted(names)

    async def list_dirs(self, prefix: str) -> list[str]:
        head = prefix.rstrip("/") + "/" if prefix else ""
        dirs: set[str] = set()
        for p in self.objects:
            if not p.startswith(head):
                continue
            tail = p[len(head) :]
            first, sep, _ = tail.partition("/")
            if sep:
                dirs.add(first)
        return sorted(dirs)


# ---------------------------------------------------------------------------
# Repo constructors that bypass __init__ (which would try to talk to network)


def make_save_repo(
    db: FakePostgREST | None = None,
) -> tuple[SupabaseSaveRepo, FakePostgREST]:
    repo = SupabaseSaveRepo.__new__(SupabaseSaveRepo)
    db = db or FakePostgREST()
    repo._db = db  # type: ignore[attr-defined]
    return repo, db


def make_scenario_repo(
    fs: FakeStorage | None = None,
) -> tuple[SupabaseStorageScenarioRepo, FakeStorage]:
    repo = SupabaseStorageScenarioRepo.__new__(SupabaseStorageScenarioRepo)
    fs = fs or FakeStorage()
    repo._fs = fs  # type: ignore[attr-defined]
    repo._object_cache = {}  # type: ignore[attr-defined]
    repo._listing_cache = {}  # type: ignore[attr-defined]
    return repo, fs


# ---------------------------------------------------------------------------
# Minimal default seed (1 race, 1 location, 1 NPC, 1 skill)


def _put_json(fs: FakeStorage, path: str, data: Any) -> None:
    if hasattr(data, "model_dump_json"):
        blob = data.model_dump_json().encode("utf-8")
    else:
        blob = json.dumps(data, ensure_ascii=False).encode("utf-8")
    fs.objects[path] = blob


def make_default_storage() -> FakeStorage:
    """A FakeStorage pre-populated with a minimal-but-valid `default` profile.

    Satisfies `check_scenario` invariants (NPC level ≥ 1, NPC has at least
    one skill, hp == max_hp, race's racial_skills exist in the skills pool,
    active_subject_id in characters and colocated with start_location_id).
    """
    fs = FakeStorage()

    fs.objects["default/profile.json"] = json.dumps(
        {"id": "default", "name": "테스트", "description": "최소 시드"},
        ensure_ascii=False,
    ).encode("utf-8")
    fs.objects["default/world.md"] = "테스트 세계".encode("utf-8")
    fs.objects["default/start.json"] = json.dumps(
        {
            "start_location_id": "loc_01",
            "active_subject_id": "edrik_chief",
            "active_quest_id": None,
        }
    ).encode("utf-8")
    fs.objects["default/player_template.json"] = json.dumps(
        {
            "id": "player_01",
            "equipment": {},
            "inventory_ids": [],
            "gold": 0,
            "xp_pool": 0,
        }
    ).encode("utf-8")

    skill = Skill(
        id="basic_strike",
        name="기본 타격",
        description="기본 공격 기술",
        type="attack",
        target="single",
        primary_stat="STR",
        power=5,
    )
    human = Race(
        id="human",
        name="인간",
        description="테스트 인간",
        racial_skill_ids=["basic_strike"],
    )
    loc = Location(id="loc_01", name="광장", description="테스트 광장")

    stats = Stats()
    edric = Character(
        id="edrik_chief",
        name="에드릭",
        race_id="human",
        gender="male",
        location_id="loc_01",
        level=4,
        stats=stats,
        racial_skill_ids=["basic_strike"],
    )
    edric.max_hp = calc_max_hp(edric.level, stats.CON)
    edric.max_mp = calc_max_mp(edric.level, stats.INT)
    edric.hp = edric.max_hp
    edric.mp = edric.max_mp

    _put_json(fs, "default/skills/basic_strike.json", skill)
    _put_json(fs, "default/races/human.json", human)
    _put_json(fs, "default/locations/loc_01.json", loc)
    _put_json(fs, "default/characters/edrik_chief.json", edric)

    return fs
