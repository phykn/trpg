"""Tests for SupabaseSaveRepo / SupabaseStorageScenarioRepo using in-memory
fakes for the PostgREST + Storage transports. We don't hit a real Supabase —
the tests verify the adapter logic (row shaping, ordering, caching, FK
ordering, parse/serialize symmetry)."""

import json
from pathlib import Path

import pytest

from src.domain.entities import Character, Item, Location, Race
from src.domain.memory import (
    ActLogEntry,
    DialoguePair,
    TurnLogEntry,
)
from src.domain.errors import PersistenceFailed
from src.domain.state import GameState
from src.persistence.supabase import (
    SupabaseSaveRepo,
    SupabaseStorageScenarioRepo,
)


# ---------------------------------------------------------------------------
# Fakes


class FakePostgREST:
    """In-memory PostgREST. Tracks rows per table; mimics filter/order/limit."""

    def __init__(self) -> None:
        self.rows: dict[str, list[dict]] = {}
        self.calls: list[tuple] = []

    async def upsert(
        self, table: str, rows: list[dict], *, on_conflict: str
    ) -> None:
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
        # Auto-fill bigserial-style seq for log/history/dialogue tables when
        # the caller didn't supply one (history_entries, dialogue_entries).
        for r in rows:
            if table in ("history_entries", "dialogue_entries") and "seq" not in r:
                r["seq"] = len(store_) + 1
        store_.extend(rows)

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
        # Names directly under prefix/, no recursion.
        head = prefix.rstrip("/") + "/"
        names: set[str] = set()
        for p in self.objects:
            if not p.startswith(head):
                continue
            tail = p[len(head):]
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
            tail = p[len(head):]
            first, sep, _ = tail.partition("/")
            if sep:
                dirs.add(first)
        return sorted(dirs)


def _make_save_repo() -> tuple[SupabaseSaveRepo, FakePostgREST]:
    repo = SupabaseSaveRepo.__new__(SupabaseSaveRepo)
    db = FakePostgREST()
    repo._db = db  # type: ignore[attr-defined]
    return repo, db


def _make_scenario_repo() -> tuple[SupabaseStorageScenarioRepo, FakeStorage]:
    repo = SupabaseStorageScenarioRepo.__new__(SupabaseStorageScenarioRepo)
    fs = FakeStorage()
    repo._fs = fs  # type: ignore[attr-defined]
    repo._world_cache = {}  # type: ignore[attr-defined]
    repo._tempdir_cache = {}  # type: ignore[attr-defined]
    repo._tempdir_handles = []  # type: ignore[attr-defined]
    import asyncio

    repo._lock = asyncio.Lock()  # type: ignore[attr-defined]
    return repo, fs


# ---------------------------------------------------------------------------
# Helpers


def _bare_state(game_id: str = "g_test_000000_aaaaaa") -> GameState:
    """Minimal GameState — enough to exercise meta + entity persistence."""
    char = Character(
        id="player_01",
        name="플레이어",
        is_player=True,
        race_id="human",
        gender="male",
        location_id="loc_01",
    )
    return GameState(
        game_id=game_id,
        profile="default",
        player_id="player_01",
        characters={"player_01": char},
        next_log_id=5,
    )


# ---------------------------------------------------------------------------
# SaveRepo tests


async def test_save_meta_upserts_jsonb_column():
    repo, db = _make_save_repo()
    state = _bare_state()
    await repo.save_meta(state)

    assert "games" in db.rows
    assert len(db.rows["games"]) == 1
    row = db.rows["games"][0]
    assert row["game_id"] == state.game_id
    assert row["meta"]["profile"] == "default"
    assert row["meta"]["next_log_id"] == 5

    # Second call upserts (no duplicate row).
    state.next_log_id = 7
    await repo.save_meta(state)
    assert len(db.rows["games"]) == 1
    assert db.rows["games"][0]["meta"]["next_log_id"] == 7


