# Graph Persistence Boundary Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Use superpowers:test-driven-development for every production change. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add graph-native save/load boundaries for graph nodes, graph edges, and progress state without moving live gameplay off legacy `GameState` yet.

**Architecture:** Keep current `SaveRepo` untouched for live flows. Add a separate graph persistence boundary that can save/load `Graph` and `GameProgress` through LocalFs and Supabase adapters. Use pure row codecs so LocalFs, fake Supabase tests, and real Supabase row shapes share the same validation path.

**Tech Stack:** Python 3.12+, Pydantic v2, pytest, Ruff, Supabase PostgREST, root `.venv` on Windows.

---

## Scope

This plan implements Phase 1 from `2026-05-09-graph-first-game-roadmap.md`.

It does not migrate `/turn`, combat, seed upload, client state, or existing entity-table live saves.

## File Structure

- `server/src/game/domain/progress.py`
  - New graph-first progress envelope for non-graph runtime state.
- `server/src/db/graph_progress_rows.py`
  - New row codec for `game_progress`.
- `server/src/db/repo.py`
  - Add a `GraphRepo` protocol. Existing `SaveRepo` stays unchanged.
- `server/src/db/graph_local_fs.py`
  - New LocalFs adapter for graph/progress round trips in tests and future QA.
- `server/src/db/graph_supabase.py`
  - New Supabase adapter for `graph_nodes`, `graph_edges`, and `game_progress`.
- `server/src/db/_supabase_http.py`
  - Add `delete` support for replace-style graph saves.
- `server/tests/_fakes.py`
  - Add fake `delete` behavior.
- `server/tests/db/test_graph_progress_rows.py`
  - Tests progress row round-trip.
- `server/tests/db/test_graph_local_fs.py`
  - Tests LocalFs graph/progress persistence.
- `server/tests/db/test_graph_supabase.py`
  - Tests Supabase graph/progress row shaping with fakes.
- `docs/supabase/graph_tables.sql`
  - SQL reference for graph tables, constraints, and indexes.

## Task 1: Progress Model And Row Codec

**Files:**
- Create: `server/src/game/domain/progress.py`
- Create: `server/src/db/graph_progress_rows.py`
- Test: `server/tests/db/test_graph_progress_rows.py`

- [ ] **Step 1: Write failing progress row tests**

Create `server/tests/db/test_graph_progress_rows.py`:

```python
from src.db.graph_progress_rows import progress_from_row, progress_to_row
from src.game.domain.progress import GameProgress
from src.game.domain.state import CombatState


def test_progress_row_round_trip():
    progress = GameProgress(
        game_id="game-1",
        player_id="player",
        locale="ko",
        active_subject_id="elder",
        active_quest_id="quest",
        turn_count=3,
        combat_state=CombatState(round=2, enemy_ids=["rat"]),
        next_log_id=9,
    )

    row = progress_to_row(progress)

    assert row.game_id == "game-1"
    assert row.progress["player_id"] == "player"
    assert row.progress["combat_state"]["round"] == 2

    restored = progress_from_row(row)

    assert restored == progress


def test_progress_row_accepts_pending_confirmation_payload():
    progress = GameProgress(
        game_id="game-1",
        player_id="player",
        pending_confirmation={
            "id": "confirm-1",
            "kind": "attack_start",
            "action": {"verb": "attack", "what": ["rat"]},
        },
    )

    restored = progress_from_row(progress_to_row(progress))

    assert restored.pending_confirmation["kind"] == "attack_start"
```

- [ ] **Step 2: Run tests and confirm RED**

Run:

```powershell
& .\.venv\Scripts\python.exe -m pytest server\tests\db\test_graph_progress_rows.py -q
```

Expected: fail because `src.game.domain.progress` and `src.db.graph_progress_rows` do not exist.

- [ ] **Step 3: Implement progress model**

Create `server/src/game/domain/progress.py`:

```python
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from src.game.domain.memory import PendingCheck
from src.game.domain.state import CombatState


class GameProgress(BaseModel):
    model_config = ConfigDict(extra="forbid")

    game_id: str
    player_id: str
    locale: str = "ko"
    active_subject_id: str | None = None
    active_quest_id: str | None = None
    turn_count: int = 0
    pending_check: PendingCheck | None = None
    pending_confirmation: dict[str, Any] | None = None
    combat_state: CombatState | None = None
    previous_phase_signal: str | None = None
    next_log_id: int = Field(default=1, ge=1)
```

- [ ] **Step 4: Implement progress row codec**

