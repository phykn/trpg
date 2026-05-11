# dev_test Social Quest Branching Design

## Goal

Add one small `dev_test` QA slice that proves NPC relationship changes alter quest resolution. The slice validates two game goals:

- NPC conversation is not only narration; it can leave a durable graph consequence.
- One quest completes through different social choices, with different relationship outcomes.

This is not a full social system. It is a narrow gameplay test that keeps `dev_test` useful as a feature-validation profile.

## Player Experience

The player finds a small supply dispute in the existing test hub/supply area. The quartermaster reports a missing supply item. The village resident has taken it for a sympathetic reason. The guide observes the outcome.

The player can resolve the quest in three ways:

- Report the resident to the quartermaster.
- Hear the resident out, then persuade the quartermaster to forgive or regularize the use.
- Quietly return the supply item without escalating the dispute.

Each route completes the same quest but changes relationships differently. The result appears in logs, quest state, and later NPC context.

## Scenario Additions

Add a new quest to `scenarios/dev_test`:

- `q_missing_supplies`
- Title: `보급품 누락`
- Giver: `quartermaster_npc`
- Target NPC: `village_resident`
- Required item or clue: a new missing supply item, for example `missing_supply_bundle`
- Initial status: `locked` or `pending`, matching existing quest-offer conventions

The quest has one route marker property, `resolution_route`, so the engine records how it was resolved without adding branching data structures.

Add or update seed content:

- Add the missing supply item.
- Add quartermaster hints that point the player toward asking about missing supplies.
- Add resident hints that expose the sympathetic reason.
- Add guide hints that frame this as a relationship/choice test.
- Add initial `relation` edges where the route needs a starting affinity. Existing seed conversion supports `relations` maps on character records.

## Engine Behavior

Add a narrow social-resolution path for `dev_test` style quests.

When a `speak` action targets a visible NPC and uses existing classifier intents, the runtime checks for this quest before treating the input as pure narration. Use current `speak.how` values instead of adding new enum values: `friendly` for reassurance or mediation, `hostile` for accusation or pressure, and `deceptive` for concealment.

For this slice, the behavior is rule-based:

- If the player accuses or reports the resident while `q_missing_supplies` is available or active, complete the quest with route `report`.
- If the player first gets the resident's reason and then persuades the quartermaster, complete the quest with route `mediate`.
- If the player returns or uses the missing supply item without accusation, complete the quest with route `quiet_return`.

Each route updates relation edges:

- `report`: quartermaster affinity increases; resident affinity decreases.
- `mediate`: resident affinity increases; guide affinity increases; quartermaster affinity increases slightly.
- `quiet_return`: resident affinity increases; quartermaster affinity does not change; add a resident help flag.

Put relation and quest-change planning in small pure functions under `game/engines/`. Keep request orchestration in `game/runtime/`. LLM classification identifies `speak` actions, but the engine decides whether quest and relation changes happen.

## Data Model

Use existing graph concepts first:

- `relation` edges carry `affinity`.
- Quest node properties carry `status`, `triggers_met`, `rewards`, and the new `resolution_route`.
- Route flags live on relation edge properties, for example `flags: ["helped_quietly"]`.

Do not add a broad reputation system, faction model, or generic dialogue tree.

## UI and Feedback

The client does not need a new screen for the first slice.

The player sees:

- A quest offer or quest panel entry for `보급품 누락`.
- A GM or action log that names the chosen resolution.
- Suggested next inputs after relevant dialogue when narration metadata provides them.

Relation changes are verified through tests and QA save inspection in this slice. Relationship labels stay out of the UI until the mechanic proves useful.

## Error Handling

Invalid or premature social attempts return a visible response.

Examples:

- If the player tries to mediate before learning the resident's reason, return a narrative response that implies more information is needed.
- If the resident or quartermaster is not visible, do not resolve the quest.
- If the quest is already completed, do not apply relation changes again.

Repeated completion is idempotent: one route is recorded once.

## Tests

Add focused server tests for:

- Seed conversion creates the expected relation and quest graph edges.
- Reporting route completes `q_missing_supplies`, records `resolution_route=report`, and changes affinities.
- Mediation route requires the resident reason flag, then completes with `resolution_route=mediate`.
- Quiet return route completes with `resolution_route=quiet_return` and records the resident help flag.
- Repeating the same social completion does not duplicate rewards or relation deltas.

Add or update manual QA in `tester.md`:

- Start a new `dev_test` game.
- Ask the quartermaster about missing supplies.
- Ask the resident about the missing supplies.
- Complete the quest through each route in separate new games.
- Record whether the next desired action was clear and whether the NPC reactions felt meaningfully different.

## Success Criteria

This slice is successful when a tester can say:

- The social choice changed the game state, not only the narration.
- The same quest had at least two meaningfully different resolutions.
- NPC reactions made the player understand why their choice mattered.
- Existing combat, trade, rest, item, and level-up `dev_test` checks still pass.

## Deferred

Do not include these in the first pass:

- Generic dialogue trees.
- Multi-faction reputation.
- Relationship UI redesign.
- LLM-generated quest branches.
- Long-term consequences outside `dev_test`.
- Full social combat.
