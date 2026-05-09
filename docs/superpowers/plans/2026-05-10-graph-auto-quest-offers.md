# Graph Auto Quest Offers Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Keep graph sessions from running out of obvious work by adding a validated quest offer when the current graph has no active quest and no visible offer.

**Architecture:** The first version is engine-owned, not LLM-owned: code chooses IDs, rewards, trigger type, target, giver, and item nodes. A later LLM text pass can rename/title the already locked bundle, but this plan keeps weak models away from graph IDs, numbers, and trigger semantics.

**Tech Stack:** Python 3.12, Pydantic v2 graph models, graph runtime `GraphChange`, pytest, Ruff, root `.venv` on Windows.

---

## Files

- Create `server/src/game/engines/graph_quest_generation.py`: pure planner that returns graph changes for one pending quest offer, or `None` if no offer is needed.
- Create `server/tests/game/engines/test_graph_quest_generation.py`: planner tests for generation, no-op when work already exists, and graph invariant safety.
- Modify `server/src/game/runtime/turn.py`: after a mutating graph action, apply one generated quest bundle before saving the graph and front state.
- Modify `server/tests/game/runtime/test_graph_action_turn.py`: runtime test that a move into a no-work location saves and returns a generated offer.
- Modify `docs/superpowers/plans/2026-05-09-graph-first-game-roadmap.md`: mark the first auto-offer slice as started after code passes.

## Task 1: Pure Quest Offer Planner

**Files:**
- Create: `server/src/game/engines/graph_quest_generation.py`
- Create: `server/tests/game/engines/test_graph_quest_generation.py`

- [ ] **Step 1: Write the failing planner tests**

Add tests that build a graph with a player in `town`, no active quest, and no visible quest giver. The planner should return changes that add exactly one pending quest, one giver character, one enemy character, one reward item, and the required `located_at`, `gives_quest`, `target_of`, and `reward_of` edges.

```python
def test_generates_pending_hunt_offer_when_no_work_exists():
    result = plan_missing_quest_offer(_graph_without_work(), "player_01")

    assert result is not None
    assert {change.type for change in result.changes} == {"add_node", "add_edge"}
    graph = _apply_all(_graph_without_work(), result.changes)
    quest = graph.nodes[result.quest_id]
    assert quest.type == "quest"
    assert quest.properties["status"] == "pending"
    assert quest.properties["triggers"][0]["type"] == "character_defeat"
    assert quest.properties["triggers_met"] == [False]
    assert any(edge.type == "gives_quest" and edge.to_node_id == result.quest_id for edge in graph.edges.values())
    assert any(edge.type == "target_of" and edge.to_node_id == result.quest_id for edge in graph.edges.values())
    assert any(edge.type == "reward_of" and edge.to_node_id == result.quest_id for edge in graph.edges.values())
```

Add no-op tests:

```python
def test_noops_when_active_quest_exists():
    graph = _graph_without_work()
    graph.nodes["quest_existing"] = GraphNode(id="quest_existing", type="quest", properties={"status": "active"})

    assert plan_missing_quest_offer(graph, "player_01") is None


def test_noops_when_visible_offer_exists():
    graph = _graph_with_visible_pending_offer()

    assert plan_missing_quest_offer(graph, "player_01") is None
```

- [ ] **Step 2: Verify RED**

Run:

```powershell
& .\.venv\Scripts\python.exe -m pytest server\tests\game\engines\test_graph_quest_generation.py -q
```

Expected: FAIL because `src.game.engines.graph_quest_generation` does not exist.

- [ ] **Step 3: Implement the planner**

Implement:

```python
def plan_missing_quest_offer(graph: Graph, player_id: str) -> GraphQuestOfferPlan | None:
    location_id = location_of(graph, player_id)
    if location_id is None or _has_open_work(graph, location_id):
        return None
    index = _next_auto_index(graph)
    quest_id = f"auto_quest_{index:03d}"
    giver_id = f"auto_giver_{index:03d}"
    enemy_id = f"auto_enemy_{index:03d}"
    reward_id = f"auto_reward_{index:03d}"
    changes = [
        AddNodeChange(type="add_node", node=_giver(giver_id)),
        AddNodeChange(type="add_node", node=_enemy(enemy_id)),
        AddNodeChange(type="add_node", node=_reward(reward_id)),
        AddNodeChange(type="add_node", node=_quest(quest_id, enemy_id, reward_id)),
        AddEdgeChange(type="add_edge", edge=_edge("located_at", giver_id, location_id)),
        AddEdgeChange(type="add_edge", edge=_edge("located_at", enemy_id, location_id)),
        AddEdgeChange(type="add_edge", edge=_edge("gives_quest", giver_id, quest_id)),
        AddEdgeChange(type="add_edge", edge=_edge("target_of", enemy_id, quest_id)),
        AddEdgeChange(type="add_edge", edge=_edge("reward_of", reward_id, quest_id)),
    ]
    return GraphQuestOfferPlan(quest_id=quest_id, changes=changes)
```

