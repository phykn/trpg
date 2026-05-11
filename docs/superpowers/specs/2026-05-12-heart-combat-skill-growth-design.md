# Heart Combat And Skill Growth Design

## Goal

Replace direct HP-damage combat with a short heart-based exchange system. Combat should stay easy to explain, keep the engine authoritative, and make skills and items meaningful without turning the game into a full deckbuilder.

The design keeps the existing core rule: the player chooses, the engine decides, and the LLM narrates only the resolved outcome.

## Player Resources

Player level ranges from 1 to 10.

At level 1, the player starts with:

- HP 5 / max HP 5
- MP 5 / max MP 5
- one starting skill

Long-term caps:

- max HP 10
- max MP 10
- three learned skills
- skill tier 3 per skill

HP is the long-term survival resource. MP is the skill resource. Combat hearts are temporary and exist only inside one combat.

## Combat Hearts

Combat starts with:

- player hearts: 3 / 3
- enemy hearts: 3 / 3

Combat ends when either side reaches 0 hearts. There is no forced round limit.

If enemy hearts reach 0, the player wins. If player hearts reach 0, the player loses and takes real HP damage equal to the enemy's remaining hearts.

Example:

```text
Player hearts: 0
Enemy hearts: 2
Result: player loses, player HP -2
```

Victory does not reduce real HP by default. Any victory cost should come from explicit effects, consumed MP, consumed items, status effects, or story consequences that the engine applies.

## Turn Structure

Each combat turn has one basic action and at most one support.

```text
basic action + optional support -> DC calculation -> player roll -> heart result
```

Allowed support:

- no support
- one skill
- one item

The player cannot attach both a skill and an item to the same action. The player cannot attach two skills or two items.

## Basic Actions

The first version supports four basic combat actions.

| Action | Success | Failure |
|---|---|---|
| Attack | enemy hearts -1 | player hearts -1 |
| Defend | player hearts +1, capped at 3 | player hearts -1 |
| Flee | combat ends with no HP loss | player hearts -1 |
| Social pressure | enemy hearts -1 | player hearts -1 |

Social pressure covers intimidation, persuasion, surrender pressure, and similar actions. The first implementation resolves social pressure success as enemy hearts -1. Surrender, truce, or combat interruption can be added later as explicit engine-owned effect templates.

## Roll And DC

Only the player rolls.

Use a d20. A roll succeeds when it is greater than or equal to final DC.

Base formula:

```text
DC = 11 + (enemy_level - player_level) - support_bonus + situation_modifier
```

Clamp final DC to:

```text
minimum DC: 6
maximum DC: 18
```

Stats are not included in combat DC. `body`, `agility`, `mind`, and `presence` remain useful for non-combat checks, character flavor, and personalized skill generation.

Situation modifiers should be rare:

| Situation | Modifier |
|---|---|
| normal | 0 |
| clearly favorable | -1 or -2 |
| clearly unfavorable | +1 or +2 |

## Skills

Skills are learned capabilities that spend MP to support one basic action. A skill can be attached to a turn only if the player knows it, can pay its MP cost, and the skill supports the selected action.

Skill storage remains graph-native:

- skill is a `skill` node
- ownership is a `knows_skill` edge
- skill tier is stored on the skill node or edge, depending on the implementation plan

The player can know at most three skills. Each skill can reach tier 3.

The first effect templates are:

| Template | Effect |
|---|---|
| `dc_down` | reduce final DC for a matching action |
| `extra_heart_damage` | on attack success, enemy hearts lose 1 additional heart |
| `prevent_heart_loss` | on failure, prevent one player heart loss |
| `escape_boost` | reduce final DC for flee actions |

Support effects run in two phases. DC modifiers apply before the roll. Heart-result effects apply after the roll succeeds or fails.

Baseline skill balance:

| Strength | Cost | Effect |
|---|---|---|
| small | MP 1 | DC -1 |
| normal | MP 2 | DC -2 |
| strong | MP 3 | DC -3 or a template-specific effect |

Skill upgrade baseline:

| Tier | Example upgrade |
|---|---|
| 1 | MP 2, DC -2 |
| 2 | MP 2, DC -3 |
| 3 | MP 3, DC -3 plus a template-specific rider |

Implementation can tune these numbers, but it should preserve the rule that MP buys lower risk or a specific tactical effect, not raw arbitrary damage.

## Personalized Skill Generation

Level-up can offer LLM-personalized skills based on player behavior.

The LLM may propose:

- skill name
- short description
- mood tags
- suggested role

The LLM must not decide:

- MP cost
- DC bonus
- heart damage
- target count
- cooldowns
- ownership

The engine maps LLM proposals to allowed effect templates. If a proposal cannot be mapped safely, the engine discards it.

Inputs for personalization:

- recent action history
- repeated verbs or tactics
- preferred narrative style
- current known skills
- character stats as flavor hints, not DC modifiers

Examples:

| Observed style | Candidate direction |
|---|---|
| frequent attacks | attack support skill |
| frequent defense | defend or prevent-loss skill |
| frequent fleeing or repositioning | flee or mobility skill |
| frequent intimidation or persuasion | social pressure skill |
| repeated fire imagery | fire-themed name and description |

## Items

Items support actions the same way skills do, but their economy is different.

| Kind | Role |
|---|---|
| consumable | stronger one-use support |
| equipment | repeatable small conditional support |
| special item | large bonus against a matching tag, enemy, or situation |

Baseline item balance:

| Item kind | Example effect |
|---|---|
| consumable | DC -2 to -4, then consumed |
| equipment | conditional DC -1 |
| special item | DC -4 against matching tag or situation |

