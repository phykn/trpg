# Graph Play Loop Smoke Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prove a graph-mode game can run from new game to quest offer, quest accept confirmation, attack confirmation, combat resolution, quest completion, and reward delivery.

**Architecture:** This session cannot see local `server/.env.*` or `client/.env`, so this pass verifies the real graph API handlers through `httpx.ASGITransport`, `LocalFsGraphRepo`, Fake Storage, and a Fake LLM. If the test exposes tuning drift, fix the graph planner rather than adding client-side special cases.

**Tech Stack:** FastAPI ASGI app, pytest, LocalFs graph repo, Pydantic graph payloads, root `.venv` on Windows.

---

### Task 1: Add Graph Play Loop Smoke Test

**Files:**
- Modify: `server/tests/api/test_graph_session_routes.py`

- [x] **Step 1: Write the failing test**

Add one test that performs this sequence:

```python
@pytest.mark.asyncio
async def test_graph_play_loop_reaches_quest_reward_without_legacy_state(tmp_path):
    app = _build_app(tmp_path)

    async with _client(app) as client:
        game_id = await _init_graph_session(client)

        move_response = await client.post(
            f"/session/{game_id}/graph/turn",
            json={"action": {"verb": "move", "to": "loc_02"}},
        )
        assert move_response.status_code == 200, move_response.text
        move_body = move_response.json()
        quest_id = move_body["state"]["questOffers"][0]["id"]

        accept_response = await client.post(
            f"/session/{game_id}/graph/turn",
            json={"action": {"verb": "transfer", "what": quest_id, "how": "accept"}},
        )
        assert accept_response.status_code == 200, accept_response.text
        accept_body = accept_response.json()
        accept_id = accept_body["state"]["pendingConfirmation"]["id"]

        accepted_response = await client.post(
            f"/session/{game_id}/graph/confirm",
            json={"confirmation_id": accept_id, "decision": "confirm"},
        )
        assert accepted_response.status_code == 200, accepted_response.text
        accepted_body = accepted_response.json()
        enemy_id = "auto_enemy_001"

        attack_response = await client.post(
            f"/session/{game_id}/graph/turn",
            json={"action": {"verb": "attack", "what": enemy_id}},
        )
        assert attack_response.status_code == 200, attack_response.text
        attack_body = attack_response.json()
        attack_id = attack_body["state"]["pendingConfirmation"]["id"]

        first_exchange_response = await client.post(
            f"/session/{game_id}/graph/confirm",
            json={"confirmation_id": attack_id, "decision": "confirm"},
        )
        assert first_exchange_response.status_code == 200, first_exchange_response.text
        first_exchange_body = first_exchange_response.json()

        final_response = await client.post(
            f"/session/{game_id}/graph/turn",
            json={"action": {"verb": "attack", "what": enemy_id}},
        )
        assert final_response.status_code == 200, final_response.text
        final_body = final_response.json()

    graph = await app.state.graph_repo.load_graph(game_id)
    progress = await app.state.graph_repo.load_progress(game_id)
    logs = await app.state.graph_repo.load_log_entries(game_id)

    assert accepted_body["state"]["quest"]["id"] == quest_id
    assert accepted_body["state"]["questOffers"] == []
    assert first_exchange_body["state"]["combat"] is not None
    assert final_body["state"]["combat"] is None
    assert final_body["state"]["quest"] is None
    assert final_body["state"]["questOffers"][0]["id"] == "auto_quest_002"
    assert final_body["state"]["hero"]["gold"] == 5
    assert final_body["state"]["hero"]["exp"] == 10
    assert graph.nodes[quest_id].properties["status"] == "completed"
    assert graph.nodes[enemy_id].properties["status"] == ["defeated"]
    assert progress.active_quest_id is None
    assert progress.graph_combat_state is None
    assert [entry.kind for entry in logs[-2:]] == ["act", "act"]
    assert [entry.text for entry in logs[-2:]] == [
        "당신은 전투에서 승리합니다.",
        "새 의뢰가 도착합니다: 마을의 부탁.",
    ]
```

- [x] **Step 2: Run the test to verify RED**

Run:

```powershell
& .\.venv\Scripts\python.exe -m pytest server\tests\api\test_graph_session_routes.py::test_graph_play_loop_reaches_quest_reward_without_legacy_state -q
```

Expected: FAIL if the current generated enemy resolves too fast, reward state does not arrive, or quest/offer state drifts.

### Task 2: Fix The Smallest Gameplay Drift

**Files:**
- Modify only the file exposed by Task 1 failure.

- [x] **Step 1: Make the minimal code change**

If the first exchange already completes combat, tune only the generated quest enemy in `server/src/game/engines/graph_quest_generation.py`:

```python
"hp": 28,
"max_hp": 28,
```

This keeps generated quest fights near two player attacks for the default graph player without touching the combat engine.

- [x] **Step 2: Run the focused test**

Run:

```powershell
& .\.venv\Scripts\python.exe -m pytest server\tests\api\test_graph_session_routes.py::test_graph_play_loop_reaches_quest_reward_without_legacy_state -q
```

Expected: PASS.

### Task 3: Regression Verification

**Files:**
- No production changes unless verification exposes a real break.

- [x] **Step 1: Run graph API tests**

```powershell
& .\.venv\Scripts\python.exe -m pytest server\tests\api\test_graph_session_routes.py -q
```

- [x] **Step 2: Run runtime graph tests**

```powershell
& .\.venv\Scripts\python.exe -m pytest server\tests\game\runtime -q
```

- [x] **Step 3: Run lint for touched server files**

```powershell
& .\.venv\Scripts\ruff.exe check server\src\game\engines\graph_quest_generation.py server\tests\api\test_graph_session_routes.py
```

- [x] **Step 4: Commit and push**

```powershell
git add docs\superpowers\plans\2026-05-10-graph-play-loop-smoke.md server\tests\api\test_graph_session_routes.py server\src\game\engines\graph_quest_generation.py
git commit -m "test: cover graph play loop"
git push
```
