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
- Skills support a combat roll; they do not replace the action.
- Avoid names or roles that duplicate known skills.
