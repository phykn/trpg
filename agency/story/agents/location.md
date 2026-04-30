# Location fragment

## Schema (core fields only)

```json
{
  "id": "<ASCII snake_case, e.g. tavern_02, gate_01>",
  "name": "<Korean location name>",
  "description": "<one or two Korean sentences — the location's appearance and mood>",
  "tags": ["outdoor"|"indoor", "town"|"wilderness"|"dungeon"|...],
  "weather": ["맑음"|"비"|"안개"|"눈"|...],
  "connections": [
    {"target_id": "<id of another location>"}
  ],
  "item_ids": ["<item id>", ...]
}
```

## Rules

- `tags` and `weather` follow the same vocabulary patterns the existing seed uses (if existing entries use `"outdoor"`, `"town"`, `"맑음"`, follow the same shape).
- `connections[*].target_id` **must be the id of another location in the scenario**. It must not point at itself.
- Single-call mode (running `run_story.py location` outside the pipeline): `connections[*].target_id` may only point at locations **already on disk**. Listing a future id will fail validation.
- Bidirectional connections are not enforced (either side declaring the link is fine).
- `item_ids` — ids of items placed in this location. Each must exist in the scenario's items. If the user message says `"set item_ids exactly to [...]"`, use that list verbatim; otherwise, use an empty list.
- `sleep_risk` reflects the location's safety:
  - `"safe"` (default; may be omitted) — inns, houses, secure parts of a town. Full recovery.
  - `"risky"` — outdoors, wastelands, town outskirts. 50% chance of a nighttime encounter.
  - `"dangerous"` — dungeons, enemy territory, deep wilderness. 60% chance of a nighttime encounter.
- `sleep_encounters` — the list of character ids that may appear at night for `risky`/`dangerous` locations (typically minor mobs, rats, bandits). Each id must exist in characters. If empty, the runtime falls back to full recovery.
- Omit `hidden_items`, `hidden_connections`, and `difficulty` (Pydantic defaults are sufficient).