async def test_save_entity_upserts_per_kind_id():
    repo, db = _make_save_repo()
    state = _bare_state()
    await repo.save_entity(state, "characters", "player_01")

    rows = db.rows["entities"]
    assert len(rows) == 1
    r = rows[0]
    assert (r["game_id"], r["kind"], r["id"]) == (state.game_id, "characters", "player_01")
    assert r["data"]["name"] == "플레이어"


async def test_save_entity_unknown_id_raises():
    repo, _ = _make_save_repo()
    state = _bare_state()
    with pytest.raises(PersistenceFailed):
        await repo.save_entity(state, "characters", "nonexistent")


async def test_append_log_uses_entry_id_as_log_id():
    repo, db = _make_save_repo()
    entries = [
        ActLogEntry(id=10, kind="act", text="첫 행동"),
        ActLogEntry(id=11, kind="act", text="두 번째"),
    ]
    await repo.append_log_entries("g_x", entries)

    rows = db.rows["log_entries"]
    assert [r["log_id"] for r in rows] == [10, 11]
    assert all(r["game_id"] == "g_x" for r in rows)
    assert rows[0]["entry"]["text"] == "첫 행동"


async def test_append_log_empty_is_noop():
    repo, db = _make_save_repo()
    await repo.append_log_entries("g_x", [])
    assert "log_entries" not in db.rows


async def test_append_history_and_dialogue():
    repo, db = _make_save_repo()
    hist = [TurnLogEntry(turn=1, target="npc_01", summary="요약")]
    dlg = [DialoguePair(turn=1, player="안녕", narrator="반갑소")]
    await repo.append_history_entries("g_x", hist)
    await repo.append_dialogue_entries("g_x", dlg)

    assert db.rows["history_entries"][0]["entry"]["summary"] == "요약"
    assert db.rows["dialogue_entries"][0]["entry"]["narrator"] == "반갑소"


async def test_load_game_missing_raises_filenotfound():
    repo, _ = _make_save_repo()
    with pytest.raises(FileNotFoundError):
        await repo.load_game("g_nonexistent")


async def test_load_game_round_trips_meta_and_entities():
    repo, db = _make_save_repo()
    state = _bare_state()
    await repo.save_meta(state)
    await repo.save_entity(state, "characters", "player_01")

    loaded = await repo.load_game(state.game_id)
    assert loaded.game_id == state.game_id
    assert loaded.profile == "default"
    assert "player_01" in loaded.characters
    assert loaded.characters["player_01"].name == "플레이어"


async def test_load_game_reverses_tail_to_chronological_order():
    repo, db = _make_save_repo()
    state = _bare_state()
    await repo.save_meta(state)
    # Insert log_entries with ids 1..5 — load_game should sort desc, limit,
    # then reverse back so the returned list is ascending by id.
    entries = [
        ActLogEntry(id=i, kind="act", text=f"t{i}")
        for i in range(1, 6)
    ]
    await repo.append_log_entries(state.game_id, entries)
    loaded = await repo.load_game(state.game_id)
    assert [e.id for e in loaded.log_entries] == [1, 2, 3, 4, 5]


async def test_load_game_next_log_id_self_heal():
    """If meta.next_log_id is stale (crash mid-flush), bump past max id we
    actually loaded."""
    repo, db = _make_save_repo()
    state = _bare_state()
    state.next_log_id = 3  # stale
    await repo.save_meta(state)
    entries = [
        ActLogEntry(id=i, kind="act", text=f"t{i}")
        for i in (1, 2, 5)  # disk has up to 5
    ]
    await repo.append_log_entries(state.game_id, entries)
    loaded = await repo.load_game(state.game_id)
    assert loaded.next_log_id == 6


async def test_copy_seed_into_game_inserts_entities():
    """Drives copy_seed_into_game with a fake scenario_repo that returns a
    handful of seed entities; verifies the entities table receives them."""
    repo, db = _make_save_repo()

    class _FakeScenario:
        async def load_seed_entities(self, profile, kind, model_cls):
            if kind == "characters":
                return {
                    "npc_01": Character(
                        id="npc_01",
                        name="에드릭",
                        race_id="human",
                        gender="male",
                        location_id="loc_01",
                    )
                }
            if kind == "races":
                return {"human": Race(id="human", name="인간", description="...")}
            return {}

    await repo.copy_seed_into_game(_FakeScenario(), "default", "g_seed_test")

    # games row created first (FK precondition).
    assert any(r["game_id"] == "g_seed_test" for r in db.rows["games"])

    inserted_kinds = {r["kind"] for r in db.rows["entities"]}
    assert inserted_kinds == {"characters", "races"}


