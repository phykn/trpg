# Graph Combat Context Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an LLM-safe graph combat context that exposes combat state words without leaking HP, MP, damage, or graph changes.

**Architecture:** Add a pure context builder under `llm/context`. It reads `Graph` plus `GraphCombatState` and returns Pydantic models that contain only public participant identity, side, resource state words, outcome, round, and trace events. It does not call the LLM or mutate graph/runtime state.

**Tech Stack:** Python 3.12+, Pydantic v2, pytest, Ruff, root `.venv` on Windows.

---

## Scope

This slice prepares graph-native combat narration input.

It includes:

- participant views with id, name, side, HP state, MP state, and defeat mode,
- trace views copied from `GraphCombatState.trace`,
- schema-level exclusion of raw HP keys, MP keys, max values, damage, and `GraphChange`,
- resource state helpers that match `docs/04-gameplay.md`.

It does not include:

- streaming `combat_narrate`,
- live `/turn` integration,
- localized prose,
- client combat panels.

## File Structure

- `server/src/llm/context/graph_combat.py`
  - New graph combat context builder and Pydantic public-view models.
- `server/src/game/domain/combat.py`
  - Shared graph combat progress models consumed by engine and context.
- `server/tests/llm/context/test_graph_combat_context.py`
  - Unit tests proving no raw combat numbers leak.
- `docs/superpowers/plans/2026-05-09-graph-first-game-roadmap.md`
  - Record that graph combat context exists.

## Task 1: Context Tests

**Files:**
- Create: `server/tests/llm/context/test_graph_combat_context.py`

- [x] **Step 1: Write failing context tests**

Create tests that:

- build a graph combat start state,
- run one attack exchange,
- apply its graph changes,
- call `build_graph_combat_context`,
- assert participant views include `hp_state` and `mp_state`,
- assert serialized context does not contain raw keys `hp`, `max_hp`, `mp`, `max_mp`, `damage`, or `changes`,
- assert HP state thresholds are `healthy`, `hurt`, `critical`, `downed`,
- assert MP state thresholds are `ready`, `strained`, `drained`.

- [x] **Step 2: Run tests to verify RED**

Run:

```powershell
& .\.venv\Scripts\python.exe -m pytest server\tests\llm\context\test_graph_combat_context.py -q
```

Expected RED: `src.llm.context.graph_combat` does not exist.

## Task 2: Context Builder

**Files:**
- Create: `server/src/llm/context/graph_combat.py`

- [x] **Step 1: Implement public models and builder**

Implement:

```python
class GraphCombatContextError(ValueError): ...
class GraphCombatParticipantView(BaseModel): ...
class GraphCombatTraceView(BaseModel): ...
class GraphCombatContext(BaseModel): ...
def hp_state(current: int, maximum: int) -> Literal["healthy", "hurt", "critical", "downed"]: ...
def mp_state(current: int, maximum: int) -> Literal["ready", "strained", "drained"]: ...
def build_graph_combat_context(graph: Graph, state: GraphCombatState) -> GraphCombatContext: ...
```

Rules:

- participant node must exist and be a character,
- `name` falls back to id,
- HP state uses the same thresholds as graph combat planner,
- MP state returns `drained` at zero or below 20%, `strained` at 50% or below, otherwise `ready`,
- trace views include only kind, actor id, target id, and state word.

- [x] **Step 2: Run context tests**

Run:

```powershell
& .\.venv\Scripts\python.exe -m pytest server\tests\llm\context\test_graph_combat_context.py -q
```

Expected GREEN: context tests pass.

## Task 3: Verification

**Files:**
- Modify: `docs/superpowers/plans/2026-05-09-graph-combat-context.md`
- Modify: `docs/superpowers/plans/2026-05-09-graph-first-game-roadmap.md`

- [x] **Step 1: Update roadmap**

Add one current-state bullet:

```markdown
- `server/src/llm/context/graph_combat.py` builds LLM-safe graph combat context without raw HP/MP/damage.
```

- [x] **Step 2: Run focused tests**

Run:

```powershell
& .\.venv\Scripts\python.exe -m pytest server\tests\llm\context\test_graph_combat_context.py server\tests\game\engines\test_graph_combat.py -q
```

Expected: pass.

- [x] **Step 3: Run Ruff**

Run:

```powershell
& .\.venv\Scripts\python.exe -m ruff check server\src\llm\context\graph_combat.py server\tests\llm\context\test_graph_combat_context.py
```

Expected: `All checks passed!`

- [x] **Step 4: Run full server tests**

Run:

```powershell
& .\.venv\Scripts\python.exe -m pytest -q
```

Expected: pass.

## Stop Point

After this slice, graph combat has a safe context boundary. The next useful slice is graph runtime dispatch, because planners and LLM-safe output will both exist.
