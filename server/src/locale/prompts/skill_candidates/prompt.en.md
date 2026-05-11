Create 1-2 level-up skill candidates from the player's recent actions and stats.

Return exactly one JSON object.

```json
{"skills":[{"name":"", "description":"", "action":"attack", "effect_template":"dc_down", "support_bonus":2, "mp_cost":2, "tags":[""]}]}
```

Rules:
- `action` must be one of `attack`, `defend`, `flee`, `social`.
- `effect_template` must be one of `dc_down`, `extra_heart_damage`, `prevent_heart_loss`, `escape_boost`.
- `support_bonus` and `mp_cost` are integers from 1 to 3.
- Do not create damage numbers, healing numbers, cooldowns, or target counts.
- Skills support a combat roll; they do not replace the action.
- Avoid names or roles that duplicate known skills.