Create `server/src/db/graph_progress_rows.py`:

```python
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict

from src.game.domain.progress import GameProgress


class GameProgressRow(BaseModel):
    model_config = ConfigDict(extra="forbid")

    game_id: str
    progress: dict[str, Any]


def progress_to_row(progress: GameProgress) -> GameProgressRow:
    payload = progress.model_dump(mode="json", exclude={"game_id"})
    return GameProgressRow(game_id=progress.game_id, progress=payload)


def progress_from_row(row: GameProgressRow) -> GameProgress:
    return GameProgress(game_id=row.game_id, **row.progress)
```

- [ ] **Step 5: Run tests and confirm GREEN**

Run:

```powershell
& .\.venv\Scripts\python.exe -m pytest server\tests\db\test_graph_progress_rows.py -q
```

Expected: pass.

## Task 2: GraphRepo Protocol

**Files:**
- Modify: `server/src/db/repo.py`

- [ ] **Step 1: Add the protocol after `SaveRepo`**

Modify `server/src/db/repo.py`:

```python
from src.game.domain.graph import Graph
from src.game.domain.progress import GameProgress


class GraphRepo(Protocol):
    """Graph-native persistence. Not used by legacy live flow until migration."""

    async def save_graph(self, game_id: str, graph: Graph) -> None: ...

    async def load_graph(self, game_id: str) -> Graph: ...

    async def save_progress(self, progress: GameProgress) -> None: ...

    async def load_progress(self, game_id: str) -> GameProgress: ...
```

- [ ] **Step 2: Run import smoke test**

Run:

```powershell
& .\.venv\Scripts\python.exe -c "import sys; sys.path.insert(0, 'server'); from src.db.repo import GraphRepo; print(GraphRepo)"
```

Expected: exits 0 and prints the protocol object.

## Task 3: LocalFs GraphRepo

**Files:**
- Create: `server/src/db/graph_local_fs.py`
- Test: `server/tests/db/test_graph_local_fs.py`

- [ ] **Step 1: Write failing LocalFs tests**

Create `server/tests/db/test_graph_local_fs.py`:

```python
import json
from pathlib import Path

import pytest

from src.db.graph_local_fs import LocalFsGraphRepo
from src.game.domain.graph import Graph, GraphEdge, GraphNode
from src.game.domain.progress import GameProgress
from src.game.domain.errors import PersistenceFailed


def _graph() -> Graph:
    return Graph(
        nodes={
            "player": GraphNode(id="player", type="character", properties={"name": "Player"}),
            "town": GraphNode(id="town", type="location", properties={"name": "Town"}),
        },
        edges={
            "located_at:player:town": GraphEdge(
                id="located_at:player:town",
                type="located_at",
                from_node_id="player",
                to_node_id="town",
            )
        },
    )


async def test_local_fs_graph_repo_round_trips_graph_and_progress(tmp_path):
    repo = LocalFsGraphRepo(str(tmp_path))
    graph = _graph()
    progress = GameProgress(game_id="game-1", player_id="player", turn_count=2)

    await repo.save_graph("game-1", graph)
    await repo.save_progress(progress)

    assert await repo.load_graph("game-1") == graph
    assert await repo.load_progress("game-1") == progress


async def test_local_fs_graph_repo_raises_for_missing_game(tmp_path):
    repo = LocalFsGraphRepo(str(tmp_path))

    with pytest.raises(FileNotFoundError):
        await repo.load_graph("missing")

    with pytest.raises(FileNotFoundError):
        await repo.load_progress("missing")


async def test_local_fs_graph_repo_wraps_invalid_graph(tmp_path):
    graph_dir = Path(tmp_path) / "games" / "game-1" / "graph"
    graph_dir.mkdir(parents=True)
    (graph_dir / "nodes.json").write_text(
        json.dumps([{"game_id": "game-1", "node_id": "player", "node_type": "character", "properties": {}}]),
        encoding="utf-8",
    )
    (graph_dir / "edges.json").write_text(
        json.dumps([
            {
                "game_id": "game-1",
                "edge_id": "located_at:player:void",
                "edge_type": "located_at",
                "from_node_id": "player",
                "to_node_id": "void",
                "properties": {},
            }
        ]),
        encoding="utf-8",
    )

    repo = LocalFsGraphRepo(str(tmp_path))

    with pytest.raises(PersistenceFailed, match="missing node"):
        await repo.load_graph("game-1")
```

- [ ] **Step 2: Run tests and confirm RED**

Run:

