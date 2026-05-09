# Graph View Id Validation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reject classify actions that reference ids outside the current `surroundings` view.

**Architecture:** Add a classify grounding validator that runs after JSON/schema validation and before `classify()` returns. The validator uses the same `surroundings` payload the LLM saw, so it is a graph-view guard rather than another legacy-state scan. Invalid ids raise a retryable grounding error so weak LLMs get a self-correction attempt.

**Tech Stack:** Python 3.12+, Pydantic v2, pytest, Ruff, root `.venv` on Windows.

---

## Scope

This slice validates ids that are already exposed in the current view:

- move destinations must be visible connection ids,
- use item ids must be in player inventory,
- attack targets must be visible non-player character ids,
- cast skill ids must be visible skill ids,
- speak targets must be visible non-player character ids,
- transfer refs must be visible character ids or accepted self refs,
- transfer item ids, when present, must be exposed through inventory, equipment, merchant stock, carryables, corpse inventory, or location items.

It does not add the final graph-native `Action` schema or query-only dispatch.

## File Structure

- `server/src/llm/calls/classify/grounding.py`
  - New view-based id validator and retryable error type.
- `server/src/llm/calls/classify/runner.py`
  - Run grounding after schema validation and include the new error in retry handling.
- `server/tests/llm/calls/test_classify_grounding.py`
  - Unit tests for validator behavior.
- `server/tests/llm/calls/test_classify_in_combat_plumbing.py`
  - Add one runner-level test that parse rejects unknown ids.
- `docs/superpowers/plans/2026-05-09-graph-first-game-roadmap.md`
  - Mark graph-view id validation as live after verification.

## Task 1: Validator Tests

**Files:**
- Create: `server/tests/llm/calls/test_classify_grounding.py`

- [x] **Step 1: Write failing validator tests**

Add tests that assert:

- valid move/use/attack/cast/speak/transfer ids pass,
- unknown move destination fails,
- unknown use item fails,
- player self-target attack fails,
- transfer accepts self refs such as `<self>.inventory` and `<self>.equipped.weapon`.

Run:

```powershell
& .\.venv\Scripts\python.exe -m pytest server\tests\llm\calls\test_classify_grounding.py -q
```

Expected RED: `classify.grounding` does not exist.

## Task 2: Grounding Validator

**Files:**
- Create: `server/src/llm/calls/classify/grounding.py`

- [x] **Step 1: Implement view id collection**

Collect ids from `surroundings` into small sets: connection ids, inventory item ids, equipment item ids, visible item ids, skill ids, character ids, non-player character ids, merchant stock item ids, carryable item ids, and corpse inventory item ids.

- [x] **Step 2: Implement verb validation**

Validate every `Verb` in `JudgeOutput.actions`. `JudgeOutput.refuse` requires no id validation.

- [x] **Step 3: Run validator tests**

Run:

```powershell
& .\.venv\Scripts\python.exe -m pytest server\tests\llm\calls\test_classify_grounding.py -q
```

Expected GREEN: validator tests pass.

## Task 3: Runner Integration

**Files:**
- Modify: `server/src/llm/calls/classify/runner.py`
- Modify: `server/tests/llm/calls/test_classify_in_combat_plumbing.py`

- [x] **Step 1: Add failing runner test**

Add a test that patches `run_with_retries` and proves `classify()` parse rejects an unknown move destination against the supplied `surroundings`.

- [x] **Step 2: Integrate validator**

In `classify()`, call the grounding validator inside the `parse` callback after `validate_judge_output`.

Include the grounding error in `retry_on` so the real retry loop can ask the LLM to correct invented ids.

- [x] **Step 3: Run classify tests**

Run:

```powershell
& .\.venv\Scripts\python.exe -m pytest server\tests\llm\calls\test_classify_grounding.py server\tests\llm\calls\test_classify_in_combat_plumbing.py server\tests\llm\calls\test_classify_runner_retry.py -q
```

Expected: pass.

## Task 4: Verification And Docs

**Files:**
- Modify: `docs/superpowers/plans/2026-05-09-graph-first-game-roadmap.md`
- Modify: `docs/superpowers/plans/2026-05-09-graph-view-id-validation.md`

- [x] **Step 1: Update roadmap**

Mark graph-view id validation as live. Leave final graph-native `Action` and query-only dispatch as remaining Phase 4 work.

- [x] **Step 2: Run Ruff**

Run:

```powershell
& .\.venv\Scripts\python.exe -m ruff check server\src\llm\calls\classify server\tests\llm\calls\test_classify_grounding.py server\tests\llm\calls\test_classify_in_combat_plumbing.py
```

Expected: `All checks passed!`

- [x] **Step 3: Run full server tests**

Run:

```powershell
& .\.venv\Scripts\python.exe -m pytest -q
```

Expected: pass.

## Stop Point

After this slice, classify output cannot reference ids outside the current graph-derived view. Phase 4 still needs the final graph-native `Action` schema and query-only dispatch.
