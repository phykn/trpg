# Graph-Native Move Engine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a graph-native move engine that returns validated `GraphChange` objects for character movement.

**Architecture:** Keep this slice pure and additive. The new engine reads only `Graph`, emits `GraphChange` plans plus small effect metadata, and leaves existing `/turn` dispatch on the legacy move path until graph apply and flow integration are ready.

**Tech Stack:** Python 3.12+, Pydantic v2, pytest, Ruff, root `.venv` on Windows.

---

## Scope

This slice covers character movement only.

It does not wire live `/turn` to the graph move engine, does not rewrite movement rolls, and does not remove legacy `apply_changes(... type="move")`.

## File Structure

- `server/src/game/engines/graph_move.py`
  - New pure graph move planner.
- `server/tests/game/engines/test_graph_move.py`
  - Unit tests for graph changes, adjacency gating, visit tracking, and companion follow.
- `docs/superpowers/plans/2026-05-09-graph-first-game-roadmap.md`
  - Mark Phase 5 as started and record that graph-native move planning exists.

## Task 1: Move Planner Tests

**Files:**
- Create: `server/tests/game/engines/test_graph_move.py`

- [x] **Step 1: Write failing graph move tests**

Create tests with this shape:

```python
import pytest

from src.game.domain.graph import Graph, GraphEdge, GraphNode
from src.game.domain.graph import apply_graph_change
from src.game.engines.graph_move import GraphMoveError, plan_character_move


def _graph() -> Graph:
    return Graph(
        nodes={
            "player_01": GraphNode(
                id="player_01",
                type="character",
                properties={"visited_location_ids": ["town"]},
            ),
            "companion_01": GraphNode(
                id="companion_01",
                type="character",
                properties={"visited_location_ids": ["town"]},
            ),
            "town": GraphNode(id="town", type="location"),
            "forest": GraphNode(id="forest", type="location"),
            "tower": GraphNode(id="tower", type="location"),
        },
        edges={
            "located_at:player_01:town": GraphEdge(
                id="located_at:player_01:town",
                type="located_at",
                from_node_id="player_01",
                to_node_id="town",
            ),
            "located_at:companion_01:town": GraphEdge(
                id="located_at:companion_01:town",
                type="located_at",
                from_node_id="companion_01",
                to_node_id="town",
            ),
            "connects_to:town:forest": GraphEdge(
                id="connects_to:town:forest",
                type="connects_to",
                from_node_id="town",
                to_node_id="forest",
            ),
            "has_companion:player_01:companion_01": GraphEdge(
                id="has_companion:player_01:companion_01",
                type="has_companion",
                from_node_id="player_01",
                to_node_id="companion_01",
            ),
        },
    )


def _apply_all(graph: Graph, changes) -> Graph:
    for change in changes:
        graph = apply_graph_change(graph, change)
    return graph


def test_move_replaces_location_edge_and_marks_visited():
    result = plan_character_move(_graph(), "player_01", "forest", require_connection=True)
    changed = _apply_all(_graph(), result.changes)

    assert result.moved_character_ids == ["player_01", "companion_01"]
    assert changed.edges["located_at:player_01:forest"].to_node_id == "forest"
    assert "located_at:player_01:town" not in changed.edges
    assert changed.nodes["player_01"].properties["visited_location_ids"] == [
        "forest",
        "town",
    ]


def test_companion_follow_moves_companion_and_marks_visited():
    result = plan_character_move(_graph(), "player_01", "forest", require_connection=True)
    changed = _apply_all(_graph(), result.changes)

    assert changed.edges["located_at:companion_01:forest"].to_node_id == "forest"
    assert "located_at:companion_01:town" not in changed.edges
    assert changed.nodes["companion_01"].properties["visited_location_ids"] == [
        "forest",
        "town",
    ]


def test_non_adjacent_move_is_rejected_when_connection_required():
    with pytest.raises(GraphMoveError, match="not adjacent"):
        plan_character_move(_graph(), "player_01", "tower", require_connection=True)


def test_npc_move_can_skip_adjacency_gate():
    graph = _graph()
    result = plan_character_move(graph, "companion_01", "tower")
    changed = _apply_all(graph, result.changes)

    assert changed.edges["located_at:companion_01:tower"].to_node_id == "tower"


def test_missing_character_or_destination_is_rejected():
    with pytest.raises(GraphMoveError, match="missing character"):
        plan_character_move(_graph(), "ghost", "forest")
    with pytest.raises(GraphMoveError, match="missing location"):
        plan_character_move(_graph(), "player_01", "void")


def test_move_result_changes_are_individually_valid_graph_changes():
    graph = _graph()
    result = plan_character_move(graph, "player_01", "forest", require_connection=True)

    for change in result.changes:
        graph = apply_graph_change(graph, change)

    assert graph.nodes["player_01"].properties["visited_location_ids"] == [
        "forest",
        "town",
    ]
```

- [x] **Step 2: Run tests to verify RED**

Run:

```powershell
& .\.venv\Scripts\python.exe -m pytest server\tests\game\engines\test_graph_move.py -q
```

Expected RED: `src.game.engines.graph_move` does not exist.

## Task 2: Move Planner Implementation

**Files:**
- Create: `server/src/game/engines/graph_move.py`

- [x] **Step 1: Implement the pure move planner**

Implement:

- `GraphMoveError(ValueError)`
- `GraphMoveResult(BaseModel)`
- `plan_character_move(graph, character_id, destination_id, require_connection=False)`

Rules:

- actor must be a character node,
- destination must be a location node,
- when `require_connection=True`, current location must connect to destination unless already there,
- remove each moved character's old `located_at` edge,
- add a new `located_at:<character_id>:<destination_id>` edge,
- update each moved character node's `visited_location_ids` property,
- move direct `has_companion` targets with the actor,
- return no graph facts outside the `changes` list.

- [x] **Step 2: Run graph move tests**

Run:

```powershell
& .\.venv\Scripts\python.exe -m pytest server\tests\game\engines\test_graph_move.py -q
```

Expected GREEN: graph move tests pass.

## Task 3: Roadmap And Verification

**Files:**
- Modify: `docs/superpowers/plans/2026-05-09-graph-first-game-roadmap.md`
- Modify: `docs/superpowers/plans/2026-05-09-graph-native-move-engine.md`

- [x] **Step 1: Update roadmap**

Change Phase 5 status to started and add one current-state bullet:

```markdown
- `server/src/game/engines/graph_move.py` plans graph-native character movement as validated `GraphChange` objects.
```

- [x] **Step 2: Run focused tests**

Run:

```powershell
& .\.venv\Scripts\python.exe -m pytest server\tests\game\engines\test_graph_move.py server\tests\game\domain\test_graph_contract.py server\tests\game\domain\test_graph_query.py -q
```

Expected: pass.

- [x] **Step 3: Run Ruff**

Run:

```powershell
& .\.venv\Scripts\python.exe -m ruff check server\src\game\engines\graph_move.py server\tests\game\engines\test_graph_move.py
```

Expected: `All checks passed!`

- [x] **Step 4: Run full server tests**

Run:

```powershell
& .\.venv\Scripts\python.exe -m pytest -q
```

Expected: pass.

## Stop Point

After this slice, Phase 5 has its first graph-native engine seam. The next slice should add a shared graph runtime apply result for engine changes or start `transfer` planning if the apply seam is already clear.
