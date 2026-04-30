# Skill fragment

## Schema

```json
{
  "id": "<ASCII snake_case, e.g. fireball, drill_strike>",
  "name": "<Korean, short noun phrase>",
  "description": "<one short Korean sentence>",
  "level": <int — must be ≤ the user character's level>,
  "type": "attack" | "heal" | "buff" | "debuff",
  "target": "self" | "single" | "area",
  "primary_stat": "STR" | "DEX" | "CON" | "INT" | "WIS" | "CHA",
  "special_effect": "<short Korean string; empty is OK>",
  "power": <int — base value for attack/heal; buff/debuff may use 0>,
  "mp_cost": <int>,
  "range": <float, meters — typically 1.5 (melee) to 5.0 (ranged)>,
  "duration": <int — depends on type>
}
```

## Rules

- `id` must never collide with another skill in the same scenario.
- `level` — racial skills are always 1; learned skills must be ≤ the character's level.
- `duration` depends on type:
  - `attack` / `heal` → `0` (no duration; applies immediately)
  - `buff` / `debuff` → `> 0` (number of turns it lasts)
- `primary_stat` mapping guide:
  - Physical attack → STR/DEX (swordplay, melee) or INT (magic — flame, lightning)
  - heal → WIS / INT
  - buff (defense, focus) → WIS / CON
  - debuff (curse, deception) → CHA / INT
- Concept consistency: the skill's name and description tone must not clash with the owner (race or character). A rogue's skill written as a light-magic spell breaks tone.
- Do not duplicate the meaning or name of an existing skill.
- If the user message forces an `id`, use that id exactly.

## Validation

The skill stage is auto-validated by `check.skills(character, skills_pool)` — it checks the type ↔ duration pairing, that the character's level is ≥ skill level, and that every racial/learned skill_id on the character exists in skills_pool.
