# Action Confirmation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Use superpowers:test-driven-development for every production change. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add explicit pending confirmation before high-impact actions so quest accept, quest abandon, attack-start, steal, dangerous rest, and dangerous item use no longer execute immediately.

**Architecture:** Use the existing legacy `Verb` path as the live bridge for this phase. Store a pending confirmation in `GameState` meta, expose a safe `pendingConfirmation` wire payload without raw action data, and add `/confirm` to either cancel or resume the stored engine action.

**Tech Stack:** Python 3.12+, Pydantic v2, FastAPI, pytest, Ruff, root `.venv` on Windows.

---

## Scope

This plan implements the first live slice of Phase 4 from `2026-05-09-graph-first-game-roadmap.md`, plus dangerous-rest and dangerous item-use confirmation using the same server contract.

It does not replace classify with the final graph-native `Action` schema, migrate all dispatch to graph changes, or update the client UI. It creates the server contract the UI can use.

## File Structure

- `server/src/game/domain/state.py`
  - Add `pending_confirmation`.
- `server/src/db/_schema.py`
  - Persist `pending_confirmation` in legacy meta during migration.
- `server/src/game/flow/confirmation.py`
  - Build pending confirmation payloads and implement confirm/cancel resume.
- `server/src/game/flow/turn.py`
  - Block new turns while confirmation is pending.
  - Create confirmation before quest actions, attack-start, and steal.
- `server/src/wire/models/pending_confirmation.py`
  - Wire-safe confirmation payload.
- `server/src/wire/emit.py`
  - Add `confirmation_required` SSE event.
- `server/src/wire/to_front.py`
  - Add `pendingConfirmation` to state payload.
- `server/src/api/schema.py`
  - Add `ConfirmRequest`.
- `server/src/api/routes/session.py`
  - Add `POST /session/{game_id}/confirm`.
- `server/tests/game/flow/test_confirmation.py`
  - New live confirmation behavior tests.
- `server/tests/game/flow/test_quest_action_button_only.py`
  - Update old auto-accept expectations.

## Task 1: Confirmation State And Wire

**Files:**
- Modify: `server/src/game/domain/state.py`
- Modify: `server/src/db/_schema.py`
- Create: `server/src/wire/models/pending_confirmation.py`
- Modify: `server/src/wire/models/__init__.py`
- Modify: `server/src/wire/emit.py`
- Modify: `server/src/wire/to_front.py`
- Test: `server/tests/game/flow/test_confirmation.py`

- [x] **Step 1: Write failing wire/meta tests**

Create tests that put a pending confirmation dict on `GameState`, call `to_front_state`, and assert:

- `pendingConfirmation.kind` is visible,
- `pendingConfirmation.payload` is not visible,
- meta round-trip preserves `pending_confirmation`.

Expected RED: `pendingConfirmation` is missing and meta does not persist the field.

- [x] **Step 2: Implement state/meta/wire**

Add `pending_confirmation: dict[str, object] | None = None` to `GameState` and `_Meta`. Emit only these keys to the client:

- `id`
- `kind`
- `title`
- `body`
- `confirm_label`
- `cancel_label`
- `target_label`

- [x] **Step 3: Run tests**

Run:

```powershell
& .\.venv\Scripts\python.exe -m pytest server\tests\game\flow\test_confirmation.py -q
```

Expected: pass for Task 1 tests.

## Task 2: Quest Confirmation

**Files:**
- Create: `server/src/game/flow/confirmation.py`
- Modify: `server/src/game/flow/turn.py`
- Modify: `server/src/api/schema.py`
- Modify: `server/src/api/routes/session.py`
- Test: `server/tests/game/flow/test_confirmation.py`
- Test: `server/tests/game/flow/test_quest_action_button_only.py`

- [x] **Step 1: Write failing quest confirmation tests**

Tests must assert:

- `quest_action=("accept", qid)` creates pending confirmation and leaves quest status unchanged.
- cancel clears pending confirmation and leaves quest status unchanged.
- confirm accepts the quest and clears pending confirmation.
- a new `/turn` while pending raises `PendingConfirmationActive`.

Expected RED: quest action still mutates immediately and `/confirm` does not exist.

- [x] **Step 2: Implement quest confirmation**

Add `run_confirm(...)` and route `/confirm`. Quest confirmation payload is internal; `to_front_state` must not expose it.

- [x] **Step 3: Run quest tests**

Run:

```powershell
& .\.venv\Scripts\python.exe -m pytest server\tests\game\flow\test_confirmation.py server\tests\game\flow\test_quest_action_button_only.py -q
```

Expected: pass.

## Task 3: Attack, Steal, Dangerous Rest, And Dangerous Use Confirmation

**Files:**
- Modify: `server/src/game/flow/turn.py`
- Modify: `server/src/game/flow/confirmation.py`
- Test: `server/tests/game/flow/test_confirmation.py`

- [x] **Step 1: Write failing attack/steal confirmation tests**

Tests must assert:

- `attack` outside combat creates `attack_start` confirmation and does not create `combat_state`.
- confirming `attack_start` resumes dispatch and creates combat.
- `transfer(mode="steal")` creates `steal` confirmation before `pending_check`.
- confirming `steal` resumes dispatch and creates `pending_check(kind="steal")`.
- `rest` in a non-safe location creates `dangerous_rest` confirmation before recovery or encounter rolls.
- confirming `dangerous_rest` resumes rest dispatch.
- `use` outside combat with a damage consumable creates `dangerous_use` confirmation before item effects.
- confirming `dangerous_use` resumes item dispatch.

Expected RED: attack, steal, dangerous rest, and dangerous use still execute immediately.

- [x] **Step 2: Implement verb confirmation gate**

Before dispatching a classified single verb, check whether it needs confirmation. Store the verb dump internally and return `confirmation_required` plus state. `run_confirm` reconstructs the `Verb` and calls `_dispatch_verb` directly.

- [x] **Step 3: Run confirmation tests**

Run:

```powershell
& .\.venv\Scripts\python.exe -m pytest server\tests\game\flow\test_confirmation.py -q
```

Expected: pass.

## Task 4: Verification

**Files:**
- Modify: `docs/superpowers/plans/2026-05-09-graph-first-game-roadmap.md`
- Modify: `docs/superpowers/plans/2026-05-09-action-confirmation.md`

- [x] **Step 1: Mark Phase 4 live slice status**

Update the roadmap to say the first confirmation slice exists, while final graph-native action schema remains pending.

- [x] **Step 2: Run focused tests**

Run:

```powershell
& .\.venv\Scripts\python.exe -m pytest server\tests\game\flow\test_confirmation.py server\tests\game\flow\test_quest_action_button_only.py server\tests\db\test_state.py server\tests\db\test_supabase.py -q
```

Expected: pass.

- [x] **Step 3: Run Ruff**

Run:

```powershell
& .\.venv\Scripts\python.exe -m ruff check server\src\game\\flow\\confirmation.py server\src\game\flow\turn.py server\src\game\domain\state.py server\src\db\_schema.py server\src\wire server\src\api server\tests\game\flow\test_confirmation.py server\tests\game\flow\test_quest_action_button_only.py
```

Expected: `All checks passed!`

- [x] **Step 4: Run full server tests**

Run:

```powershell
& .\.venv\Scripts\python.exe -m pytest -q
```

Expected: pass.

## Stop Point

After this slice, the server can hold and resolve pending confirmations. The remaining Phase 4 work is the final graph-native `Action` schema, graph-view id validation, and query-only dispatch.
