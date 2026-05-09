# Runtime Envelope Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Use superpowers:test-driven-development for every production change. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a graph-first runtime envelope that loads `Graph`, `GameProgress`, and recent log/history/dialogue tails without loading legacy entity tables.

**Architecture:** Keep graph facts in `Graph` and request-continuation fields in `GameProgress`. Store log/history/dialogue as append-only tails outside graph facts. Provide a one-way compatibility converter from graph runtime to legacy `GameState` so old engines can be migrated one at a time.

**Tech Stack:** Python 3.12+, Pydantic v2, pytest, Ruff, root `.venv` on Windows.

---

## Scope

This plan implements Phase 3 from `2026-05-09-graph-first-game-roadmap.md`.

It does not migrate `/turn`, engine mutation, LLM context, or client wire mapping. It only creates a runtime object and a compatibility adapter.

## File Structure

- `server/src/game/runtime/__init__.py`
  - Exports runtime model, loader, and legacy converter.
- `server/src/game/runtime/state.py`
  - Defines `GameRuntimeState`.
- `server/src/game/runtime/load.py`
  - Loads graph, progress, log entries, history entries, and dialogue entries from `GraphRepo`.
- `server/src/game/runtime/legacy.py`
  - Converts `GameRuntimeState` to legacy `GameState`.
- `server/src/db/repo.py`
  - Extends `GraphRepo` with append/load methods for log/history/dialogue tails.
- `server/src/db/graph_local_fs.py`
  - Implements graph runtime log tail methods over existing JSONL files.
- `server/src/db/graph_supabase.py`
  - Implements graph runtime log tail methods over existing Supabase log tables.
- `server/tests/game/runtime/test_load.py`
  - Tests runtime load and progress survival.
- `server/tests/game/runtime/test_legacy.py`
  - Tests graph runtime to legacy `GameState` conversion.
- `server/tests/db/test_graph_supabase.py`
  - Adds Supabase graph log tail tests.

## Task 1: Runtime Model And Loader

**Files:**
- Create: `server/src/game/runtime/__init__.py`
- Create: `server/src/game/runtime/state.py`
- Create: `server/src/game/runtime/load.py`
- Modify: `server/src/db/repo.py`
- Modify: `server/src/db/graph_local_fs.py`
- Test: `server/tests/game/runtime/test_load.py`

- [x] **Step 1: Write failing runtime load tests**

Create tests that save a graph and progress with `LocalFsGraphRepo`, append one entry to each log tail, and call `load_runtime_state(repo, game_id)`.

The test must assert:

- `runtime.graph` equals the saved graph.
- `runtime.progress.pending_confirmation` survives reload.
- `runtime.progress.combat_state` survives reload.
- `runtime.log_entries`, `runtime.turn_log`, and `runtime.recent_dialogue` are loaded.
- `runtime.progress.next_log_id` is bumped past the largest loaded log id.

Expected RED: `src.game.runtime` import fails or `GraphRepo` lacks load tail methods.

- [x] **Step 2: Implement runtime state**

`GameRuntimeState` contains:

```python
class GameRuntimeState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    graph: Graph
    progress: GameProgress
    log_entries: list[LogEntry] = Field(default_factory=list)
    turn_log: list[TurnLogEntry] = Field(default_factory=list)
    recent_dialogue: list[DialoguePair] = Field(default_factory=list)
```

- [x] **Step 3: Extend graph repo boundary**

Add these methods to `GraphRepo`:

```python
async def append_log_entries(self, game_id: str, entries: list[LogEntry]) -> None: ...
async def append_history_entries(self, game_id: str, entries: list[TurnLogEntry]) -> None: ...
async def append_dialogue_entries(self, game_id: str, entries: list[DialoguePair]) -> None: ...
async def load_log_entries(self, game_id: str) -> list[LogEntry]: ...
async def load_history_entries(self, game_id: str) -> list[TurnLogEntry]: ...
async def load_dialogue_entries(self, game_id: str) -> list[DialoguePair]: ...
```

- [x] **Step 4: Implement LocalFs graph tail methods**

Reuse the same JSONL paths and caps as legacy `store.load_game`. Do not read entity folders.

