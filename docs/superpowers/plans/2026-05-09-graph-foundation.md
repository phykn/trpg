# Graph Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first implementation layer for the ontology-first game model without replacing the current turn engine in one risky change.

**Architecture:** The contract graph stays in `server/src/game/domain/graph.py` as a pure Pydantic model. Existing `GameState` can be projected into that graph so tests and future systems can rely on the new node/edge contract before persistence and runtime flow are migrated. Storage work starts with deterministic row codecs for future Supabase tables, not with live database writes.

**Tech Stack:** Python 3.12+, Pydantic v2, pytest, Ruff, root `.venv` on Windows.

---

## File Structure

- `server/src/game/domain/graph.py`
  - Already contains the pure graph contract, graph changes, and invariant checks.
- `server/src/game/ontology/contract_graph.py`
  - New bridge from current `GameState` objects to the contract `Graph`.
  - This file may import legacy game state models; `game/domain/graph.py` must stay independent.
- `server/tests/game/ontology/test_contract_graph.py`
  - New tests for deterministic projection from current state to contract graph nodes and edges.
- `server/src/db/graph_rows.py`
  - New pure row codec for future `graph_nodes` and `graph_edges` tables.
  - It must not call Supabase or read env.
- `server/tests/db/test_graph_rows.py`
  - New tests proving graph rows round-trip without losing node properties, edge endpoints, or edge properties.

## Task 1: Project Current State Into Contract Graph

**Files:**
- Create: `server/src/game/ontology/contract_graph.py`
- Create: `server/tests/game/ontology/test_contract_graph.py`

- [ ] **Step 1: Write the failing projection test**

Create `server/tests/game/ontology/test_contract_graph.py`:

```python
from src.game.domain.entities import (
    Character,
    Connection,
    Item,
    Location,
    Quest,
    QuestRewards,
    QuestTrigger,
    Skill,
)
from src.game.domain.state import GameState
from src.game.ontology.contract_graph import build_contract_graph


def test_build_contract_graph_projects_location_inventory_and_quest_edges():
    state = GameState(game_id="g", profile="p", player_id="player")
    state.characters = {
        "player": Character(
            id="player",
            name="Player",
            race_id="human",
            location_id="town",
            inventory_ids=["potion"],
            learned_skill_ids=["slash"],
            relations={"elder": 25},
        ),
        "elder": Character(id="elder", name="Elder", race_id="human", location_id="town"),
        "rat": Character(id="rat", name="Rat", race_id="beast", location_id="cellar"),
    }
    state.items = {
        "rusty_sword": Item(id="rusty_sword", name="Rusty Sword"),
        "potion": Item(id="potion", name="Potion"),
        "reward_gem": Item(id="reward_gem", name="Reward Gem"),
    }
    state.locations = {
        "town": Location(
            id="town",
            name="Town",
            item_ids=["rusty_sword"],
            connections=[Connection(target_id="cellar", difficulty="easy", key_item_id="rusty_sword")],
        ),
        "cellar": Location(id="cellar", name="Cellar"),
    }
    state.skills = {
        "slash": Skill(
            id="slash",
            name="Slash",
            type="attack",
            target="single",
            primary_stat="STR",
        )
    }
    state.quests = {
        "rat_quest": Quest(
            id="rat_quest",
            title="Rat Quest",
            giver_id="elder",
            difficulty="easy",
            triggers=[
                QuestTrigger(
                    id="kill_rat",
                    name="Kill Rat",
                    type="character_death",
                    target_id="rat",
                )
            ],
            rewards=QuestRewards(gold=5, exp=10, items=["reward_gem"]),
        )
    }

    graph = build_contract_graph(state)

    assert graph.nodes["player"].type == "character"
    assert graph.nodes["town"].type == "location"
    assert graph.nodes["rusty_sword"].type == "item"
    assert graph.nodes["rat_quest"].type == "quest"

    edge_types = {(edge.type, edge.from_node_id, edge.to_node_id) for edge in graph.edges.values()}

    assert ("located_at", "player", "town") in edge_types
    assert ("located_at", "rusty_sword", "town") in edge_types
    assert ("connects_to", "town", "cellar") in edge_types
    assert ("carries", "player", "potion") in edge_types
    assert ("knows_skill", "player", "slash") in edge_types
    assert ("relation", "player", "elder") in edge_types
    assert ("gives_quest", "elder", "rat_quest") in edge_types
    assert ("target_of", "rat", "rat_quest") in edge_types
    assert ("reward_of", "reward_gem", "rat_quest") in edge_types

    connection_edge = graph.edges["connects_to:town:cellar"]
    assert connection_edge.properties == {"difficulty": "easy", "key_item_id": "rusty_sword"}

    relation_edge = graph.edges["relation:player:elder"]
    assert relation_edge.properties == {"affinity": 25}
```

