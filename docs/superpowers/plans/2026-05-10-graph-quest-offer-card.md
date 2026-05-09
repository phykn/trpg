# Graph Quest Offer Card Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** When the graph runtime creates an automatic quest offer, the player also receives a system log card that makes the new offer visible.

**Architecture:** `plan_missing_quest_offer` already creates the graph bundle. `run_graph_action_turn_from_runtime` should detect that plan, apply it, append the normal action card, then append one extra `ActLogEntry` for the generated offer and persist both cards with one `next_log_id` update.

**Tech Stack:** Python 3.13 in the root `.venv`, Pydantic v2, pytest, Ruff.

---

### Task 1: Append an Offer Card

**Files:**
- Modify: `server/tests/game/runtime/test_graph_action_turn.py`
- Modify: `server/src/game/runtime/cards.py`
- Modify: `server/src/game/runtime/turn.py`

- [x] **Step 1: Write the failing test**

Add this assertion block to `test_run_graph_action_turn_generates_offer_when_no_work_exists`:

```python
saved_logs = await repo.load_log_entries("game-1")

assert [entry.kind for entry in saved_logs] == ["act", "act"]
assert saved_logs[1].text == "새 의뢰가 도착합니다: 마을의 부탁."
assert result.front_state.log == saved_logs
```

- [x] **Step 2: Run test to verify it fails**

Run:

```powershell
& .\.venv\Scripts\python.exe -m pytest server\tests\game\runtime\test_graph_action_turn.py::test_run_graph_action_turn_generates_offer_when_no_work_exists -q
```

Expected: FAIL because only one log entry is persisted.

- [x] **Step 3: Write minimal implementation**

Add a helper in `server/src/game/runtime/cards.py`:

```python
def build_graph_quest_offer_card(
    runtime: GameRuntimeState,
    quest_id: str,
    log_id: int,
) -> ActLogEntry:
    quest = _quest_title(runtime.graph, quest_id)
    return ActLogEntry(id=log_id, kind="act", text=f"새 의뢰가 도착합니다: {quest}.")
```

In `run_graph_action_turn_from_runtime`, keep the existing action card and append the offer card only when an offer plan was applied.

- [x] **Step 4: Run focused tests**

Run:

```powershell
& .\.venv\Scripts\python.exe -m pytest server\tests\game\runtime\test_graph_action_turn.py -q
```

Expected: PASS.

- [x] **Step 5: Run verification**

Run:

```powershell
& .\.venv\Scripts\python.exe -m pytest -q
& .\.venv\Scripts\ruff.exe check server
```

Expected: all tests pass and Ruff reports no errors.

- [x] **Step 6: Commit**

```powershell
git add docs\superpowers\plans\2026-05-10-graph-quest-offer-card.md server\tests\game\runtime\test_graph_action_turn.py server\src\game\runtime\cards.py server\src\game\runtime\turn.py
git commit -m "feat: show generated graph quest offers"
```