- [x] **Step 5: Implement runtime loader**

`load_runtime_state(repo, game_id)` gathers graph, progress, and tails. It returns `GameRuntimeState` and applies `_resolve_next_log_id` to the loaded progress copy.

- [x] **Step 6: Run runtime load tests**

Run:

```powershell
& .\.venv\Scripts\python.exe -m pytest server\tests\game\runtime\test_load.py -q
```

Expected: pass.

## Task 2: Supabase Runtime Tails

**Files:**
- Modify: `server/src/db/graph_supabase.py`
- Modify: `server/tests/db/test_graph_supabase.py`

- [x] **Step 1: Write failing Supabase tail tests**

Add a test to `server/tests/db/test_graph_supabase.py` that appends log/history/dialogue entries through `SupabaseGraphRepo`, then loads each tail and verifies chronological order.

Expected RED: `SupabaseGraphRepo` lacks the new methods.

- [x] **Step 2: Implement Supabase graph tail methods**

Use the same table names and row shapes as `SupabaseSaveRepo`:

- `log_entries`: `game_id`, `log_id`, `entry`
- `history_entries`: `game_id`, auto `seq`, `entry`
- `dialogue_entries`: `game_id`, auto `seq`, `entry`

Load tails in descending DB order, then reverse them to chronological order.

- [x] **Step 3: Run Supabase graph tests**

Run:

```powershell
& .\.venv\Scripts\python.exe -m pytest server\tests\db\test_graph_supabase.py -q
```

Expected: pass.

## Task 3: Legacy Compatibility Converter

**Files:**
- Create: `server/src/game/runtime/legacy.py`
- Test: `server/tests/game/runtime/test_legacy.py`

- [x] **Step 1: Write failing converter tests**

Create a graph with character, item, location, race, skill, quest, and chapter nodes plus edges for location, inventory, equipment, race, skills, quest giver, target, reward, and chapter membership. Wrap it in `GameRuntimeState`, convert with `runtime_to_legacy_state(runtime, profile_name="default")`, then assert legacy fields are restored.

The test must assert:

- `GameState.characters[player].location_id` comes from `located_at`.
- inventory and equipment come from `carries` and `equips`.
- race skills come from `grants_skill` and `knows_skill`.
- quest giver, triggers, rewards, and chapter quest ids come from edges.
- pending/combat/log fields come from `GameProgress` and runtime tails.

Expected RED: `src.game.runtime.legacy` import fails.

- [x] **Step 2: Implement converter**

Convert node properties back into existing Pydantic entity models, then patch relationship fields from edges. Require `profile_name` as an argument because profile metadata is not a graph fact.

- [x] **Step 3: Run converter tests**

Run:

```powershell
& .\.venv\Scripts\python.exe -m pytest server\tests\game\runtime\test_legacy.py -q
```

Expected: pass.

## Task 4: Documentation And Verification

**Files:**
- Modify: `docs/superpowers/plans/2026-05-09-graph-first-game-roadmap.md`
- Modify: `docs/superpowers/plans/2026-05-09-runtime-envelope.md`

- [x] **Step 1: Mark Phase 3 status**

Update the roadmap so Phase 3 says the runtime envelope exists, but `/turn` is still legacy.

- [x] **Step 2: Run focused tests**

Run:

```powershell
& .\.venv\Scripts\python.exe -m pytest server\tests\game\runtime server\tests\db\test_graph_local_fs.py server\tests\db\test_graph_supabase.py -q
```

Expected: pass.

- [x] **Step 3: Run Ruff on touched files**

Run:

```powershell
& .\.venv\Scripts\python.exe -m ruff check server\src\game\runtime server\src\db\repo.py server\src\db\graph_local_fs.py server\src\db\graph_supabase.py server\tests\game\runtime server\tests\db\test_graph_supabase.py
```

Expected: `All checks passed!`

- [x] **Step 4: Run full server tests**

Run:

```powershell
& .\.venv\Scripts\python.exe -m pytest -q
```

Expected: pass.

## Stop Point

After Phase 3, graph saves can be loaded as a runtime envelope and temporarily converted to legacy `GameState`. Phase 4 should start the action and confirmation contract; that is where player input behavior begins to change.
