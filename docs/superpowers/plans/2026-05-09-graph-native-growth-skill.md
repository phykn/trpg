# Graph-Native Growth And Skill Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add graph-native planners for XP grants, level-up stat pair trades, and skill learning.

**Architecture:** Keep this slice on the current 6-stat model because the 4-stat redesign is a later phase. The new planner reads character and skill graph nodes, emits `GraphChange` objects for character properties and `knows_skill` edges, and leaves live flow wiring for a later integration pass.

**Tech Stack:** Python 3.12+, Pydantic v2, pytest, Ruff, root `.venv` on Windows.

---

## Scope

This slice covers:

- adding XP to a character,
- level-up with the existing pair-trade rule,
- learning an existing skill through a `knows_skill` edge.

It does not cast skills, generate new skills, change the 6-stat model, or wire live `/turn`.

## File Structure

- `server/src/game/engines/graph_growth.py`
  - New pure graph growth and skill learning planner.
- `server/tests/game/engines/test_graph_growth.py`
  - Unit tests for XP grants, level-up changes, invalid level-up states, and skill learning edges.
- `docs/superpowers/plans/2026-05-09-graph-first-game-roadmap.md`
  - Record that graph-native growth and skill learning planning exists.

## Task 1: Growth Tests

**Files:**
- Create: `server/tests/game/engines/test_graph_growth.py`

- [x] **Step 1: Write failing graph growth tests**

Create tests that assert:

- XP grant increments `xp_pool`,
- level-up deducts XP, increases `level`, applies stat pair trade, and recalculates max HP/MP,
- level-up rejects insufficient XP,
- level-up rejects invalid capped stat trades,
- skill learning adds `knows_skill:learned:<character_id>:<skill_id>`,
- duplicate learned skill raises `GraphGrowthError`,
- every emitted change can be applied one by one with `apply_graph_change`.

- [x] **Step 2: Run tests to verify RED**

Run:

```powershell
& .\.venv\Scripts\python.exe -m pytest server\tests\game\engines\test_graph_growth.py -q
```

Expected RED: `src.game.engines.graph_growth` does not exist.

## Task 2: Growth Planner

**Files:**
- Create: `server/src/game/engines/graph_growth.py`

- [x] **Step 1: Implement growth planner**

Implement:

- `GraphGrowthError(ValueError)`
- `GraphGrowthResult(BaseModel)`
- `plan_xp_grant(graph, character_id, amount)`
- `plan_level_up(graph, character_id, stat_up)`
- `plan_skill_learn(graph, character_id, skill_id)`

Rules:

- character id must resolve to a character node,
- XP grants must be non-negative,
- level-up uses `xp_for_next_level(level)` and `STAT_PAIRS`,
- level-up writes `xp_pool`, `level`, `stats.<up>`, `stats.<down>`, `max_hp`, `max_mp`, `hp`, and `mp`,
- skill id must resolve to a skill node,
- duplicate `knows_skill` edges reject,
- learned skill edge id is `knows_skill:learned:<character_id>:<skill_id>` with `{"source": "learned"}`.

- [x] **Step 2: Run graph growth tests**

Run:

```powershell
& .\.venv\Scripts\python.exe -m pytest server\tests\game\engines\test_graph_growth.py -q
```

Expected GREEN: graph growth tests pass.

## Task 3: Roadmap And Verification

**Files:**
- Modify: `docs/superpowers/plans/2026-05-09-graph-first-game-roadmap.md`
- Modify: `docs/superpowers/plans/2026-05-09-graph-native-growth-skill.md`

- [x] **Step 1: Update roadmap**

Add one current-state bullet:

```markdown
- `server/src/game/engines/graph_growth.py` plans graph-native XP, level-up, and skill-learning changes.
```

- [x] **Step 2: Run focused tests**

Run:

```powershell
& .\.venv\Scripts\python.exe -m pytest server\tests\game\engines\test_graph_growth.py server\tests\game\domain\test_graph_contract.py -q
```

Expected: pass.

- [x] **Step 3: Run Ruff**

Run:

```powershell
& .\.venv\Scripts\python.exe -m ruff check server\src\game\engines\graph_growth.py server\tests\game\engines\test_graph_growth.py
```

Expected: `All checks passed!`

- [x] **Step 4: Run full server tests**

Run:

```powershell
& .\.venv\Scripts\python.exe -m pytest -q
```

Expected: pass.

## Stop Point

After this slice, Phase 5 covers every non-combat planner except live-flow integration. The next slice should either start graph-native combat planning or wire one low-risk action path to the graph runtime.
