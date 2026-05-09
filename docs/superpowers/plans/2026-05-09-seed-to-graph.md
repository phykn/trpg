# Seed To Graph Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Use superpowers:test-driven-development for every production change. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a graph-native game start path that turns scenario seed files and player creation input into a persisted `Graph` plus `GameProgress`.

**Architecture:** Keep the existing legacy `init_game` flow unchanged while adding a graph-first initialization path beside it. A pure seed builder creates all graph nodes first, then relationship edges, then progress. A flow wrapper loads scenario seed data, reuses existing seed invariant checks, builds the graph bundle, and saves it through `GraphRepo`.

**Tech Stack:** Python 3.12+, Pydantic v2, pytest, Ruff, root `.venv` on Windows.

---

## Scope

This plan implements Phase 2 from `2026-05-09-graph-first-game-roadmap.md`.

It does not migrate `/session/init`, `/turn`, combat, UI, LLM context, or legacy save loading. The new graph init path is additive so the live game stays playable while graph-first runtime work continues.

## File Structure

- `server/src/game/seed/graph_seed.py`
  - New pure builder for seed entities, player input, `start.json`, and `player_template.json`.
  - Produces `SeedGraphBundle(graph, progress)`.
- `server/src/game/seed/__init__.py`
  - Exports graph seed builder types.
- `server/src/game/flow/init_graph.py`
  - New graph-native initialization flow that loads seed data and saves graph/progress through `GraphRepo`.
- `server/tests/game/seed/test_graph_seed.py`
  - Unit tests for graph shape, hidden/reward placement, and progress.
- `server/tests/game/flow/test_init_graph.py`
  - Flow tests for profile lookup, race errors, persistence, and broken seed blocking start.
- `docs/superpowers/plans/2026-05-09-graph-first-game-roadmap.md`
  - Mark Phase 2 as the active next plan after implementation.

## Task 1: Seed Graph Builder

**Files:**
- Create: `server/src/game/seed/__init__.py`
- Create: `server/src/game/seed/graph_seed.py`
- Test: `server/tests/game/seed/test_graph_seed.py`

- [x] **Step 1: Write failing seed graph tests**

Create `server/tests/game/seed/test_graph_seed.py` with tests that call a wished-for `build_seed_graph(...)` API. Cover these behaviors:

```python
from src.game.domain.entities import (
    Chapter,
    Character,
    Connection,
    Item,
    Location,
    Quest,
    QuestRewards,
    QuestTrigger,
    Race,
    Skill,
)
from src.game.flow.init import PlayerInput
from src.game.seed.graph_seed import build_seed_graph


def _skill() -> Skill:
    return Skill(
        id="slash",
        name="베기",
        type="attack",
        target="single",
        primary_stat="STR",
    )


def test_build_seed_graph_creates_nodes_edges_and_progress():
    bundle = build_seed_graph(
        profile_name="default",
        player=PlayerInput(name="테스터", race_id="human", gender="female"),
        races={"human": Race(id="human", name="인간", description="", racial_skill_ids=["slash"])},
        locations={
            "town": Location(
                id="town",
                name="마을",
                item_ids=["potion"],
                connections=[Connection(target_id="forest", difficulty="normal")],
            ),
            "forest": Location(id="forest", name="숲"),
        },
        items={"potion": Item(id="potion", name="물약")},
        skills={"slash": _skill()},
        npcs={},
        quests={},
        chapters={},
        start={"start_location_id": "town", "active_subject_id": None, "active_quest_id": None},
        template={"id": "player_01", "inventory_ids": [], "equipment": {}, "gold": 0, "xp_pool": 0},
        game_id="game-1",
        locale="ko",
    )

    graph = bundle.graph

    assert graph.nodes["player_01"].type == "character"
    assert "default" not in graph.nodes
    assert graph.edges["located_at:player_01:town"].type == "located_at"
    assert graph.edges["belongs_to_race:player_01:human"].type == "belongs_to_race"
    assert graph.edges["knows_skill:racial:player_01:slash"].properties["source"] == "racial"
    assert graph.edges["grants_skill:human:slash"].type == "grants_skill"
    assert graph.edges["located_at:potion:town"].type == "located_at"
    assert graph.edges["connects_to:town:forest"].properties["difficulty"] == "normal"
    assert bundle.progress.game_id == "game-1"
    assert bundle.progress.player_id == "player_01"
    assert bundle.progress.locale == "ko"
```

Add separate tests for:

```python
def test_build_seed_graph_keeps_reward_items_out_of_visible_placement():
    reward = Item(id="reward_sword", name="보상 검")
    quest = Quest(
        id="quest_01",
        title="첫 의뢰",
        giver_id="elder",
        difficulty="easy",
        triggers=[QuestTrigger(id="reach_forest", name="숲 도착", type="location_enter", target_id="forest")],
        rewards=QuestRewards(items=["reward_sword"]),
        status="pending",
    )
    bundle = build_seed_graph(
        profile_name="default",
        player=PlayerInput(name="테스터", race_id="human", gender="female"),
        races={"human": Race(id="human", name="인간", description="")},
        locations={"town": Location(id="town", name="마을"), "forest": Location(id="forest", name="숲")},
        items={"reward_sword": reward},
        skills={},
        npcs={"elder": Character(id="elder", name="장로", race_id="human", location_id="town", level=1)},
        quests={"quest_01": quest},
        chapters={},
        start={"start_location_id": "town", "active_subject_id": "elder", "active_quest_id": None},
        template={"id": "player_01"},
        game_id="game-1",
        locale="ko",
    )

    edge_types = {edge.type for edge in bundle.graph.edges.values() if edge.from_node_id == "reward_sword"}
    assert edge_types == {"reward_of"}
```

