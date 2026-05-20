# SERVER Theory

## Current claim

The optimal server architecture is runtime-state-authoritative transition orchestration with graph-authoritative relational facts.

The runtime snapshot is the source for player-visible payloads. The graph is the source of truth for durable world relations. LLM output is proposal, evidence, narration, or persisted narration metadata only after runtime commits it through bounded paths.

## Minimum condition

A server change is well-placed when it satisfies all of these:

- Graph-derived facts remain relational-graph SSOT.
- Durable graph mutations are planned as `GraphChange` transitions by engines, or as explicitly bounded runtime transitions that are equivalent to a graph-change plan and dirty-tracked.
- Bounded runtime transitions coordinate session flow, pending state, LLM/narration, logs, progress commits, persistence, and dirty tracking; they do not decide reusable game semantics.
- Reusable game semantics move to `game.engines`: DC/stat selection, success/failure consequences, relation/node fact changes, quest/growth/reward effects, combat/inventory/recovery invariants, or any durable world fact that should be testable without runtime, repo, LLM, log, or wire concerns.
- Progress, pending confirmation/roll state, logs, history, and dialogue are committed as runtime records, not hidden inside prompt or client payload state.
- Wire and db adapt committed state at boundaries.
- API routes stay glue.

## Boundary or decision forced

Put a change where its authority lives:

- Relation or node fact: graph/domain/query/engine path.
- Reusable rule or durable world-fact planning: engine path.
- Turn orchestration, pending state, LLM call, log/history/dialogue commit: runtime path.
- Persistence concern: db adapter or row codec.
- Server-client shape: wire model/projection.
- HTTP concern: API route.

Reject changes that let LLM text, client payloads, or prompt payloads become authoritative world state. Also reject runtime code that owns reusable game-rule semantics merely because it is convenient to commit there.
