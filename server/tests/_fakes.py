"""Test-only in-memory fakes for the Supabase HTTP layer.

The Supabase graph and scenario adapters talk to `_PostgREST` and `_Storage`.
Tests replace both with these fakes so adapter logic runs without network IO,
credentials, or real DB pollution.

`make_default_storage()` returns a FakeStorage pre-loaded with a
minimal `default` scenario seed (1 race, 1 location, 1 NPC,
1 skill) — enough to let
/session/graph/init succeed end-to-end.
"""

import json
from typing import Any

from src.db.supabase import SupabaseStorageScenarioRepo
from src.game.engines.growth import calc_max_hp, calc_max_mp


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
                if expr.startswith("eq."):
                    if str(row.get(col)) != expr[3:]:
                        return False
                    continue
                if expr.startswith("not.in.(") and expr.endswith(")"):
                    values = set(expr[8:-1].split(","))
                    if str(row.get(col)) in values:
                        return False
                    continue
                if expr.startswith("in.(") and expr.endswith(")"):
                    values = set(expr[4:-1].split(","))
                    if str(row.get(col)) not in values:
                        return False
                    continue
                raise AssertionError(f"unsupported fake filter: {expr}")
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
    blob = json.dumps(data, ensure_ascii=False).encode("utf-8")
    fs.objects[path] = blob


def make_default_storage() -> FakeStorage:
    """A FakeStorage pre-populated with a minimal-but-valid `default` profile.

    Includes enough graph seed data for /session/graph/init to succeed.
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

    skill = {
        "id": "basic_strike",
        "name": "기본 타격",
        "description": "기본 공격 기술",
        "kind": "attack",
        "target": "single",
        "power": 5,
    }
    human = {
        "id": "human",
        "name": "인간",
        "description": "테스트 인간",
        "racial_skill_ids": ["basic_strike"],
    }
    loc = {"id": "loc_01", "name": "광장", "description": "테스트 광장"}

    edric_level = 4
    edric_stats = {"body": 10, "agility": 10, "mind": 10, "presence": 10}
    edric = {
        "id": "edrik_chief",
        "name": "에드릭",
        "race_id": "human",
        "gender": "male",
        "location_id": "loc_01",
        "level": edric_level,
        "stats": edric_stats,
        "racial_skill_ids": ["basic_strike"],
        "max_hp": calc_max_hp(edric_level, edric_stats["body"]),
        "max_mp": calc_max_mp(edric_level, edric_stats["mind"]),
    }
    edric["hp"] = edric["max_hp"]
    edric["mp"] = edric["max_mp"]

    _put_json(fs, "default/skills/basic_strike.json", skill)
    _put_json(fs, "default/races/human.json", human)
    _put_json(fs, "default/locations/loc_01.json", loc)
    _put_json(fs, "default/characters/edrik_chief.json", edric)

    return fs
