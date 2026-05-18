# Theory-Driven Runtime Improvement Design

## Goal

Improve the game runtime according to `docs/research/THEORY.md`.

The theory says playable continuity requires three conditions at the same time:

```text
PlayableContinuity =
ExposedTransitionValidity + FictionContinuity + AgencyContinuity
```

The implementation plan must therefore avoid horizontal phases such as "fix
validity first, then continuity later." A player experiences all three
conditions in one turn. Each work unit must close a real gameplay situation
end to end.

## Design Rule

Use vertical gameplay slices.

```text
Completed Gameplay Slice =
ExposedTransitionValidity
+ FictionContinuity
+ AgencyContinuity
+ Evidence
```

A slice is not complete when it only improves one axis. It is complete only
when a player-facing situation has clear transition logic, coherent fiction,
preserved player agency, and test or QA evidence.

## Slice Template

Before implementing any slice, read:

- `docs/research/THEORY.md`
- this design spec

Do not start code changes until the slice has a written acceptance check
against all three theory conditions and evidence.

Each slice must include these sections before implementation:

1. Play Situation
   - The concrete player-facing situation.

2. Theory Risk
   - How the situation can break exposed transition validity, fiction
     continuity, or agency continuity.

3. Code Scope
   - The smallest relevant code area.

4. ExposedTransitionValidity
   - What constraint is operating.
   - Which visible current condition matters.
   - What kind of changed condition would make the outcome different.

5. FictionContinuity
   - Which previous state, scene, target, relationship, memory, or content fact
     must continue into this turn.
   - Which facts must not be invented by narration.

6. AgencyContinuity
   - How the player input remains recognizable through classification,
     resolution, narration, and suggestions.
   - How the player still has a plausible next move after failure, rejection,
     or partial execution.

7. Evidence
   - Focused pytest coverage, prompt payload assertions, QA transcript evidence,
     or a narrow combination of these.

## Slice Order

### 0. Target Field Contract Normalization

Play Situation:
The player or client names a target for an action, combat command, memory entry,
or narration payload.

Theory Risk:
If some layers say `target_id` while others say `target`, the system has two
parallel contracts for the same concept. That makes grounding and narration
harder to reason about, and future slices can accidentally preserve one path
while breaking the other.

Code Scope:

- Client combat command payloads
- Server API combat command schema
- LLM classify intent contract and examples
- Action builder intent parsing
- Combat trace/action domain models
- Runtime narration, memory, and related tests that serialize target fields

ExposedTransitionValidity:
There should be one public field for the selected target: `target`. The value is
still an existing raw id, but the field name is consistent across boundaries.

FictionContinuity:
Memory and narration payloads should preserve the same target under `target`
instead of splitting recent dialogue, combat traces, and rejection payloads
between two names.

AgencyContinuity:
Player intent should not depend on whether a caller used the old or new target
field. After this normalization, new prompts, client payloads, and tests should
use only `target`.

Evidence:
Focused server and client tests should prove combat commands, classify intents,
memory payloads, combat narration payloads, and prompt text no longer require
`target_id`. A repository search for `target_id` should return no source or test
hits after the slice is complete.

### 1. Protected Target Attack Rejection

Play Situation:
The player tries to attack a `protected=true` character.

Theory Risk:
If the game silently ignores the attack, agency breaks. If it lets the attack
through, transition validity breaks. If narration implies success or a new
conflict state, fiction continuity breaks.

Code Scope:

- `server/src/llm/context/classify_view.py`
- `server/src/llm/calls/classify/grounding.py`
- `server/src/game/runtime/flow/input.py`
- `server/src/locale/catalog/log.toml`
- `server/src/locale/prompts/graph_narrate/prompt.ko.md`
- Existing focused tests under `server/tests/llm/` and
  `server/tests/game/runtime/`

ExposedTransitionValidity:
The protected target remains visible, but is not attackable. Rejection should
expose that a protection constraint is active and that a different approach is
needed.

FictionContinuity:
The target remains present and protected. Narration must not imply the target
was hit, injured, killed, moved, or newly hostile unless the engine created
that state.

AgencyContinuity:
The player's attempted attack is acknowledged as an attempted attack. The
result should leave room for another valid approach such as talking, observing,
or choosing an unprotected target.

Evidence:
Assert classify context includes the target but excludes it from `can_attack`.
Assert grounding rejects protected target attacks. Assert graph input returns a
rejected result and rejection narration receives the protected-target reason.

### 2. Missing or Uncarried Item Use Rejection

Play Situation:
The player tries to use an item that does not exist in the exposed context or
is not carried by the player.

Theory Risk:
If the game invents the item, fiction continuity breaks. If it permits use,
transition validity breaks. If it replies with a generic block, agency weakens
because the player cannot tell what to change.

Code Scope:

- classify context inventory and location item projection
- classify grounding for `use`
- graph item use engine
- public rejection reason mapping
- item-use rejection tests

