# Quest fragment

## Schema (core fields only)

```json
{
  "id": "q_<short identifier>",
  "title": "<Korean, short noun phrase>",
  "summary": "<one sentence — who is asking for what>",
  "giver_id": "<id from characters/>",
  "difficulty": "매우 쉬움" | "쉬움" | "보통" | "어려움" | "매우 어려움" | "전설" | "신화",
  "triggers": [
    {"id":"<short key>", "name":"<one Korean line>", "type":"character_death"|"location_enter"|"item_use", "target_id":"<id of the matching kind>"}
  ],
  "conditions": ["<free-form constraint, optional>"],
  "rewards": {"gold": <int>, "exp": <int>},
  "status": "locked" | "active",
  "required": true | false,
  "prerequisite_ids": ["<id of another quest>", ...]
}
```

## Rules

- `giver_id` — **must exist in the scenario's characters**. The quest-giver character.
- `triggers[*].target_id` points into a different pool depending on `type`:
  - `character_death` → an id in characters (typically a hostile)
  - `location_enter` → an id in locations
  - `item_use` → an id in items
- `prerequisite_ids` — ids of other quests. Once they all reach `completed`, this quest unlocks (`locked → active`). Inside one chapter, every quest other than the start quest (which has empty prereqs) must connect through prereqs so the unlock flow feels natural.
- `status` is `"active"` when `prerequisite_ids` is empty, otherwise `"locked"` — follow the status directive in the hint exactly.
- `triggers` is usually 1~3 entries. All must be satisfied to flip the quest to completed.
- `fail_triggers` follows the same shape (failure conditions). Typically omitted.
- Do not duplicate the intent of an existing quest.
- Do not write runtime fields like `triggers_met` or `fail_triggers_met`.

## Rewards

Balance against `difficulty`:

| difficulty | exp | gold |
|---|---|---|
| 매우 쉬움 | 25 | 10 |
| 쉬움 | 50 | 25 |
| 보통 | 100 | 50 |
| 어려움 | 200 | 100 |
| 매우 어려움 | 400 | 200 |
| 전설 | 800 | 500 |
| 신화 | 1500 | 1000 |

The level-up cost for the player is `100 × current_level` (linear; level 0→1 = 100). A main quest naturally jumps the player by 1~2 levels; side quests are about half that.
