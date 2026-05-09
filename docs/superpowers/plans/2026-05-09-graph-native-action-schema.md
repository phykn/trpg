# Graph-Native Action Schema Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the documented graph-native `Action` shape a real classify contract while keeping current playable dispatch stable.

**Architecture:** Add a domain `Action` model with the documented fields: `verb`, `what`, `from`, `to`, `with`, `how`, and `note`. The classify parser accepts the new `Action` JSON and converts it through a tested adapter into the existing `Verb` bridge until graph-native engines replace legacy dispatch. The client still never receives raw `Action`.

**Tech Stack:** Python 3.12+, Pydantic v2, pytest, Ruff, root `.venv` on Windows.

---

## Scope

This slice makes `Action` live at the classify contract boundary.

It does not rewrite all dispatch handlers to consume `Action` directly, and it does not migrate engine effects to graph-native `GraphChange` yet. Those belong to Phase 5.

## File Structure

- `server/src/game/domain/action.py`
  - New `Action`, `ActionOutput`, and adapter functions.
- `server/src/llm/calls/classify/schema.py`
  - Parse new Action JSON and return the existing `JudgeOutput` bridge.
- `server/src/locale/prompts/classify/prompt.ko.md`
  - Change examples and catalog from legacy `Verb` JSON to `Action` JSON.
- `server/tests/game/domain/test_action_contract.py`
  - Unit tests for Action validation and adapter behavior.
- `server/tests/llm/calls/test_classify_action_schema.py`
  - Parser tests proving classify accepts Action JSON and still accepts legacy Verb JSON during migration.
- `docs/superpowers/plans/2026-05-09-graph-first-game-roadmap.md`
  - Mark Phase 4 complete and point the next planning target to Phase 5.

## Task 1: Action Model Tests

**Files:**
- Create: `server/tests/game/domain/test_action_contract.py`

- [x] **Step 1: Write failing Action tests**

Add tests that assert:

- `Action` accepts alias keys `from` and `with`,
- extra result fields such as `success` are rejected,
- `Action(verb="pass")` converts to legacy `Verb(name="wait")`,
- `transfer` maps `what/from/to/how` to `item_id/from_id/to_id/mode`,
- `attack` maps `what` to `target_ids` and `with` to `skill_id`,
- `query` maps `what="exits"` to `modifiers.topic`.

Run:

```powershell
& .\.venv\Scripts\python.exe -m pytest server\tests\game\domain\test_action_contract.py -q
```

Expected RED: `src.game.domain.action` does not exist.

## Task 2: Action Model And Adapter

**Files:**
- Create: `server/src/game/domain/action.py`

- [x] **Step 1: Implement Action model**

Implement:

- `ActionVerb`
- `Action`
- `ActionOutput`
- `action_to_verb`
- `verb_to_action`
- `action_output_to_judge_output`

- [x] **Step 2: Run Action tests**

Run:

```powershell
& .\.venv\Scripts\python.exe -m pytest server\tests\game\domain\test_action_contract.py -q
```

Expected GREEN: Action contract tests pass.

## Task 3: Classify Parser Integration

**Files:**
- Create: `server/tests/llm/calls/test_classify_action_schema.py`
- Modify: `server/src/llm/calls/classify/schema.py`

- [x] **Step 1: Write failing classify parser tests**

Add tests that assert:

- `validate_judge_output` accepts Action JSON: `{"actions":[{"verb":"move","to":"loc_01"}]}`,
- converted output is the existing `JudgeOutput` with `Verb(name="move", modifiers.destination="loc_01")`,
- `pass` converts to `wait`,
- legacy `{"name":"wait"}` JSON still works during migration,
- invalid Action JSON raises `ValidationError`.

Run:

```powershell
& .\.venv\Scripts\python.exe -m pytest server\tests\llm\calls\test_classify_action_schema.py -q
```

Expected RED: parser only understands legacy `name` verbs.

- [x] **Step 2: Integrate Action parser path**

Update `validate_judge_output` so it detects Action JSON when an action object has `verb`. Convert it to `JudgeOutput` through `action_output_to_judge_output`.

- [x] **Step 3: Run classify parser tests**

Run:

```powershell
& .\.venv\Scripts\python.exe -m pytest server\tests\llm\calls\test_classify_action_schema.py server\tests\llm\calls\test_classify_validate_judge_output.py -q
```

Expected GREEN: new and legacy classify parser tests pass.

## Task 4: Prompt And Roadmap

**Files:**
- Modify: `server/src/locale/prompts/classify/prompt.ko.md`
- Modify: `docs/superpowers/plans/2026-05-09-graph-first-game-roadmap.md`
- Modify: `docs/superpowers/plans/2026-05-09-graph-native-action-schema.md`

- [x] **Step 1: Update classify prompt**

Change the output shape and examples to Action JSON:

```json
{"actions": [{"verb": "move", "to": "herb_garden"}]}
{"actions": [{"verb": "attack", "what": ["bandit_01"]}]}
{"actions": [{"verb": "query", "what": "exits"}]}
```

Keep a short migration note out of the prompt; the LLM should emit only the new shape.

- [x] **Step 2: Update roadmap**

Mark Phase 4 complete. Set the next planning target to Phase 5 graph-native engines.

- [x] **Step 3: Re-read docs**

Check the plan and roadmap for stale “final Action remains” wording.

## Task 5: Verification

**Files:**
- Modify: all files above

- [x] **Step 1: Run focused tests**

Run:

```powershell
& .\.venv\Scripts\python.exe -m pytest server\tests\game\domain\test_action_contract.py server\tests\llm\calls\test_classify_action_schema.py server\tests\llm\calls\test_classify_validate_judge_output.py server\tests\llm\calls\test_classify_grounding.py server\tests\game\flow\test_query.py -q
```

Expected: pass.

- [x] **Step 2: Run Ruff**

Run:

```powershell
& .\.venv\Scripts\python.exe -m ruff check server\src\game\domain\action.py server\src\game\domain\verb.py server\src\llm\calls\classify server\tests\game\domain\test_action_contract.py server\tests\llm\calls\test_classify_action_schema.py
```

Expected: `All checks passed!`

- [x] **Step 3: Run full server tests**

Run:

```powershell
& .\.venv\Scripts\python.exe -m pytest -q
```

Expected: pass.

## Stop Point

After this slice, Phase 4 is complete: confirmation, classify id grounding, query-only dispatch, and the graph-native Action classify contract are live. The next work is Phase 5: moving engines from legacy mutations to validated `GraphChange`.
