# Graph First Game Roadmap Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:writing-plans for each phase before code changes. Use superpowers:test-driven-development for implementation. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move the game from legacy entity-first runtime toward a graph-first ontology runtime without breaking playable flows during the migration.

**Architecture:** The graph is the source of truth for game facts. Progress state stores only turn count, pending confirmation/check, combat progress, locale, logs, and other request-continuation data. The migration proceeds by adding graph-native seams first, then moving storage, seed loading, engines, context, wire mapping, and UI one subsystem at a time.

**Tech Stack:** Python 3.12+, Pydantic v2, FastAPI, Supabase Postgres/Storage, pytest, Ruff, Expo React Native client. Use the root `.venv` on Windows.

---

## Current State

- `docs/` now describes the target graph-first design.
- `server/src/game/domain/graph.py` defines contract graph models, graph changes, and invariants.
- `server/src/game/domain/graph_query.py` provides graph query helpers.
- `server/src/game/ontology/contract_graph.py` projects legacy `GameState` into the contract graph.
- `server/src/db/graph_rows.py` converts graph nodes and edges to future table rows.
- `server/src/db/graph_local_fs.py` and `server/src/db/graph_supabase.py` save/load graph nodes, graph edges, and progress.
- `server/src/game/seed/graph_seed.py` builds a graph from scenario seed data.
- `server/src/game/flow/init_graph.py` starts a graph game beside the existing legacy init path.
- `server/src/game/runtime/` loads graph runtime state and can convert it to legacy `GameState` during migration.
- `server/src/game/flow/confirmation.py` stores and resolves pending confirmations for quest actions and high-impact verbs.
- `server/src/llm/calls/classify/grounding.py` rejects classify ids that are outside the current graph-derived surroundings view.
- `server/src/game/flow/query.py` answers public information queries without advancing time or mutating graph facts.
- `server/src/game/engines/graph_move.py` plans graph-native character movement as validated `GraphChange` objects.
- `server/src/game/engines/graph_transfer.py` plans graph-native item transfer, equip, and unequip changes.
- `server/src/game/engines/graph_item_use.py` plans graph-native non-damage item-use changes.
- `server/src/game/engines/graph_quest.py` plans graph-native quest status transitions.
- `server/src/game/runtime/apply.py` applies graph change batches atomically to runtime state.
- `server/src/game/engines/graph_rest.py` plans graph-native safe-rest recovery changes.
- `server/src/game/engines/graph_growth.py` plans graph-native XP, level-up, and skill-learning changes.
- `server/src/game/domain/combat.py` defines graph-native combat progress models shared by engine and context.
- `server/src/game/engines/graph_combat.py` plans graph-native short combat exchanges.
- `server/src/llm/context/graph_combat.py` builds LLM-safe graph combat context without raw HP/MP/damage.
- `GameProgress.graph_combat_state` persists graph-native combat progress separately from legacy combat state.
- `server/src/game/runtime/combat.py` dispatches graph-native combat actions inside graph runtime state.
- `server/src/game/runtime/dispatch.py` routes confirmed graph-native actions to graph planners.
- `server/src/wire/graph_to_front.py` builds a minimal public state snapshot from graph runtime.
- `server/src/game/runtime/turn.py` executes and persists one confirmed graph action.
- Separate graph API routes can initialize a graph game and execute one confirmed graph action.
- Graph API routes now require explicit confirmation before quest accept/abandon and combat-start actions mutate the graph.
- Graph sessions can classify player text into one grounded `Action` and feed it into the confirmation-aware graph request layer.
- Graph `query` actions answer from visible graph facts through a `message` without advancing time or mutating graph/progress.
- Confirmed graph actions append factual `act` log cards and graph front state exposes `log`.
- Graph init may append one LLM-written GM narration for the first place; later move actions remain system-card-only.
- Graph runtime can create a deterministic pending quest offer when no active quest or visible offer exists.
- Automatic graph quest offers append a system log card so the player can notice the new work without LLM narration.
- The live flow still uses legacy `GameState`, legacy entity tables, and old derived ontology graph in several places.

## Migration Rule

Do not replace multiple runtime layers in one step.

Each phase must finish with:

- a small implementation plan,
- failing tests before production code,
- compatibility with existing playable flows,
- focused tests for the changed layer,
- full server tests when the changed layer touches runtime behavior.

