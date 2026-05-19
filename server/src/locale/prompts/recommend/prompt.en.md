Create 1-2 level-up skill candidates from the player's recent actions and stats.

Return exactly one JSON object.

```json
{"skills":[{"name":"","description":""}]}
```

Rules:
- Match the order of the input `skills` array.
- Output only the skill name and description.
- Do not output rule fields such as `action`, `bonus`, or `mp_cost`; the server chooses them from the input order.
- Do not create damage numbers, healing numbers, cooldowns, or target counts.
- Skills support a roll/check; they do not replace the action.
- Avoid names or roles that duplicate known skills.

Use only:
- The player's recent actions
- The player's stats
- The player's combat, dialogue, defense, escape, and exploration tendencies
- The skills already learned
- The action types the player currently repeats

Candidate rhythm:
1. Pick an action the player actually repeated.
2. Choose a small support role for that action.
3. Describe when the skill helps; do not promise the result.

Do not add setting lore, classes, species, equipment, magic systems, new resources, new statuses, new damage systems, or new reward systems that are not in the input.

Prefer under-supported play patterns when learned skills are already concentrated in one area.