```powershell
& .\.venv\Scripts\python.exe -m pytest server\tests\db\test_graph_local_fs.py -q
```

Expected: fail because `src.db.graph_local_fs` does not exist.

- [ ] **Step 3: Implement LocalFs adapter**

Create `server/src/db/graph_local_fs.py`:

```python
from __future__ import annotations

import asyncio
import json
from pathlib import Path

from pydantic import ValidationError

from src.db.graph_progress_rows import GameProgressRow, progress_from_row, progress_to_row
from src.db.graph_rows import GraphEdgeRow, GraphNodeRow, graph_from_rows, graph_to_rows
from src.game.domain.errors import PersistenceFailed
from src.game.domain.graph import Graph
from src.game.domain.progress import GameProgress


class LocalFsGraphRepo:
    def __init__(self, saves_dir: str) -> None:
        self.saves_dir = saves_dir

    def _game_dir(self, game_id: str) -> Path:
        return Path(self.saves_dir) / "games" / game_id

    def _graph_dir(self, game_id: str) -> Path:
        return self._game_dir(game_id) / "graph"

    async def save_graph(self, game_id: str, graph: Graph) -> None:
        node_rows, edge_rows = graph_to_rows(game_id, graph)
        graph_dir = self._graph_dir(game_id)
        await asyncio.to_thread(graph_dir.mkdir, parents=True, exist_ok=True)
        await asyncio.to_thread(
            (graph_dir / "nodes.json").write_text,
            json.dumps([row.model_dump(mode="json") for row in node_rows], ensure_ascii=False),
            "utf-8",
        )
        await asyncio.to_thread(
            (graph_dir / "edges.json").write_text,
            json.dumps([row.model_dump(mode="json") for row in edge_rows], ensure_ascii=False),
            "utf-8",
        )

    async def load_graph(self, game_id: str) -> Graph:
        graph_dir = self._graph_dir(game_id)
        nodes_path = graph_dir / "nodes.json"
        edges_path = graph_dir / "edges.json"
        if not nodes_path.exists() or not edges_path.exists():
            raise FileNotFoundError(game_id)
        try:
            node_rows = [GraphNodeRow.model_validate(row) for row in json.loads(nodes_path.read_text(encoding="utf-8"))]
            edge_rows = [GraphEdgeRow.model_validate(row) for row in json.loads(edges_path.read_text(encoding="utf-8"))]
            return graph_from_rows(node_rows, edge_rows)
        except (ValidationError, OSError, json.JSONDecodeError, ValueError) as e:
            raise PersistenceFailed(str(e)) from e

    async def save_progress(self, progress: GameProgress) -> None:
        path = self._game_dir(progress.game_id) / "progress.json"
        row = progress_to_row(progress)
        await asyncio.to_thread(path.parent.mkdir, parents=True, exist_ok=True)
        await asyncio.to_thread(path.write_text, row.model_dump_json(), "utf-8")

    async def load_progress(self, game_id: str) -> GameProgress:
        path = self._game_dir(game_id) / "progress.json"
        if not path.exists():
            raise FileNotFoundError(game_id)
        try:
            return progress_from_row(GameProgressRow.model_validate_json(path.read_text(encoding="utf-8")))
        except (ValidationError, OSError, json.JSONDecodeError, ValueError) as e:
            raise PersistenceFailed(str(e)) from e
```

- [ ] **Step 4: Run tests and confirm GREEN**

Run:

```powershell
& .\.venv\Scripts\python.exe -m pytest server\tests\db\test_graph_local_fs.py -q
```

Expected: pass.

## Task 4: Supabase Delete Support

**Files:**
- Modify: `server/src/db/_supabase_http.py`
- Modify: `server/tests/_fakes.py`

- [ ] **Step 1: Add fake delete behavior first**

Modify `FakePostgREST` in `server/tests/_fakes.py`:

```python
    async def delete(self, table: str, *, filters: dict[str, str]) -> None:
        self.calls.append(("delete", table, filters))
        store_ = self.rows.get(table, [])
        out = list(store_)
        for col, expr in filters.items():
            assert expr.startswith("eq."), f"only eq supported in fake: {expr}"
            val = expr[3:]
            out = [r for r in out if str(r.get(col)) != val]
        self.rows[table] = out
```

- [ ] **Step 2: Add real PostgREST delete**

Modify `_PostgREST` in `server/src/db/_supabase_http.py`:

```python
    async def delete(self, table: str, *, filters: dict[str, str]) -> None:
        params: list[tuple[str, str]] = []
        for col, expr in filters.items():
            params.append((col, expr))
        url = f"{self._base}/{table}"
        r = await self._client.delete(url, headers=self._headers, params=params)
        if r.status_code >= 300:
            raise PersistenceFailed(f"delete {table}: {r.status_code} {r.text}")
```

This is used only by the new graph adapter.

## Task 5: Supabase GraphRepo

**Files:**
- Create: `server/src/db/graph_supabase.py`
- Test: `server/tests/db/test_graph_supabase.py`

- [ ] **Step 1: Write failing Supabase graph tests**

Create `server/tests/db/test_graph_supabase.py`:

```python
from src.db.graph_supabase import SupabaseGraphRepo
from src.game.domain.graph import Graph, GraphEdge, GraphNode
from src.game.domain.progress import GameProgress
from tests._fakes import FakePostgREST


def _repo(db: FakePostgREST | None = None) -> tuple[SupabaseGraphRepo, FakePostgREST]:
    repo = SupabaseGraphRepo.__new__(SupabaseGraphRepo)
    db = db or FakePostgREST()
    repo._db = db
    return repo, db


def _graph() -> Graph:
    return Graph(
        nodes={
            "player": GraphNode(id="player", type="character", properties={"name": "Player"}),
            "town": GraphNode(id="town", type="location", properties={"name": "Town"}),
        },
        edges={
            "located_at:player:town": GraphEdge(
                id="located_at:player:town",
                type="located_at",
                from_node_id="player",
                to_node_id="town",
            )
        },
    )


async def test_supabase_graph_repo_round_trips_graph_and_progress():
    repo, db = _repo()
    graph = _graph()
    progress = GameProgress(game_id="game-1", player_id="player", turn_count=4)

    await repo.save_graph("game-1", graph)
    await repo.save_progress(progress)

    assert await repo.load_graph("game-1") == graph
    assert await repo.load_progress("game-1") == progress

    assert "graph_nodes" in db.rows
    assert "graph_edges" in db.rows
    assert "game_progress" in db.rows


async def test_supabase_graph_repo_replace_save_removes_stale_rows():
    repo, db = _repo()
    await repo.save_graph("game-1", _graph())

    smaller = Graph(nodes={"town": GraphNode(id="town", type="location")})
    await repo.save_graph("game-1", smaller)

    assert await repo.load_graph("game-1") == smaller
    assert any(call[0] == "delete" and call[1] == "graph_edges" for call in db.calls)
    assert any(call[0] == "delete" and call[1] == "graph_nodes" for call in db.calls)


async def test_supabase_graph_repo_missing_rows_raise_filenotfound():
    repo, _ = _repo()

    try:
        await repo.load_graph("missing")
    except FileNotFoundError as e:
        assert str(e)
    else:
        raise AssertionError("expected FileNotFoundError")
```

- [ ] **Step 2: Run tests and confirm RED**

Run:

```powershell
& .\.venv\Scripts\python.exe -m pytest server\tests\db\test_graph_supabase.py -q
```

Expected: fail because `src.db.graph_supabase` does not exist.

- [ ] **Step 3: Implement Supabase adapter**

Create `server/src/db/graph_supabase.py`:

```python
from __future__ import annotations

from pydantic import ValidationError

from src.db._supabase_http import _PostgREST
from src.db.graph_progress_rows import GameProgressRow, progress_from_row, progress_to_row
from src.db.graph_rows import GraphEdgeRow, GraphNodeRow, graph_from_rows, graph_to_rows
from src.game.domain.errors import PersistenceFailed
from src.game.domain.graph import Graph
from src.game.domain.progress import GameProgress


class SupabaseGraphRepo:
    def __init__(self, *, url: str, service_key: str) -> None:
        self._db = _PostgREST(url, service_key)

    async def save_graph(self, game_id: str, graph: Graph) -> None:
        node_rows, edge_rows = graph_to_rows(game_id, graph)
        filters = {"game_id": f"eq.{game_id}"}
        await self._db.delete("graph_edges", filters=filters)
        await self._db.delete("graph_nodes", filters=filters)
        await self._db.upsert(
            "graph_nodes",
            [row.model_dump(mode="json") for row in node_rows],
            on_conflict="game_id,node_id",
        )
        await self._db.upsert(
            "graph_edges",
            [row.model_dump(mode="json") for row in edge_rows],
            on_conflict="game_id,edge_id",
        )

    async def load_graph(self, game_id: str) -> Graph:
        try:
            node_data = await self._db.select(
                "graph_nodes",
                filters={"game_id": f"eq.{game_id}"},
                select="game_id,node_id,node_type,properties",
            )
            edge_data = await self._db.select(
                "graph_edges",
                filters={"game_id": f"eq.{game_id}"},
                select="game_id,edge_id,edge_type,from_node_id,to_node_id,properties",
            )
            if not node_data:
                raise FileNotFoundError(game_id)
            node_rows = [GraphNodeRow.model_validate(row) for row in node_data]
            edge_rows = [GraphEdgeRow.model_validate(row) for row in edge_data]
            return graph_from_rows(node_rows, edge_rows)
        except ValidationError as e:
            raise PersistenceFailed(str(e)) from e

    async def save_progress(self, progress: GameProgress) -> None:
        row = progress_to_row(progress)
        await self._db.upsert(
            "game_progress",
            [row.model_dump(mode="json")],
            on_conflict="game_id",
        )

    async def load_progress(self, game_id: str) -> GameProgress:
        row = await self._db.select_one(
            "game_progress",
            filters={"game_id": f"eq.{game_id}"},
            select="game_id,progress",
        )
        if row is None:
            raise FileNotFoundError(game_id)
        try:
            return progress_from_row(GameProgressRow.model_validate(row))
        except ValidationError as e:
            raise PersistenceFailed(str(e)) from e
```

- [ ] **Step 4: Run tests and confirm GREEN**

Run:

```powershell
& .\.venv\Scripts\python.exe -m pytest server\tests\db\test_graph_supabase.py -q
```

Expected: pass.

## Task 6: SQL Reference

**Files:**
- Create: `docs/supabase/graph_tables.sql`

- [ ] **Step 1: Add graph table SQL**

Create `docs/supabase/graph_tables.sql`:

```sql
create table if not exists graph_nodes (
  game_id text not null,
  node_id text not null,
  node_type text not null,
  properties jsonb not null default '{}'::jsonb,
  primary key (game_id, node_id)
);

create table if not exists graph_edges (
  game_id text not null,
  edge_id text not null,
  edge_type text not null,
  from_node_id text not null,
  to_node_id text not null,
  properties jsonb not null default '{}'::jsonb,
  primary key (game_id, edge_id),
  foreign key (game_id, from_node_id) references graph_nodes(game_id, node_id) on delete cascade,
  foreign key (game_id, to_node_id) references graph_nodes(game_id, node_id) on delete cascade
);

create table if not exists game_progress (
  game_id text primary key,
  progress jsonb not null default '{}'::jsonb
);

create index if not exists graph_nodes_game_type_idx
  on graph_nodes(game_id, node_type);

create index if not exists graph_edges_game_type_idx
  on graph_edges(game_id, edge_type);

create index if not exists graph_edges_game_from_type_idx
  on graph_edges(game_id, from_node_id, edge_type);

create index if not exists graph_edges_game_to_type_idx
  on graph_edges(game_id, to_node_id, edge_type);
```

This file is a schema reference. Applying it to a real Supabase project is a separate operational step.

## Task 7: Verification

**Files:**
- No new files.

- [ ] **Step 1: Run graph persistence tests**

Run:

```powershell
& .\.venv\Scripts\python.exe -m pytest server\tests\db\test_graph_rows.py server\tests\db\test_graph_progress_rows.py server\tests\db\test_graph_local_fs.py server\tests\db\test_graph_supabase.py -q
```

Expected: pass.

- [ ] **Step 2: Run graph domain and ontology tests**

Run:

```powershell
& .\.venv\Scripts\python.exe -m pytest server\tests\game\domain server\tests\game\ontology -q
```

Expected: pass.

- [ ] **Step 3: Run Ruff**

Run:

```powershell
& .\.venv\Scripts\python.exe -m ruff check server\src\game\domain\progress.py server\src\db\graph_progress_rows.py server\src\db\graph_local_fs.py server\src\db\graph_supabase.py server\src\db\_supabase_http.py server\tests\db\test_graph_progress_rows.py server\tests\db\test_graph_local_fs.py server\tests\db\test_graph_supabase.py server\tests\_fakes.py
```

Expected: `All checks passed!`

- [ ] **Step 4: Run full server tests**

Run:

```powershell
& .\.venv\Scripts\python.exe -m pytest -q
```

Expected: pass.

## Stop Point

Stop after Phase 1 unless the user explicitly says to continue into Phase 2.

Phase 2 changes game creation and seed interpretation, so it needs a fresh implementation plan.
