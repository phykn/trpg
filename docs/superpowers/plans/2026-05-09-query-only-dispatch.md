# Query-Only Dispatch Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a real `query` verb that answers current public information without advancing time or mutating game facts.

**Architecture:** Extend the existing legacy `Verb` bridge with `query` as a temporary Phase 4 slice. `query` must be a single action, not part of a chain. Dispatch answers from the graph-derived `surroundings` view and finalizes logs/state without calling narrate, changing graph facts, ticking buffs, or incrementing `turn_count`.

**Tech Stack:** Python 3.12+, Pydantic v2, pytest, Ruff, root `.venv` on Windows.

---

## Scope

Supported query topics for this slice:

- `surroundings`
- `exits`
- `inventory`
- `quests`
- `status`

If the LLM omits `topic`, use `surroundings`.

This does not add the final graph-native `Action` schema. It keeps the legacy `Verb` bridge while making the documented query behavior real.

## File Structure

- `server/src/game/domain/verb.py`
  - Add `query` to the verb catalog and reject query chains.
- `server/src/game/flow/query.py`
  - New query response builder and dispatch helper.
- `server/src/game/flow/dispatch.py`
  - Route `query` to `run_query`.
- `server/src/llm/calls/classify/grounding.py`
  - Treat `query` as id-free unless future schema adds targets.
- `server/src/locale/prompts/classify/prompt.ko.md`
  - Teach classify when to emit `query`.
- `server/tests/llm/calls/test_classify_modifier_schemas.py`
  - Add schema tests for query.
- `server/tests/llm/calls/test_classify_validate_judge_output.py`
  - Add query-chain rejection test.
- `server/tests/game/flow/test_query.py`
  - Add flow tests for no time change and public responses.
- `docs/superpowers/plans/2026-05-09-graph-first-game-roadmap.md`
  - Mark query-only dispatch as live after verification.

## Task 1: Query Schema Tests

**Files:**
- Modify: `server/tests/llm/calls/test_classify_modifier_schemas.py`
- Modify: `server/tests/llm/calls/test_classify_validate_judge_output.py`

- [x] **Step 1: Write failing schema tests**

Add tests that assert:

- `query` is in `_MODIFIER_SCHEMAS`,
- `query` accepts no modifiers and optional `topic`,
- unknown query topic is rejected,
- `JudgeOutput(actions=[query, wait])` is rejected.

Run:

```powershell
& .\.venv\Scripts\python.exe -m pytest server\tests\llm\calls\test_classify_modifier_schemas.py server\tests\llm\calls\test_classify_validate_judge_output.py -q
```

Expected RED: `query` is not a valid verb.

## Task 2: Query Flow Tests

**Files:**
- Create: `server/tests/game/flow/test_query.py`

- [x] **Step 1: Write failing flow tests**

Add tests that assert:

- `query(topic="exits")` emits a GM log containing visible connection names,
- `query` does not increment `turn_count`,
- `query` does not create pending confirmation or pending check,
- `query(topic="inventory")` only answers from player inventory.

Run:

```powershell
& .\.venv\Scripts\python.exe -m pytest server\tests\game\flow\test_query.py -q
```

Expected RED: `query` is not dispatchable.

## Task 3: Implement Query

**Files:**
- Modify: `server/src/game/domain/verb.py`
- Create: `server/src/game/flow/query.py`
- Modify: `server/src/game/flow/dispatch.py`
- Modify: `server/src/llm/calls/classify/grounding.py`
- Modify: `server/src/locale/prompts/classify/prompt.ko.md`

- [x] **Step 1: Add schema support**

Add `query` to `VerbName` and `_MODIFIER_SCHEMAS` with optional enum `topic`.

Reject query chains in `JudgeOutput`.

- [x] **Step 2: Add query dispatch**

Create `run_query` that:

- builds the response from `build_surroundings`,
- pushes a GM log entry,
- finalizes without incrementing `turn_count`,
- does not tick buffs,
- does not call narrate.

- [x] **Step 3: Update prompt**

Add `query` to the classify prompt catalog and examples.

- [x] **Step 4: Run query tests**

Run:

```powershell
& .\.venv\Scripts\python.exe -m pytest server\tests\llm\calls\test_classify_modifier_schemas.py server\tests\llm\calls\test_classify_validate_judge_output.py server\tests\game\flow\test_query.py -q
```

Expected GREEN: query schema and flow tests pass.

## Task 4: Verification And Docs

**Files:**
- Modify: `docs/superpowers/plans/2026-05-09-graph-first-game-roadmap.md`
- Modify: `docs/superpowers/plans/2026-05-09-query-only-dispatch.md`

- [x] **Step 1: Update roadmap**

Mark query-only dispatch as live. Leave final graph-native `Action` as the remaining Phase 4 work.

- [x] **Step 2: Run focused tests**

Run:

```powershell
& .\.venv\Scripts\python.exe -m pytest server\tests\llm\calls\test_classify_modifier_schemas.py server\tests\llm\calls\test_classify_validate_judge_output.py server\tests\llm\calls\test_classify_grounding.py server\tests\game\flow\test_query.py -q
```

Expected: pass.

- [x] **Step 3: Run Ruff**

Run:

```powershell
& .\.venv\Scripts\python.exe -m ruff check server\src\game\domain\verb.py server\src\game\flow\query.py server\src\game\flow\dispatch.py server\src\llm\calls\classify server\tests\llm\calls\test_classify_modifier_schemas.py server\tests\llm\calls\test_classify_validate_judge_output.py server\tests\game\flow\test_query.py
```

Expected: `All checks passed!`

- [x] **Step 4: Run full server tests**

Run:

```powershell
& .\.venv\Scripts\python.exe -m pytest -q
```

Expected: pass.

## Stop Point

After this slice, Phase 4 has confirmation, classify id grounding, and query-only dispatch. The remaining Phase 4 work is the final graph-native `Action` schema.
