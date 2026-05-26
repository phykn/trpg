# LLM Base Generated Runtime Design

## Purpose

`llm_base` moves the project from seed-heavy scenario playback toward the architecture described in `docs/theory.md`: the seed is a contract, the LLM proposes world changes, the server validates them, the graph stores accepted facts, and the UI shows those facts as discoveries or memories.

The first implementation target is intentionally narrow: `Memory + Clue Write` for a generated `white_isle_llm` profile. Existing seed-heavy scenarios may remain as legacy compatibility and comparison paths, but new design work should treat `contract.json + generated runtime` as the main direction.

## Goals

- Load a generated profile from `contract.json`.
- Keep existing public API routes and stream event order for the MVP.
- Let the writer propose only `add_memory` and `add_clue` patches.
- Persist accepted memories and clues in the runtime graph, not only in prose logs.
- Let the narrator speak only from accepted patches and existing graph state.
- Expose accepted memories and clues in front state so the UI can show them outside narration text.
- Preserve legacy scenario tests while the generated runtime becomes the new direction.

## Non-Goals

- Full dynamic locations, NPCs, items, quest beats, rollback UI, or patch repair loops.
- A separate player-facing generated endpoint.
- A new stream event for accepted patches in the MVP.
- Removing legacy seed runtime in this branch.
- Migrating existing seed-heavy scenarios to `contract.json` in this branch.

## Architecture

Generated mode is selected by a scenario-loading boundary, not by route code directly reading files. The boundary answers whether a profile has a generated contract and loads it if present.

```text
contract exists -> generated runtime
contract missing -> legacy seed runtime
```

Proposed modules:

- `game/domain/story_contract.py`: Pydantic model for `contract.json`.
- `game/domain/story_patch.py`: Pydantic model for writer patches.
- `llm/calls/story_write.py`: structured writer call for patch proposals.
- `llm/context/story_write_context.py`: graph, contract, action, and recent history context.
- `game/runtime/flow/generated_input.py`: generated input orchestration.
- `game/engines/story_patch_validator.py`: contract, budget, and graph validation.
- `wire/graph/to_front.py`: front-state projection for discoveries or journal entries.

Routes stay thin. `/session/graph/init` and `/session/{game_id}/graph/input/stream` choose generated or legacy flow internally through session/runtime loading, preserving current client integration.

Legacy seed-heavy runtime remains as a compatibility path only. New LLM-base work should target generated runtime first, and any legacy changes should be limited to keeping existing tests and comparison profiles working.

## Runtime Flow

Writer patches are applied only after the engine accepts the player action. Failed or blocked actions must not become world facts.

```text
input stream
-> classify
-> derive StoryWriteIntent
-> resolve or accept engine action
-> story_write
-> validate patch
-> apply accepted patch to graph
-> graph_narrate
-> result / narration_delta / final
```

`StoryWriteIntent` is derived from current classifier/action output after normalization. It should not depend on vague labels unless those labels exist in stable runtime data.

Initial values:

- `none`: do not call writer.
- `memory_candidate`: action can create a remembered choice or trace.
- `clue_candidate`: action can reveal new information.
- `both`: action can create both.

No patch is persisted for rejected actions, pending confirmations, blocked rolls, invalid actions, or writer failures.

For this spec, an accepted action means the current runtime flow has resolved enough to commit game state for that turn. It excludes confirmation prompts, pending roll requests, validation failures, and command paths that return only an error or "nothing happened" response.

## Graph Persistence

Accepted patches become graph-backed facts. They must not exist only in `log_entries`, `history_entries`, `exchange_entries`, or narration text.

MVP patch operations:

```json
{ "op": "add_memory", "id": "mem_...", "summary": "...", "stability": "campaign" }
{ "op": "add_clue", "id": "clue_...", "title": "...", "summary": "...", "stability": "scene" }
```

Preferred implementation is to reuse the existing knowledge shape with a constrained kind:

```text
GraphNode(type="knowledge", properties.kind="memory" | "clue")
```

Link generated facts with existing graph edges where possible:

```text
player_or_subject --has_knowledge--> knowledge(kind="memory" | "clue")
current_location --has_knowledge--> knowledge(kind="clue"), when the clue belongs to a place
quest_or_item --has_knowledge--> knowledge(kind="clue"), when the clue belongs to that object
```

Do not use `knowledge --located_at--> location` in the MVP. Current graph invariants allow `located_at` only from `character` or `item` to `location`; place-scoped clues should use the existing `location --has_knowledge--> knowledge` shape.

The MVP uses constrained `knowledge` nodes only. First-class `memory` or `clue` node types are deferred until implementation proves that existing `knowledge(kind=...)` nodes cannot support narration, validation, and front-state projection.

Each generated fact should include:

- stable id
- summary or title
- origin/provenance, including writer and turn id
- stability (`scene`, `chapter`, `campaign`, or `core` when applicable)
- relevant links to player, current location, or subject when available

The graph fact is the source of truth. UI and narration recall must read accepted facts from graph-backed state rather than diagnostics.

For the MVP, rejected writer responses are diagnostics only: emit them through the existing stderr diagnostic path (`engine_diag` / `llm_diag`) with game id, turn, operation ids, and rejection reasons. Do not add a persistent patch ledger or database table in the first PR. Accepted facts are persisted in the graph; rejected proposals are developer evidence, not game state.

## Contract Loading

`contract.json` owns the generated profile contract:

- world identity
- fixed elements
- forbidden moves
- tone and Korean register
- generation budgets
- allowed patch operations
- stability defaults

Minimum MVP schema:

```json
{
  "id": "white_isle_llm",
  "world": { "title": "...", "locale": "ko" },
  "fixed": [],
  "forbid": [],
  "tone": { "register": "합니다체", "person": "second" },
  "budgets": { "patches_per_turn": 1, "new_terms_per_turn": 1 },
  "allowed_ops": ["add_memory", "add_clue"],
  "stability_defaults": { "add_memory": "campaign", "add_clue": "scene" }
}
```

Unknown top-level fields should fail validation for the MVP so schema drift is visible early.

The scenario boundary should expose contract loading with a method such as `read_contract_json(profile, missing_ok=True)` or a generated loader built over `ScenarioRepo`. Route handlers must not inspect `scenarios/<profile>` directly.

`scenarios/white_isle_llm/contract.json` is the first generated profile fixture. It may keep minimal compatibility files only when current profile listing, player setup, or tests need them.

Compatibility files in `white_isle_llm` should be treated as bootstrapping shims. They must not become a second seed-heavy story source beside `contract.json`.

## Writer

The writer is not the narrator. It returns structured JSON only.

Input:

- contract
- current graph summary
- accepted action context
- recent history
- player input
- `StoryWriteIntent`
- generation budget

Output:

- `reason`
- `patches`
- `narration_brief`

The writer may return an empty patch list. Empty output is valid when the accepted action does not need a new world fact.

The writer must not return final prose for the player. `narration_brief` is private context for the narrator and may be ignored if validation rejects every patch.

## Validation

The validator rejects patches that:

- use an operation outside the MVP allowlist
- exceed per-turn or per-scene budget
- duplicate an existing id
- reference missing graph nodes
- attempt to mutate core/fixed contract elements
- violate `contract.forbid`
- introduce too many new proper nouns or concepts
- try to decide the player's choice or emotion

MVP validation failure behavior is conservative: if any patch in a writer response is invalid, reject the whole writer response, emit diagnostics, and continue the accepted action/narration without generated facts. Automatic repair, rollback, and per-patch subset application are deferred.

Silent partial writes are not allowed. Tests should prove that a mixed valid/invalid response persists no generated facts and records the rejection reason.

## Narration

The narrator receives accepted patch summaries and the updated graph state. It must not treat rejected writer content as true. Player-facing Korean follows existing repo rules: second-person polite `합니다체`, `당신`, and canonical `기술` terminology.

Generated facts should be narrated diegetically:

- good: "젖은 표의 반쪽이 당신의 손에 남습니다."
- bad: "[시스템] memory node가 생성되었습니다."

## Front State And UI

The MVP keeps the current stream event order:

```text
result -> narration_delta -> final
```

No player-facing `patch_accepted` event is added in the first pass. Instead, `FrontState` gains a small surface for accepted graph facts, for example:

```ts
discoveries: {
  memories: JournalEntry[];
  clues: JournalEntry[];
}
```

The UI can render this as a compact journal, discovery tray, or world tray. The exact component can stay minimal, but accepted memories and clues must be visible outside prose narration.

The stream shape remains compatible by carrying the updated front state through existing `result` and `final` payloads. Client parsing should not need to understand a new event type for this MVP.

Projection rules are part of the server contract:

- Include only accepted graph facts represented as `GraphNode(type="knowledge", properties.kind in {"memory", "clue"})`.
- Include only facts whose `properties.visibility` is `"player"` or missing; `"private"` and `"developer"` facts stay out of `FrontState`.
- Include only facts linked by `has_knowledge` from the player, the current location, the active quest, or a currently visible subject. Do not expose arbitrary NPC-owned knowledge.
- Sort by accepted turn order, newest last, using provenance turn id as the stable order key.
- Scope `scene` facts to the current scene/location, while `chapter`, `campaign`, and `core` facts remain visible after leaving the scene.

## Error Handling

- Writer timeout or unavailable model: no patch, continue action/narration.
- Writer JSON parse or schema failure: reject patch, record diagnostics.
- Contract violation: reject patch, record diagnostics, no player-facing error.
- Duplicate id or dangling reference: reject patch.
- Graph apply failure: do not partially persist the patch; surface diagnostics for developers.
- Legacy profile without contract: use legacy seed runtime.

The safest MVP behavior is "do not write" rather than "write possibly wrong state."

## Testing

Focused tests should cover:

- `white_isle_llm` init loads `contract.json` and enters generated runtime.
- Legacy `white_isle` still uses legacy seed runtime.
- Rejected, pending, blocked, or invalid actions do not create memory or clue facts.
- Accepted clue/memory candidate actions call writer and persist accepted patches.
- Validator rejects unsupported ops and contract violations.
- Narration context includes accepted patches only.
- Front state includes accepted memories and clues.
- Stream event order remains `result -> narration_delta* -> final`.

Verification before broader implementation:

```bash
.venv/bin/python -m pytest server/tests/game/runtime -q
.venv/bin/python -m pytest server/tests/api/test_graph_session_routes.py -q
.venv/bin/ruff check server/ agency/
```

Client tests should be added or updated when the front-state field and UI surface are implemented.

## Suggested Implementation Order

1. Add contract loading boundary and `white_isle_llm/contract.json` fixture.
2. Add story patch models and validator with unit tests.
3. Add generated graph apply for `knowledge(kind="memory" | "clue")`.
4. Add `StoryWriteIntent` derivation and generated input flow after action acceptance.
5. Add writer LLM call with schema validation and no-op failure behavior.
6. Project accepted facts into `FrontState`.
7. Add minimal client journal/discovery surface.

## Open Implementation Decisions

- Exact `StoryWriteIntent` derivation rules from current classifier/action output.
- Minimal compatibility files needed for `white_isle_llm` profile listing and new-game setup.
