# Chapter fragment

## Schema

```json
{
  "id": "ch<number>",
  "title": "<Korean, short noun phrase>",
  "summary": "<Korean, one or two sentences — the chapter's overall arc and goal>",
  "quest_ids": ["<quest id>", ...],
  "prerequisite_ids": ["<other chapter id>", ...],
  "status": "locked" | "active",
  "required": true | false
}
```

## Rules

- `quest_ids` — ids that **must exist in the scenario's quests**. Typically 2~5. Each quest belongs to exactly one chapter.
- `prerequisite_ids` — ids of other chapters. Once all of them reach `completed`, this chapter unlocks (`locked → active`). The opening chapter (with empty prerequisite_ids) is `active` at game start; the rest start `locked`.
- `status` is `"active"` when `prerequisite_ids` is empty, otherwise `"locked"` — follow the status directive in the hint exactly.
- Do not include the `progress` field (the runtime fills it).
- `required: true` marks a chapter as part of the main arc; `false` marks it as a side chapter.
