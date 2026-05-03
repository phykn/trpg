# Race fragment

## Schema

```json
{
  "id": "<ASCII snake_case>",
  "name": "<Korean race name>",
  "description": "<Korean, one or two sentences>",
  "racial_skill_ids": ["<skill id>", ...]
}
```

## Rules

- `name` — a single Korean word or short noun phrase, e.g. "인간" / "엘프" / "드워프".
- `description` — one or two Korean sentences covering the race's body, temperament, and role (e.g., "땅 밑 산에서 자란 단단한 종족. 망치질과 광맥에 능하다.").
- `racial_skill_ids` — 0 to 2 ids. The innate skills shared by every character of this race.
  - For ordinary races (e.g., humans), leave it empty (`[]`).
  - For races with a clear concept (dragons, elves, dwarves, etc.), specify 1 or 2 ids — they must match the ids of Skills authored in the separate `skill` step.
- Do not duplicate the meaning or role of an existing race (e.g., if "long-lived sage race" already exists, do not author another with the same concept).