# ---------------------------------------------------------------------------
# ScenarioRepo tests


async def test_profile_exists_true_when_profile_json_present():
    repo, fs = _make_scenario_repo()
    fs.objects["default/profile.json"] = b'{"id":"default","name":"X"}'
    assert await repo.profile_exists("default") is True
    assert await repo.profile_exists("missing") is False


async def test_read_world_md_caches_second_call():
    repo, fs = _make_scenario_repo()
    fs.objects["default/world.md"] = "# 세계\n원본".encode("utf-8")
    a = await repo.read_world_md("default")
    # Mutate underlying storage; cached read should still return the original.
    fs.objects["default/world.md"] = "변경됨".encode("utf-8")
    b = await repo.read_world_md("default")
    assert a == b == "# 세계\n원본"


async def test_read_world_md_missing_ok_returns_empty():
    repo, _ = _make_scenario_repo()
    assert await repo.read_world_md("absent", missing_ok=True) == ""
    with pytest.raises(FileNotFoundError):
        await repo.read_world_md("absent")


async def test_read_start_and_player_template():
    repo, fs = _make_scenario_repo()
    fs.objects["default/start.json"] = json.dumps(
        {"start_location_id": "loc_01"}
    ).encode("utf-8")
    fs.objects["default/player_template.json"] = json.dumps(
        {"id": "player_01", "gold": 5}
    ).encode("utf-8")
    start = await repo.read_start_json("default")
    template = await repo.read_player_template("default")
    assert start["start_location_id"] == "loc_01"
    assert template["gold"] == 5


async def test_load_seed_entities_parses_each_file():
    repo, fs = _make_scenario_repo()
    fs.objects["default/items/sword.json"] = json.dumps(
        {"id": "sword", "name": "검", "description": "강철", "weight": 1.0}
    ).encode("utf-8")
    fs.objects["default/items/shield.json"] = json.dumps(
        {"id": "shield", "name": "방패", "description": "원형", "weight": 2.0}
    ).encode("utf-8")
    items = await repo.load_seed_entities("default", "items", Item)
    assert set(items) == {"sword", "shield"}
    assert items["sword"].name == "검"


async def test_local_profile_path_materializes_and_caches(tmp_path, monkeypatch):
    repo, fs = _make_scenario_repo()
    fs.objects["default/world.md"] = b"# world"
    fs.objects["default/profile.json"] = b'{"id":"default","name":"X"}'
    fs.objects["default/items/sword.json"] = (
        '{"id":"sword","name":"검","description":"","weight":1.0}'.encode("utf-8")
    )

    p1 = await repo.local_profile_path("default")
    assert (p1 / "world.md").read_text() == "# world"
    assert (p1 / "items" / "sword.json").exists()

    # Second call returns same cached Path (no re-materialize).
    p2 = await repo.local_profile_path("default")
    assert p1 == p2


async def test_list_profiles_walks_top_level_dirs():
    repo, fs = _make_scenario_repo()
    fs.objects["default/profile.json"] = json.dumps(
        {"id": "default", "name": "기본", "description": "d1"}
    ).encode("utf-8")
    fs.objects["default/races/human.json"] = json.dumps(
        {"id": "human", "name": "인간", "description": "d2"}
    ).encode("utf-8")
    fs.objects["other/profile.json"] = json.dumps(
        {"id": "other", "name": "다른", "description": ""}
    ).encode("utf-8")

    profiles = await repo.list_profiles()
    ids = sorted(p["id"] for p in profiles)
    assert ids == ["default", "other"]
    default = next(p for p in profiles if p["id"] == "default")
    assert default["name"] == "기본"
    assert [r["id"] for r in default["races"]] == ["human"]