## Phase 0: Graph Foundation

**Status:** Complete.

**Purpose:** Make the graph contract real in code before changing persistence or gameplay.

**Includes:**

- `Graph`, `GraphNode`, `GraphEdge`
- `GraphChange`
- graph invariant validation
- graph query helpers
- legacy `GameState` to contract graph projection
- graph row codecs

**Done when:**

- contract graph rejects broken edge endpoints,
- item placement conflicts are impossible,
- character location conflicts are impossible,
- race/chapter relationships are edges, not properties,
- graph rows round-trip through JSON-safe values.

**Current verification:**

```powershell
& .\.venv\Scripts\python.exe -m pytest server\tests\game\domain server\tests\game\ontology server\tests\db\test_graph_rows.py -q
& .\.venv\Scripts\python.exe -m ruff check server\src\game\domain\graph.py server\src\game\domain\graph_query.py server\src\game\ontology\contract_graph.py server\src\db\graph_rows.py server\tests\game\domain server\tests\game\ontology\test_contract_graph.py server\tests\db\test_graph_rows.py
```

## Phase 1: Graph Persistence Boundary

**Status:** Complete.

**Purpose:** Add graph-native persistence without moving live gameplay yet.

**Includes:**

- `GraphSaveRepo` protocol or graph methods on the existing repo boundary
- LocalFs graph persistence for tests and QA
- Supabase graph row read/write adapter over `graph_nodes`, `graph_edges`, and `game_progress`
- progress row codec for non-graph runtime state
- transaction shape for applying a batch of `GraphChange`

**Done when:**

- a graph can be saved and loaded without legacy entity tables,
- progress can be saved and loaded without graph facts,
- malformed graph rows fail on load,
- graph row writes are JSON-safe,
- no production code writes to Supabase during tests.

**Do not do in this phase:**

- migrate `/turn`,
- migrate combat,
- remove `entities`,
- change client payload shape.

## Phase 2: Seed To Graph

**Status:** Complete. Implemented additively; the live API still uses legacy `init_game`.

**Purpose:** Turn scenario seed files into a graph at game creation.

**Includes:**

- seed loader that creates all nodes first,
- seed edge builder for location, ownership, quest, race, skill, and chapter relationships,
- seed validation before save,
- graph init path beside legacy `init_game` so existing playable flows stay unchanged during migration.

**Done when:**

- a minimal profile becomes a valid graph,
- broken references block game start,
- hidden items and reward-only items do not leak into visible placement,
- quest bundles have giver, target, trigger, reward, and status,
- `profile.json` and `world.md` stay outside graph facts.

**Do not do in this phase:**

- generate quests with LLM,
- change combat rules,
- change UI.

## Phase 3: Runtime Envelope

**Status:** Complete. `/turn` still uses the legacy runtime.

**Purpose:** Define graph-first `GameRuntimeState`.

**Includes:**

- `graph`,
- `progress`,
- log/history/dialogue tails,
- locale,
- compatibility conversion to current `GameState` where old flows still need it.

**Done when:**

- runtime state loads from graph tables plus progress row,
- pending confirmation/check survives reload,
- combat progress survives reload,
- graph facts are not duplicated in progress.

**Do not do in this phase:**

- rewrite all engines,
- remove old `GameState`.

## Phase 4: Action And Dispatch

**Status:** Complete. Quest accept/abandon, attack-start, steal, dangerous-rest, dangerous item-use confirmation, graph-view id validation, query-only dispatch, and the graph-native `Action` classify contract are live.

**Purpose:** Make player input flow use the new `Action` and confirmation contract.

**Includes:**

- new action schema matching `docs/01-contract.md`,
- classify post-processing that validates ids against graph views,
- confirmation pending for quest accept, attack-start, steal, dangerous item use, dangerous rest,
- query path that cannot mutate graph or time,
- dispatch that routes to graph-native engines where available and legacy fallback elsewhere.

**Done when:**

- quest offers are not auto-accepted,
- attack-start asks for confirmation outside combat,
- confirmation cancel changes no graph facts,
- pending state blocks unrelated input,
- query returns public information only.

## Phase 5: Graph-Native Engines