Items should make preparation matter. They should not stack with skills on the same turn.

Examples:

| Item | Use |
|---|---|
| smoke bomb | support flee, DC -4, consumed |
| throwing knife | support attack, DC -3, consumed |
| old shield | support defend, DC -1, equipped |
| silver dust | support attack against undead or monster tags, DC -4, consumed |

## Level-Up

Level-up choices appear after combat or quest completion at a safe point. They should not interrupt combat.

The player earns level-up eligibility from engine-awarded experience. When reward application leaves `xp_pool >= current_level`, the engine creates one pending level-up choice set at the next safe point. Confirming the level-up consumes `current_level` XP, increases level by 1, and applies the selected growth. Level 10 is the cap.

The first implementation creates at most one pending level-up per reward application. If leftover XP is still high enough for another level after confirmation, it carries forward until the next reward application or another safe-point growth check.

Each level-up grants one choice.

Choice types:

- max HP +1, capped at 10
- max MP +1, capped at 10
- learn a new skill, if the player knows fewer than three skills
- upgrade an existing skill, if it is below tier 3

When the player already knows three skills, new skill choices are not offered in the first implementation. Replacing or forgetting skills can be considered later if the three-slot limit feels too rigid.

## Starting Skill

A level 1 player starts with one skill so MP matters from the first combat.

The starting skill comes from initial profile, class, or declared character style.

Examples:

| Style | Starting skill direction |
|---|---|
| melee | attack DC reduction |
| guardian | defend DC reduction or heart-loss prevention |
| agile | flee or mobility support |
| social | intimidation or persuasion support |
| magic | higher-MP skill with stronger support |

## Data Model Changes

`GraphCombatState` should move away from round-limited direct HP exchange and store the temporary heart contest.

Expected state fields:

- location id
- player id
- enemy ids
- participants and sides
- player hearts
- active enemy id
- enemy hearts for the active enemy
- last action
- last support id and support type
- trace events
- outcome

The first implementation supports one active enemy in heart combat. Multiple enemies can still exist in the graph, but the combat state resolves one active enemy at a time until a later design adds group hearts or per-enemy hearts.

Enemy level and player level should be read from character node properties.

Skill nodes need enough structured properties for engine validation:

- kind or action scope
- tier
- MP cost
- effect template
- support bonus or effect strength
- tags

Item nodes need enough structured properties for support validation:

- support action scope
- effect template
- support bonus or effect strength
- consumed on use
- matching tags, if any

## Narration And UI Contract

The LLM receives resolved combat facts, not raw authority.

The engine may expose:

- current player hearts
- current enemy hearts
- action name
- support name, if any
- success or failure
- outcome
- HP/MP state words

The LLM must not invent:

- damage numbers
- HP loss
- MP cost
- victory or defeat
- learned skills

The client should show heart state plainly. HP and MP remain visible as long-term resources.

## Existing Rule Changes

This design intentionally replaces these older rules from `docs/04-gameplay.md`:

- Direct per-exchange HP damage is replaced by temporary heart loss.
- The fourth-exchange forced ending is removed.
- Skill `power` no longer means direct HP damage.
- Stats no longer feed combat DC.

These older rules remain valid:

- Engine decides state changes.
- LLM narrates resolved results.
- New combat starts through confirmation.
- Quest completion and rewards remain engine-owned.
- Defeat mode is not automatically death.

## Migration Requirements

The implementation should migrate by rule, not by preserving old combat semantics.

Active old-format `GraphCombatState` should be cleared when the new runtime loads it. Clearing an old active combat is acceptable because combat state is temporary scene state, while HP, MP, quests, inventory, and location remain graph-owned durable state.

Existing skill nodes that use `power` as direct HP damage should be converted into support templates during seed or scenario migration:

| Old skill shape | New template |
|---|---|
| attack skill with `mp_cost` and `power` | `dc_down` with MP cost derived from existing `mp_cost` |
| unusually high `power` attack skill | `extra_heart_damage` if it should feel like a burst skill |
| non-attack skill | hold for a later non-combat skill pass unless it maps safely to defend, flee, or social support |

Existing item nodes without support metadata remain normal inventory items until explicitly given support properties. The migration must not infer combat effects from item names.

## Testing Requirements

Focused tests should cover:

- combat starts with player and enemy hearts at 3
- attack success reduces enemy hearts
- attack failure reduces player hearts
- defend success restores player hearts up to 3
- defend failure reduces player hearts
- flee success ends combat without HP loss
- flee failure reduces player hearts
- social pressure success reduces enemy hearts
- social pressure failure reduces player hearts
- player defeat reduces real HP by enemy remaining hearts
- player victory does not reduce real HP by default
- DC uses level difference and one support only
- DC clamps to minimum 6 and maximum 18
- stats do not change combat DC
- skill support spends MP and applies only to matching actions
- `extra_heart_damage` applies only after a successful attack roll
- `prevent_heart_loss` applies only after a failed roll that would reduce player hearts
- item support consumes consumables and does not stack with skills
- level-up offers a new skill only below three known skills
- level-up offers upgrades only below skill tier 3
- level-up eligibility is created when `xp_pool >= current_level` at a safe point
- confirming level-up consumes `current_level` XP and increases level by 1
- LLM skill proposals are mapped to allowed templates or rejected

## Open Follow-Ups For Implementation Planning

The implementation plan should decide:

- whether skill tier lives on the skill node or `knows_skill` edge
- how roll randomness is injected for deterministic tests
- how much of the existing level-up UI can be reused
- how initial profile selects the starting skill
