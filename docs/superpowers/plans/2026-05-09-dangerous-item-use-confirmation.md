# Dangerous Item-Use Confirmation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ask for confirmation before a player uses a damage item outside combat.

**Architecture:** Reuse the existing pending-confirmation contract in `server/src/game/flow/confirmation.py`. The engine, not the LLM, decides the action is dangerous by looking up the item and checking for `ConsumableEffect(effect="damage")`. Combat item use stays immediate because the player is already inside an explicit combat state.

**Tech Stack:** Python 3.12+, Pydantic v2, pytest, Ruff, root `.venv` on Windows.

---

## Scope

This is a narrow Phase 4 follow-up. It does not add a new item danger schema field, change item effects, or migrate use dispatch to graph-native `Action`.

## File Structure

- `server/src/game/flow/confirmation.py`
  - Add a use-confirmation branch in `build_verb_confirmation`.
- `server/tests/game/flow/test_confirmation.py`
  - Add tests for dangerous damage item use and safe heal item use.
- `docs/superpowers/plans/2026-05-09-graph-first-game-roadmap.md`
  - Mark dangerous item-use confirmation as live after verification.
- `docs/superpowers/plans/2026-05-09-action-confirmation.md`
  - Update the completed confirmation slice list after verification.

## Task 1: Dangerous Use Detection

**Files:**
- Modify: `server/tests/game/flow/test_confirmation.py`
- Modify: `server/src/game/flow/confirmation.py`

- [x] **Step 1: Write failing dangerous-use tests**

Add tests that assert:

- `use` outside combat with a damage consumable creates `dangerous_use` confirmation.
- the damage item is not consumed before confirmation.
- confirming `dangerous_use` resumes the original use action.
- `use` outside combat with a heal consumable does not create confirmation.

Run:

```powershell
& .\.venv\Scripts\python.exe -m pytest server\tests\game\flow\test_confirmation.py -q
```

Expected RED: damage item use currently applies immediately.

- [x] **Step 2: Implement minimal use confirmation**

In `build_verb_confirmation`, add a branch for `verb.name == "use"` before the final `return None`.

The branch should:

- skip confirmation when `state.combat_state is not None`,
- read `item_id` from `verb.modifiers`,
- require that the item exists and is in the player's inventory,
- require that `item.effects` is `ConsumableEffect` with `effect == "damage"`,
- store the original verb and player input in the internal payload.

- [x] **Step 3: Verify confirmation tests**

Run:

```powershell
& .\.venv\Scripts\python.exe -m pytest server\tests\game\flow\test_confirmation.py -q
```

Expected GREEN: all confirmation tests pass.

## Task 2: Regression Coverage

**Files:**
- Modify: `server/tests/game/flow/test_use_matching.py`
- Modify: `docs/superpowers/plans/2026-05-09-graph-first-game-roadmap.md`
- Modify: `docs/superpowers/plans/2026-05-09-action-confirmation.md`

- [x] **Step 1: Update use-flow regression tests**

If an existing out-of-combat damage item flow expects immediate damage, update it to confirm first. Do not change heal-item tests.

- [x] **Step 2: Update docs**

Mark dangerous item-use confirmation as live. Leave final graph-native `Action`, graph-view id validation, and query-only dispatch as remaining Phase 4 work.

- [x] **Step 3: Run focused tests**

Run:

```powershell
& .\.venv\Scripts\python.exe -m pytest server\tests\game\flow\test_confirmation.py server\tests\game\flow\test_use_matching.py server\tests\game\flow\test_use_heal_e2e.py -q
```

Expected: pass.

- [x] **Step 4: Run Ruff**

Run:

```powershell
& .\.venv\Scripts\python.exe -m ruff check server\src\game\flow\confirmation.py server\tests\game\flow\test_confirmation.py server\tests\game\flow\test_use_matching.py server\tests\game\flow\test_use_heal_e2e.py
```

Expected: `All checks passed!`

- [x] **Step 5: Run full server tests**

Run:

```powershell
& .\.venv\Scripts\python.exe -m pytest -q
```

Expected: pass.

## Stop Point

After this slice, high-impact confirmation covers quest accept/abandon, attack-start, steal, dangerous rest, and out-of-combat damage item use. The remaining Phase 4 work is final graph-native `Action`, graph-view id validation, and query-only dispatch.