- [ ] **Step 2: Run the projection test and confirm RED**

Run:

```powershell
& .\.venv\Scripts\python.exe -m pytest server\tests\game\ontology\test_contract_graph.py -q
```

Expected result: fail because `src.game.ontology.contract_graph` does not exist.

- [ ] **Step 3: Implement `build_contract_graph`**

Create `server/src/game/ontology/contract_graph.py`:

```python
from __future__ import annotations

from typing import Any

from src.game.domain.graph import EdgeType, Graph, GraphEdge, GraphNode, NodeType
from src.game.domain.state import GameState


def build_contract_graph(state: GameState) -> Graph:
    nodes: dict[str, GraphNode] = {}
    edges: dict[str, GraphEdge] = {}

    def add_node(node_id: str, node_type: NodeType, properties: dict[str, Any]) -> None:
        nodes[node_id] = GraphNode(id=node_id, type=node_type, properties=properties)

    def add_edge(
        edge_type: EdgeType,
        from_node_id: str,
        to_node_id: str,
        properties: dict[str, Any] | None = None,
        *,
        unique_id: str | None = None,
    ) -> None:
        edge_id = unique_id or f"{edge_type}:{from_node_id}:{to_node_id}"
        edges[edge_id] = GraphEdge(
            id=edge_id,
            type=edge_type,
            from_node_id=from_node_id,
            to_node_id=to_node_id,
            properties=properties or {},
        )

    for location in state.locations.values():
        add_node(location.id, "location", location.model_dump(exclude={"item_ids", "connections"}))
        for item_id in location.item_ids:
            add_edge("located_at", item_id, location.id)
        for connection in location.connections:
            properties = connection.model_dump(exclude={"target_id"}, exclude_none=True)
            add_edge("connects_to", location.id, connection.target_id, properties)

    for character in state.characters.values():
        add_node(
            character.id,
            "character",
            character.model_dump(
                exclude={
                    "location_id",
                    "equipment",
                    "inventory_ids",
                    "relations",
                    "racial_skill_ids",
                    "learned_skill_ids",
                    "companions",
                }
            ),
        )
        if character.location_id:
            add_edge("located_at", character.id, character.location_id)
        for slot, item_id in character.equipment.equipped_items():
            add_edge("equips", character.id, item_id, {"slot": slot})
        for item_id in character.inventory_ids:
            add_edge("carries", character.id, item_id)
        for skill_id in character.racial_skill_ids:
            add_edge("knows_skill", character.id, skill_id, {"source": "racial"})
        for skill_id in character.learned_skill_ids:
            add_edge("knows_skill", character.id, skill_id, {"source": "learned"})
        for companion_id in character.companions:
            add_edge("has_companion", character.id, companion_id)
        for target_id, affinity in character.relations.items():
            add_edge("relation", character.id, target_id, {"affinity": affinity})

    for item in state.items.values():
        add_node(item.id, "item", item.model_dump())

    for skill in state.skills.values():
        add_node(skill.id, "skill", skill.model_dump())

    for quest in state.quests.values():
        add_node(quest.id, "quest", quest.model_dump(exclude={"giver_id", "triggers", "rewards"}))
        if quest.giver_id:
            add_edge("gives_quest", quest.giver_id, quest.id)
        for trigger in quest.triggers:
            add_edge(
                "target_of",
                trigger.target_id,
                quest.id,
                trigger.model_dump(exclude={"target_id"}),
                unique_id=f"target_of:{trigger.id}:{trigger.target_id}:{quest.id}",
            )
        for item_id in quest.rewards.items:
            add_edge("reward_of", item_id, quest.id)

    return Graph(nodes=nodes, edges=edges)
```

- [ ] **Step 4: Run the projection test and confirm GREEN**

Run:

```powershell
& .\.venv\Scripts\python.exe -m pytest server\tests\game\ontology\test_contract_graph.py -q
```

Expected result: pass.

- [ ] **Step 5: Run neighboring graph tests**

Run:

```powershell
& .\.venv\Scripts\python.exe -m pytest server\tests\game\domain server\tests\game\ontology -q
```