Use fixed safe values: enemy HP 12/12, MP 0/0, stats `{body: 2, agility: 1, mind: 0, presence: 0}`, reward gold 5 and exp 10, and quest status `pending`.

- [ ] **Step 4: Verify GREEN**

Run:

```powershell
& .\.venv\Scripts\python.exe -m pytest server\tests\game\engines\test_graph_quest_generation.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add server\src\game\engines\graph_quest_generation.py server\tests\game\engines\test_graph_quest_generation.py
git commit -m "feat: plan graph quest offers"
```

## Task 2: Runtime Hook

**Files:**
- Modify: `server/src/game/runtime/turn.py`
- Modify: `server/tests/game/runtime/test_graph_action_turn.py`

- [ ] **Step 1: Write the failing runtime test**

Add a test that moves the player in a graph without any quest. The saved graph and returned front state should contain the generated pending quest.

```python
async def test_run_graph_action_turn_generates_offer_when_no_work_exists(tmp_path):
    repo = await _repo(tmp_path)

    result = await run_graph_action_turn(repo, "game-1", Action(verb="move", to="forest"))
    saved_graph = await repo.load_graph("game-1")

    assert "auto_quest_001" in saved_graph.nodes
    assert saved_graph.nodes["auto_quest_001"].properties["status"] == "pending"
    assert result.front_state.quest is not None
    assert result.front_state.quest.id == "auto_quest_001"
    assert result.front_state.quest.actions == ["accept"]
```

- [ ] **Step 2: Verify RED**

Run:

```powershell
& .\.venv\Scripts\python.exe -m pytest server\tests\game\runtime\test_graph_action_turn.py::test_run_graph_action_turn_generates_offer_when_no_work_exists -q
```

Expected: FAIL because the runtime does not call the planner.

- [ ] **Step 3: Apply planner changes during graph turns**

In `run_graph_action_turn_from_runtime`, after `dispatch.runtime` is available and before saving, call `plan_missing_quest_offer`. If it returns changes, apply them with `apply_runtime_graph_changes`; keep the original action card unchanged.

```python
offer = plan_missing_quest_offer(next_runtime.graph, next_runtime.progress.player_id)
if offer is not None:
    applied = apply_runtime_graph_changes(next_runtime, offer.changes)
    next_runtime = applied.runtime
```

- [ ] **Step 4: Verify GREEN**

Run:

```powershell
& .\.venv\Scripts\python.exe -m pytest server\tests\game\runtime\test_graph_action_turn.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add server\src\game\runtime\turn.py server\tests\game\runtime\test_graph_action_turn.py
git commit -m "feat: replenish graph quest offers"
```

## Task 3: Verification And Roadmap Note

**Files:**
- Modify: `docs/superpowers/plans/2026-05-09-graph-first-game-roadmap.md`

- [ ] **Step 1: Run focused server tests**

```powershell
& .\.venv\Scripts\python.exe -m pytest server\tests\game\engines\test_graph_quest_generation.py server\tests\game\runtime\test_graph_action_turn.py server\tests\wire\test_graph_to_front.py server\tests\api\test_graph_session_routes.py -q
```

Expected: PASS.

- [ ] **Step 2: Run full server tests and ruff**

```powershell
& .\.venv\Scripts\python.exe -m pytest -q
& .\.venv\Scripts\python.exe -m ruff check server
```

Expected: pytest passes with one skipped test; ruff reports `All checks passed!`.

- [ ] **Step 3: Update roadmap current state**

Add one bullet under Current State:

```markdown
- Graph runtime can create a deterministic pending quest offer when no active quest or visible offer exists.
```

- [ ] **Step 4: Commit**

```powershell
git add docs\superpowers\plans\2026-05-09-graph-first-game-roadmap.md
git commit -m "docs: note graph quest offer replenishment"
```

## Self-Review

- Spec coverage: the plan creates a quest bundle with quest, giver NPC, monster target, reward item, trigger, reward budget, and offer state. It intentionally defers LLM text generation because the current weak-model constraint requires locked IDs and numbers first.
- Placeholder scan: no step depends on undefined files except files created by earlier steps.
- Type consistency: the plan uses existing `GraphChange`, `GraphNode`, `GraphEdge`, `GameRuntimeState`, and `graph_to_front_state` names.