Expected RED: import error for `src.game.seed.graph_seed`.

- [x] **Step 2: Implement the minimal builder**

Create `server/src/game/seed/graph_seed.py` with:

- `SeedGraphBundle(BaseModel)` containing `graph: Graph` and `progress: GameProgress`.
- `build_seed_graph(...)` that accepts loaded seed dictionaries, player input, start/template dictionaries, game id, and locale.
- node creation for character, item, location, quest, skill, race, and chapter.
- edge creation for location, inventory, equipment, race, skills, companions, relations, connections, quest giver, triggers, rewards, and chapters.
- player creation logic matching legacy defaults: template id, template inventory/equipment, starting location, selected race skills, `RULES.death.revive_coins`, max HP/MP, full HP/MP, and first visited location.

Do not create graph nodes or graph properties for `profile.json`, profile id, or `world.md`. They are profile metadata, not game-world facts.

- [x] **Step 3: Run seed graph tests**

Run:

```powershell
& .\.venv\Scripts\python.exe -m pytest server\tests\game\seed\test_graph_seed.py -q
```

Expected GREEN after implementation.

## Task 2: Graph Init Flow

**Files:**
- Create: `server/src/game/flow/init_graph.py`
- Test: `server/tests/game/flow/test_init_graph.py`

- [x] **Step 1: Write failing graph init flow tests**

Create tests for the wished-for `init_graph_game(...)` API:

```python
import json
from pathlib import Path

import pytest

from src.db.graph_local_fs import LocalFsGraphRepo
from src.db.local_fs import LocalFsScenarioRepo
from src.game.domain.errors import ProfileMalformed, ProfileNotFound, RaceNotFound
from src.game.flow.init import PlayerInput
from src.game.flow.init_graph import init_graph_game


def _write_seed(root: Path) -> None:
    pdir = root / "default"
    pdir.mkdir(parents=True)
    (pdir / "world.md").write_text("world", encoding="utf-8")
    (pdir / "start.json").write_text(json.dumps({"start_location_id": "town"}), encoding="utf-8")
    (pdir / "player_template.json").write_text(json.dumps({"id": "player_01"}), encoding="utf-8")
    (pdir / "races").mkdir()
    (pdir / "races" / "human.json").write_text(
        json.dumps({"id": "human", "name": "인간", "description": ""}, ensure_ascii=False),
        encoding="utf-8",
    )
    (pdir / "locations").mkdir()
    (pdir / "locations" / "town.json").write_text(
        json.dumps({"id": "town", "name": "마을"}, ensure_ascii=False),
        encoding="utf-8",
    )


async def test_init_graph_game_persists_graph_and_progress(tmp_path):
    profiles = tmp_path / "profiles"
    saves = tmp_path / "saves"
    _write_seed(profiles)

    repo = LocalFsGraphRepo(str(saves))
    bundle = await init_graph_game(
        "default",
        PlayerInput(name="테스터", race_id="human", gender="female"),
        repo,
        LocalFsScenarioRepo(str(profiles)),
        locale="ko",
    )

    loaded_graph = await repo.load_graph(bundle.progress.game_id)
    loaded_progress = await repo.load_progress(bundle.progress.game_id)

    assert loaded_graph == bundle.graph
    assert loaded_progress == bundle.progress
    assert loaded_graph.nodes["player_01"].properties["name"] == "테스터"
```

Add tests that `init_graph_game` raises `ProfileNotFound`, `RaceNotFound`, and `ProfileMalformed` for the same cases as legacy init.

Expected RED: import error for `src.game.flow.init_graph`.

- [x] **Step 2: Implement graph init flow**

Create `server/src/game/flow/init_graph.py` that:

- checks `scenario_repo.profile_exists(profile_name)`,
- loads races, locations, items, skills, NPCs, quests, chapters, start, and template with `asyncio.gather`,
- runs existing `check_scenario(Scenario(...))`,
- raises `ProfileMalformed` on violations,
- raises `RaceNotFound` when the selected race is missing,
- creates a `game_id` with the same timestamp/hex shape as legacy init,
- calls `build_seed_graph(...)`,
- saves `bundle.graph` and `bundle.progress` through `GraphRepo`,
- returns the bundle.

- [x] **Step 3: Run graph init flow tests**

Run:

```powershell
& .\.venv\Scripts\python.exe -m pytest server\tests\game\flow\test_init_graph.py -q
```

Expected GREEN after implementation.

## Task 3: Documentation And Verification

**Files:**
- Modify: `docs/superpowers/plans/2026-05-09-graph-first-game-roadmap.md`
- Modify: `docs/superpowers/plans/2026-05-09-seed-to-graph.md`

- [x] **Step 1: Mark Phase 2 status**

Update the roadmap so Phase 2 points at this detailed plan and says it is implemented additively. Do not mark later phases done.

- [x] **Step 2: Run focused tests**

Run:

```powershell
& .\.venv\Scripts\python.exe -m pytest server\tests\game\seed server\tests\game\flow\test_init_graph.py server\tests\db\test_graph_local_fs.py -q
```

Expected: pass.

- [x] **Step 3: Run Ruff on touched files**

Run:

```powershell
& .\.venv\Scripts\python.exe -m ruff check server\src\game\seed server\src\game\flow\init_graph.py server\tests\game\seed server\tests\game\flow\test_init_graph.py
```

Expected: `All checks passed!`

- [x] **Step 4: Run full server tests**

Run:

```powershell
& .\.venv\Scripts\python.exe -m pytest -q
```

Expected: pass.

## Stop Point

After Phase 2, graph game creation exists but live API still starts legacy saves. Next phase is Runtime Envelope: load graph/progress/log tails into a graph-first runtime object and provide a compatibility conversion only where old flows still require `GameState`.
