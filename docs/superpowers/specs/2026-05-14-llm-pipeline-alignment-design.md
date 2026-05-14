# LLM Pipeline Alignment Design

## Goal

Align the server and client with `docs/plan/00-llm-pipeline.md`.

The player-facing reason for this work is simple: the client must know whether a result succeeded or failed before streamed narration text arrives, so it can color that narration immediately.

## Scope

This design covers:

- Server graph action/input/confirm/roll stream order.
- Server response-level outcome for narration coloring.
- Pending-state guard before text input classification.
- Roll handling after a pending roll is submitted.
- Complete removal of partial roll outcomes.
- Client stream parsing and log typing updates.

This design does not change LLM prompt style or add new game mechanics beyond the continuation needed for pending roll actions.

## Result Outcome

Add a response-level outcome:

```ts
outcome: "success" | "failure" | "neutral"
```

Use it only for client presentation, especially streamed narration color. The LLM does not choose this value.

Mapping:

- `success`: action applied successfully, roll success, combat favorable result.
- `failure`: action rejected, roll fail, combat unfavorable result.
- `neutral`: movement, query answer, confirmation required, roll required, cancellation, simple dialogue/pass.

No `partial` outcome exists.

## Remove Partial Roll Results

Rolls become binary:

- `success`: total roll meets or exceeds `required_roll`.
- `fail`: anything below `required_roll`.

Remove the “missing by exactly one” partial window.

Server changes:

- `compute_grade()` no longer returns `partial_success`.
- `Grade` no longer includes `partial_success`.
- `RollLogEntry.result` is `success | fail`.
- `roll._roll_result()` returns only `success | fail`.
- Rule config entries for `partial_success` are removed if no remaining code uses them.

Client changes:

- `RollResult` is `success | fail`.
- Roll log UI removes the partial style and label.
- Korean locale removes `ko.roll.partial`.

## Stream Contract

All graph NDJSON stream endpoints use this order:

```json
{"type":"result","payload":{...GraphActionResponse}}
{"type":"narration_delta","text":"..."}
{"type":"final","payload":{...GraphActionResponse}}
```

Meanings:

- `result`: engine result has been saved and contains authoritative state plus outcome.
- `narration_delta`: LLM narration text chunks for the already-known result.
- `final`: narration persistence is complete and state is final.

If no narration is needed, the stream may emit `result` followed by `final` with the same payload.

Intro stream follows the same shape: initial state as `result`, intro narration as `narration_delta`, final state as `final`.

## Server Runtime Flow

The action runtime is split into clear phases:

1. Load runtime.
2. Guard pending state.
3. Build or receive action.
4. Run engine dispatch.
5. Save graph/progress/result card.
6. Build `GraphActionResponse` with `outcome`.
7. For stream endpoints, emit `result`.
8. Ask LLM for narration if needed.
9. Save narration and dialogue/history metadata.
10. Emit or return final response.

Non-stream endpoints return only the final response, but internally still save the result before narration.

## Pending Guard For Text Input

`/graph/input` checks pending state before appending the player log and before classify.

If `pending_confirmation` exists, the request fails through the existing pending-confirmation error path. The client must resolve it with `/graph/confirm`.

If `pending_roll` exists, the request fails through the pending-roll error path. The client must resolve it with `/graph/roll`.

This prevents new text from being classified while the game is waiting for a player choice or roll.

## Roll Continuation

Submitting a pending roll:

1. Loads and validates the pending roll.
2. Computes binary roll result.
3. Saves the roll log and clears `pending_roll`.
4. Loads the stored pending action.
5. Continues that action through the normal action pipeline.

First implementation rule: roll success/failure affects response outcome and narration context. It does not yet introduce separate success/failure graph branches unless the engine action already supports them.

This keeps the current game mechanics small while matching the document’s requirement that the stored game action resumes after roll submission.

## Failure Handling

Engine-level “cannot do this now” failures return a graph action response instead of becoming a bare HTTP 422 when possible.

Use `outcome: "failure"` for these rejected results.

Request-shape errors remain HTTP 422. Examples: invalid JSON, malformed action payload, missing confirmation id, wrong roll id.

## Client Changes

`client/services/api.ts` parses both state-changing and narration events from the new stream contract.

Client behavior:

- On `result`, update state and remember `outcome`.
- On `narration_delta`, append temporary narration text using the remembered outcome color.
- On `final`, replace temporary state with final server state.

Client types add response-level `outcome`.

The old `delta` event type is removed from tests and parsing once server and client are updated together.

## Tests

Server tests:

- Input with pending confirmation or roll does not classify or append a player log.
- Stream endpoints emit `result` before any `narration_delta`.
- Final event is emitted after narration persistence.
- Roll partial case now becomes fail.
- Roll submission clears pending roll and continues the stored action path.
- Action rejection returns `outcome: "failure"` where the request shape is valid.

Client tests:

- Stream parser handles `result`, `narration_delta`, `final`.
- Temporary narration uses the latest response outcome.
- Roll log types and UI no longer mention partial.

Full verification:

- Server: `.\.venv\Scripts\python.exe -m pytest server\tests -q`
- Client: `npm run lint`, `npx tsc --noEmit`, and focused Jest tests for `services/api` and log rendering.