**Status:** Started. Graph-native move, item-placement, non-damage item-use, quest-status, runtime apply, safe-rest, XP, level-up, skill-learning, and short-combat planning exist, but live `/turn` still uses the legacy paths.

**Purpose:** Move rule execution from entity mutation to `GraphChange`.

**Order:**

1. move
2. transfer and equipment
3. item use
4. quest accept, abandon, complete, fail
5. rest
6. growth and skill learn/use
7. combat

**Done when:**

- each engine returns `GraphChange` and effects,
- a shared apply path validates every change,
- engine tests assert graph changes instead of legacy field mutation,
- old entity mutation paths are unused for migrated actions.

**Do not do in one pass:**

- migrate all engines together,
- change LLM prompts before context is graph-native.

## Phase 6: Context And Wire From Graph

**Purpose:** Build LLM context and client state from graph instead of legacy state fields.

**Includes:**

- `surroundings`
- `target_view`
- `storyGraph`
- `hero`
- `place`
- `quest`
- `combat`

**Done when:**

- hidden items do not appear in public views,
- hidden connections do not appear as exits,
- quest offers are distinct from active quests,
- HP/MP state words are server-computed,
- client receives no raw `Action`, `NarrateAction`, or `GraphChange`.

## Phase 7: UI Pending And Combat UX

**Purpose:** Make the client reflect the graph-first runtime contract.

**Includes:**

- pending confirmation modal or panel,
- confirm/cancel route usage,
- input disabling while pending,
- combat status panel,
- combat suggestions as natural-language input helpers,
- quest offer display separate from active quest display.

**Done when:**

- accepting a quest requires explicit confirmation,
- starting a fight requires explicit confirmation,
- cancel leaves graph unchanged,
- combat is playable without action-specific client APIs.

## Phase 8: Automatic Quest Generation

**Purpose:** Keep players supplied with work using guarded content drafts.

**Includes:**

- quest need detector,
- engine-chosen quest templates,
- locked draft schema,
- LLM writes text fields only,
- quest bundle validator,
- graph changes for accepted bundle,
- offer state that does not auto-activate.

**Done when:**

- generated quest bundle includes quest, related target, needed NPC/item/monster nodes, edges, triggers, and reward budget,
- failed validation discards the whole bundle,
- generated quest starts as an offer,
- weak LLM cannot change locked ids, numbers, rewards, or trigger type.

## Phase 9: Combat And Growth Redesign

**Purpose:** Apply the simplified combat and stat/resource model from docs.

**Includes:**

- 4-stat model,
- HP/MP resource state words,
- 2-3 exchange combat target,
- forced 4th exchange end,
- combat outcome modes,
- growth choices instead of automatic stat application.

**Done when:**

- combat normally resolves within 2-3 player inputs,
- 4th exchange always resolves,
- LLM never receives raw damage numbers,
- level-up requires a player choice.

## Phase 10: Legacy Removal

**Purpose:** Remove old entity-first assumptions after graph-first paths are live.

**Includes:**

- remove legacy ontology graph,
- remove entity-table runtime dependency,
- update `server/AGENTS.md` and `server/README.md`,
- delete compatibility converters no longer used,
- update QA harness expectations.

**Done when:**

- runtime save/load uses graph tables,
- old `entities` table is not required for active game saves,
- tests no longer depend on legacy relation fields as source of truth,
- docs, AGENTS, and README agree.

## Execution Order

1. Phases 0-4 are complete.
2. Phase 5 is adding graph-native planners one engine at a time.
3. Stop before replacing live `/turn` paths, because that is where graph/runtime drift is easiest to introduce.
4. Continue one migration layer at a time.

## Risk Register

| risk | mitigation |
|---|---|
| graph and legacy state drift apart | use projection only as temporary compatibility; do not write both as independent truths |
| Supabase schema blocks local tests | keep pure row codecs and LocalFs graph repo before Supabase adapter |
| weak LLM invents ids or rewards | engine chooses locked ids, numbers, templates, and reward budgets |
| UI implies action already happened | confirmation responses must emit `confirmation_required` before narrative |
| full migration becomes too large | each phase gets its own implementation plan and TDD cycle |

## Next Planning Target

Continue graph-first client integration: surface pending confirmations, graph logs, and graph input routes without exposing raw graph changes to the client.