Expected result: pass.

## Task 2: Add Graph Row Codecs

**Files:**
- Create: `server/src/db/graph_rows.py`
- Create: `server/tests/db/test_graph_rows.py`

- [ ] **Step 1: Write the failing row round-trip test**

Create `server/tests/db/test_graph_rows.py`:

```python
from src.db.graph_rows import graph_from_rows, graph_to_rows
from src.game.domain.graph import Graph, GraphEdge, GraphNode


def test_graph_rows_round_trip_nodes_edges_and_properties():
    graph = Graph(
        nodes={
            "town": GraphNode(id="town", type="location", properties={"name": "Town"}),
            "player": GraphNode(id="player", type="character", properties={"name": "Player"}),
        },
        edges={
            "located_at:player:town": GraphEdge(
                id="located_at:player:town",
                type="located_at",
                from_node_id="player",
                to_node_id="town",
                properties={"source": "test"},
            )
        },
    )

    node_rows, edge_rows = graph_to_rows("game-1", graph)

    assert node_rows[0].game_id == "game-1"
    assert edge_rows[0].from_node_id == "player"

    restored = graph_from_rows(node_rows, edge_rows)

    assert restored == graph
```

- [ ] **Step 2: Run the row test and confirm RED**

Run:

```powershell
& .\.venv\Scripts\python.exe -m pytest server\tests\db\test_graph_rows.py -q
```

Expected result: fail because `src.db.graph_rows` does not exist.

- [ ] **Step 3: Implement pure row codecs**

Create `server/src/db/graph_rows.py`:

```python
from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from src.game.domain.graph import Graph, GraphEdge, GraphNode


class GraphNodeRow(BaseModel):
    game_id: str
    node_id: str
    node_type: str
    properties: dict[str, object]


class GraphEdgeRow(BaseModel):
    game_id: str
    edge_id: str
    edge_type: str
    from_node_id: str
    to_node_id: str
    properties: dict[str, object]

    model_config = ConfigDict(populate_by_name=True)


def graph_to_rows(game_id: str, graph: Graph) -> tuple[list[GraphNodeRow], list[GraphEdgeRow]]:
    node_rows = [
        GraphNodeRow(game_id=game_id, node_id=node.id, node_type=node.type, properties=node.properties)
        for node in graph.nodes.values()
    ]
    edge_rows = [
        GraphEdgeRow(
            game_id=game_id,
            edge_id=edge.id,
            edge_type=edge.type,
            from_node_id=edge.from_node_id,
            to_node_id=edge.to_node_id,
            properties=edge.properties,
        )
        for edge in graph.edges.values()
    ]
    return node_rows, edge_rows


def graph_from_rows(node_rows: list[GraphNodeRow], edge_rows: list[GraphEdgeRow]) -> Graph:
    nodes = {
        row.node_id: GraphNode(id=row.node_id, type=row.node_type, properties=row.properties)
        for row in node_rows
    }
    edges = {
        row.edge_id: GraphEdge(
            id=row.edge_id,
            type=row.edge_type,
            from_node_id=row.from_node_id,
            to_node_id=row.to_node_id,
            properties=row.properties,
        )
        for row in edge_rows
    }
    return Graph(nodes=nodes, edges=edges)
```

- [ ] **Step 4: Run row tests and confirm GREEN**

Run:

```powershell
& .\.venv\Scripts\python.exe -m pytest server\tests\db\test_graph_rows.py -q
```

Expected result: pass.

- [ ] **Step 5: Run graph-related tests and lint**

Run:

```powershell
& .\.venv\Scripts\python.exe -m pytest server\tests\game\domain server\tests\game\ontology server\tests\db\test_graph_rows.py -q
& .\.venv\Scripts\python.exe -m ruff check server\src\game\domain\graph.py server\src\game\ontology\contract_graph.py server\src\db\graph_rows.py server\tests\game\domain server\tests\game\ontology\test_contract_graph.py server\tests\db\test_graph_rows.py
```

Expected result: tests pass and Ruff reports no findings.

## Self-Review

- This plan covers only the graph foundation: contract model, current-state projection, query helpers, and storage row codecs.
- It deliberately does not migrate the live turn engine or Supabase writes yet.
- No task writes to a live database.
- Execution added `belongs_to_race`, `grants_skill`, and `part_of_chapter` because `race` and `chapter` are graph nodes and their relationships must not stay as properties.