ExposedTransitionValidity:
The reason should show that only exposed or carried usable items can be used.
For uncarried visible items, the repair path can be to pick it up first. For an
unknown item, the repair path is to inspect available items or use a known one.

FictionContinuity:
The item must not appear in inventory, disappear from the scene, or produce an
effect unless state changes actually happened.

AgencyContinuity:
The player's intended item use should be preserved in the rejection context.
If a nearby item is visible, suggestions may point to pickup or inspect rather
than pretending the use succeeded.

Evidence:
Focused tests should distinguish unknown item, visible-but-uncarried item, and
carried-but-invalid item cases.

### 3. Trade Rejection for Resource or Relationship Conditions

Play Situation:
The player tries to buy, sell, or trade when gold, stock, equipment, or affinity
constraints block the transaction.

Theory Risk:
Trade depends on both resources and social state. A vague rejection makes the
economy and relationships feel arbitrary.

Code Scope:

- classify merchant and stock projection
- transfer engine
- public rejection reason mapping
- transaction tests

ExposedTransitionValidity:
The reason should identify the visible class of blocker: not enough gold,
wrong stock, equipped item, or low affinity. It should expose a plausible repair
path when one exists.

FictionContinuity:
Gold, inventory, merchant stock, equipment, and affinity must remain consistent
before and after the failed transaction.

AgencyContinuity:
The player's trade intent remains visible. The result can suggest earning gold,
choosing another item, unequipping before sale, or improving the relationship
when those options are grounded.

Evidence:
Focused transfer tests plus graph input rejection tests for public reason and
state preservation.

### 4. Social Check-Gated Action

Play Situation:
The player persuades, deceives, recruits, threatens, or otherwise socially
pressures an NPC.

Theory Risk:
If the game auto-succeeds, transition validity breaks. If it blocks without
procedure, agency breaks. If it reveals secrets without support, fiction
continuity breaks.

Code Scope:

- classify prompt and action check output
- pending roll creation
- preroll and postroll narration payloads
- dialogue memory payloads
- graph input and roll tests

ExposedTransitionValidity:
The player should see why a roll is required without seeing hidden DC, stat, or
future result. The visible reason should name the social uncertainty or risk.

FictionContinuity:
NPC traits, faction, public knowledge, secrets, relationship context, and recent
dialogue constrain the response. Narration must not reveal unsupported secrets
or create relationship changes not confirmed by the engine.

AgencyContinuity:
The player's original social tactic should survive into the pending roll and
the postroll narration. Failure should not close the scene; it should preserve a
next social or investigative move where grounded.

Evidence:
Tests should assert `check_reason` is persisted into pending roll and narration
payloads, preroll narration does not confirm success, and postroll narration
does not repeat the preroll as the result.

### 5. Investigation Check-Gated Action

Play Situation:
The player searches, inspects, reads, listens, or studies something where hidden
information or risk may be involved.

Theory Risk:
Investigation can break the theory by revealing unsupported clues, withholding
all feedback, or turning a player question into unrelated narration.

Code Scope:

- classify `inspect` and `query` distinction
- action check hints
- target view and scene anchor payloads
- graph narration prompt and tests

ExposedTransitionValidity:
The player should understand whether the action is simple observation, public
information query, or uncertain investigation requiring a check.

FictionContinuity:
Success may only surface information present in payloads or engine results.
Failure may describe confusion, pressure, or inconclusive observation, but not
new clues.

AgencyContinuity:
The player's inspected target or topic remains recognizable. Failure should
leave room to inspect another target, ask an NPC, use an item, or move, if those
options are grounded.

Evidence:
Tests should cover inspect/query classification, check reason propagation, and
narration constraints for success versus failure.

### 6. Quest Accept or Abandon

Play Situation:
The player accepts or abandons an active quest.

Theory Risk:
Quest state is durable continuity. If the quest status, log, narration, and
suggestions disagree, the world stops remembering commitments.

Code Scope:

- classify active quest projection
- quest engine
- narration result cards
- front-state and suggestion tests

ExposedTransitionValidity:
The quest can be accepted or abandoned only when a grounded quest id is active
and the transition is legal.

FictionContinuity:
Quest status, active quest id, log text, and narration must describe the same
commitment state.

AgencyContinuity:
The player's explicit accept or abandon intent is preserved. Suggestions should
reflect the new quest state and should not offer impossible quest actions.

Evidence:
Focused quest engine tests plus graph action or graph input tests checking
state, narration payload, and suggestions.

### 7. Corpse Looting or Item Pickup

Play Situation:
The player takes an item from the location or from a corpse.

Theory Risk:
This crosses location, possession, visibility, and sometimes death state. If any
part is loose, items duplicate, vanish, or become usable without a valid path.

Code Scope:

- classify context `location_items` and `corpses`
- grounding for pickup and loot transfer
- transfer engine
- front-state inventory and location rendering tests

ExposedTransitionValidity:
The item must be visible in the current location or in a grounded corpse
inventory. The outcome should make it clear that possession changed because the
item was reachable.

FictionContinuity:
The item moves from its old owner or location into the player inventory exactly
once. Narration must not invent extra loot.

AgencyContinuity:
The player's target item remains recognizable. If the item or corpse is
ambiguous, the system should avoid choosing silently and leave a way to inspect
or specify.

Evidence:
Tests should assert grounding, graph changes, front-state changes, and ambiguous
loot rejection.

### 8. Repeated NPC Dialogue

Play Situation:
The player keeps talking to the same NPC across multiple turns.

Theory Risk:
Dialogue can remain grammatically coherent while forgetting promises, previous
answers, boundaries, or recent refusals. That breaks fiction continuity and
agency.

Code Scope:

- `recent_dialogue`
- `related_memory`
- target-first dialogue selection
- `graph_narrate` dialogue prompt
- memory context tests

ExposedTransitionValidity:
Dialogue itself often does not change transition state, but any request for
secrets, commitments, items, recruitment, or quest movement must still be routed
through the correct grounded action or check.

FictionContinuity:
The NPC should not mechanically repeat the same answer when recent dialogue is
available. It must preserve public knowledge, previous answer shape, and
boundaries without treating memory summaries as transition authority.

AgencyContinuity:
The newest player utterance must be answered directly when grounded. The NPC
should respond to repetition, escalation, or clarification as such.

Evidence:
Tests should assert target-first dialogue payload selection and prompt payload
shape. QA transcript evidence can verify repeated dialogue behavior with turn
numbers.

### 9. Multi-Intent Input

Play Situation:
The player gives a compound command where some intents are valid and others are
ambiguous or impossible.

Theory Risk:
Dropping the whole input weakens agency. Executing impossible parts breaks
transition validity. Narrating unsupported skipped parts breaks fiction
continuity.

Code Scope:

- classify prompt multi-intent rules
- action builder
- classified action execution loop
- partial execution tests

ExposedTransitionValidity:
Each executed action must be grounded and legal. Invalid parts should not sneak
through because another part is valid.

FictionContinuity:
Only executed state changes become fiction. Narration should not describe
invalid skipped actions as completed.

AgencyContinuity:
Valid parts of the player's compound command should execute when possible.
Invalid or ambiguous parts should be acknowledged without erasing the rest of
the input.

Evidence:
Tests should cover valid-then-invalid, invalid-then-valid, and mixed
multi-intent cases with final state and narration assertions.

## Cross-Slice Acceptance Criteria

Every implementation slice must answer these four lines before it is complete:

```text
ExposedTransitionValidity: The player can understand the relevant allowed,
blocked, or check-gated condition without hidden DCs or secret facts.

FictionContinuity: Previous facts and the new result remain one consistent
world state, and narration does not invent unsupported facts.

AgencyContinuity: The player input remains recognizable, and failure,
rejection, or partial execution leaves grounded next choices.

Evidence: A focused test, prompt payload assertion, QA transcript citation, or
explicitly justified combination verifies the claim.
```

## Verification Strategy

Prefer focused pytest coverage before broad runs.

Useful starting points:

- `server/tests/llm/context/test_classify_view.py`
- `server/tests/llm/calls/test_classify_grounding.py`
- `server/tests/game/runtime/test_graph_input.py`
- `server/tests/game/runtime/test_graph_action_turn.py`
- `server/tests/game/engines/test_graph_transfer.py`
- `server/tests/game/engines/test_graph_item_use.py`
- `server/tests/game/engines/test_graph_quest.py`
- `server/tests/game/runtime/test_memory_context.py`

For QA claims, read transcripts under `qa_test/agency/<agent>/transcript.md`
and cite turn numbers. Do not use an automatic reviewer as the source of truth.

## Non-Goals

- Do not rebuild the whole runtime around new theory classes.
- Do not expose hidden DCs, secret facts, private timers, or complete alternate
  solution lists.
- Do not explain every trivial action.
- Do not let the LLM invent transition authority.
- Do not treat bounded memory as authoritative graph state.
- Do not refactor unrelated runtime boundaries while implementing a slice.

## First Implementation Target

Start with Protected Target Attack Rejection.

It is the smallest slice with existing coverage and a clear theory mapping:

- The target is present in the fiction.
- `protected=true` is a transition-relevant fact.
- The attack must be blocked.
- The blocked attempt must be narrated as blocked, not successful.
- The player should retain another possible approach.

This first slice should establish the work pattern for the rest:

1. Write or tighten focused tests.
2. Apply the smallest code and prompt changes.
3. Verify the slice against all three theory conditions.
4. Record any recurring acceptance language that should become a shared helper
   or QA checklist only after repetition proves it useful.
