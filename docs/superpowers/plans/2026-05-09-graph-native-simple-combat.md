# Graph-Native Simple Combat Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a graph-native combat planner that resolves fights in a small number of player exchanges without asking the LLM to decide damage, death, or victory.

**Architecture:** Keep this slice additive. The new planner reads `Graph`, emits `GraphChange`, and returns a graph combat progress object; it does not wire live `/turn` or replace legacy `game.engines.combat`. Combat math is deterministic and paced so ordinary attacks finish in about three exchanges, while the fourth exchange always produces a terminal outcome.

**Tech Stack:** Python 3.12+, Pydantic v2, pytest, Ruff, root `.venv` on Windows.

---

## Scope

This slice covers player-versus-enemy graph combat planning.

It includes:

- starting combat from one enemy target,
- attack, cast, defend, and flee exchanges,
- HP/MP graph changes,
- enemy defeat modes that do not require death,
- forced terminal resolution on the fourth exchange.

It does not include:

- live `/turn` integration,
- loot transfer,
- quest trigger checks,
- combat narration prompts,
- companion AI,
- the final 4-stat migration of all existing seed/runtime data.

## File Structure

- `server/src/game/domain/combat.py`
  - New graph combat progress/action models shared by engine and context.
- `server/src/game/engines/graph_combat.py`
  - New pure graph-native combat planner.
  - Owns `GraphCombatResult`, planning rules, and validation errors.
- `server/tests/game/engines/test_graph_combat.py`
  - Unit tests for start validation, attack pacing, cast MP cost, flee, defend, forced fourth exchange, and graph-change validity.
- `docs/superpowers/plans/2026-05-09-graph-first-game-roadmap.md`
  - Record that graph-native simple combat planning exists.

## Design Rules

The planner follows the current docs:

- The graph is the source of truth for participants, location, HP, MP, skill ownership, and equipment.
- LLM-visible combat output is not part of this slice, but the planner result separates graph changes from public trace text so later narration can avoid raw damage.
- `character_defeat` is not automatically death. Enemy defeat writes `defeat_mode` and a status marker.
- New combat start validates same-location visibility and does not mutate graph facts.
- The fourth exchange never leaves `outcome="ongoing"`.

## Task 1: Combat Start Tests

**Files:**
- Create: `server/tests/game/engines/test_graph_combat.py`

- [x] **Step 1: Write failing start tests**

Create tests that build a graph with `player_01`, `goblin_01`, and `town_gate` connected through `located_at` edges.

Assert:

```python
result = plan_combat_start(graph, "player_01", "goblin_01")
assert result.state.location_id == "town_gate"
assert result.state.player_id == "player_01"
assert result.state.enemy_ids == ["goblin_01"]
assert result.state.round == 1
assert result.state.outcome == "ongoing"
assert result.changes == []
```

Also assert missing target, non-character target, dead actor, and different-location target raise `GraphCombatError`.

- [x] **Step 2: Run tests to verify RED**

Run:

```powershell
& .\.venv\Scripts\python.exe -m pytest server\tests\game\engines\test_graph_combat.py -q
```

Expected RED: `src.game.engines.graph_combat` does not exist.

## Task 2: Combat Start Planner

**Files:**
- Create: `server/src/game/engines/graph_combat.py`

- [x] **Step 1: Implement start models and start planner**

Implement:

```python
class GraphCombatError(ValueError): ...
class GraphCombatState(BaseModel): ...
class GraphCombatResult(BaseModel): ...
def plan_combat_start(graph: Graph, player_id: str, enemy_id: str) -> GraphCombatResult: ...
```

Rules:

- player and enemy must be different character nodes,
- both must be able to fight (`hp > 0`, `max_hp > 0`, `alive` not false),
- both must share the same `located_at` location,
- state stores location id, participant ids, side map, round `1`, enemy ids, trace, and `outcome="ongoing"`.

- [x] **Step 2: Run start tests**

Run:

```powershell
& .\.venv\Scripts\python.exe -m pytest server\tests\game\engines\test_graph_combat.py -q
```

Expected: combat-start behavior passes; exchange behavior may still fail until Task 4.

## Task 3: Exchange Tests

**Files:**
- Modify: `server/tests/game/engines/test_graph_combat.py`

- [x] **Step 1: Write failing exchange tests**

Add tests that assert:

- one attack lowers enemy HP and advances to round 2,
- three ordinary attacks against the fixture enemy produce a terminal victory,
- cast requires a known skill and enough MP, then deducts MP,
- flee ends combat with outcome `fled` and no graph mutation,
- defend advances the exchange and reduces incoming player HP loss,
- a fourth exchange forces a terminal outcome even if no one reaches 0 HP,
- every returned change can be applied by `apply_graph_change`.

- [x] **Step 2: Run tests to verify RED**

Run:

```powershell
& .\.venv\Scripts\python.exe -m pytest server\tests\game\engines\test_graph_combat.py -q
```

Expected RED: `plan_combat_exchange` or exchange behavior is missing.

## Task 4: Exchange Planner

**Files:**
- Modify: `server/src/game/engines/graph_combat.py`

- [x] **Step 1: Implement action and exchange planner**

Implement:

```python
CombatActionKind = Literal["attack", "cast", "defend", "flee"]

class GraphCombatAction(BaseModel):
    kind: CombatActionKind
    target_id: str | None = None
    skill_id: str | None = None

def plan_combat_exchange(
    graph: Graph,
    state: GraphCombatState,
    actor_id: str,
    action: GraphCombatAction,
) -> GraphCombatResult: ...
```

Rules:

- only `outcome="ongoing"` can continue,
- only the state player can act in this slice,
- attack uses `stats.body` first and falls back to legacy `stats.STR` during migration,
- cast requires a `knows_skill` edge, skill kind/type compatible with attack, and enough MP,
- no raw damage appears in trace entries,
- ordinary attack pace is high enough for three attacks to defeat the fixture enemy,
- enemy response happens only if combat is still ongoing and the fourth-exchange force rule has not ended it,
- enemy defeat sets `hp=0`, `defeat_mode="unconscious"`, and appends `"defeated"` to status,
- player defeat sets `hp=0`, `defeat_mode="downed"`, and appends `"downed"` to status,
- the fourth exchange compares remaining HP ratios and returns a terminal outcome.

- [x] **Step 2: Run exchange tests**

Run:

```powershell
& .\.venv\Scripts\python.exe -m pytest server\tests\game\engines\test_graph_combat.py -q
```

Expected GREEN: all graph combat tests pass.

## Task 5: Roadmap And Verification

**Files:**
- Modify: `docs/superpowers/plans/2026-05-09-graph-first-game-roadmap.md`
- Modify: `docs/superpowers/plans/2026-05-09-graph-native-simple-combat.md`

- [x] **Step 1: Update roadmap**

Add one current-state bullet:

```markdown
- `server/src/game/engines/graph_combat.py` plans graph-native short combat exchanges.
```

Update Phase 5 status to mention combat planning.

- [x] **Step 2: Run focused tests**

Run:

```powershell
& .\.venv\Scripts\python.exe -m pytest server\tests\game\engines\test_graph_combat.py server\tests\game\runtime\test_runtime_apply.py -q
```

Expected: pass.

- [x] **Step 3: Run Ruff**

Run:

```powershell
& .\.venv\Scripts\python.exe -m ruff check server\src\game\engines\graph_combat.py server\tests\game\engines\test_graph_combat.py
```

Expected: `All checks passed!`

- [x] **Step 4: Run full server tests**

Run:

```powershell
& .\.venv\Scripts\python.exe -m pytest -q
```

Expected: pass.

## Stop Point

After this slice, graph-native combat planning exists but is not live. The next work should either wire the graph-native planner into a graph runtime dispatch path, or add a public combat-narration context that hides raw damage while exposing HP/MP state words.
