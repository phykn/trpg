# Agency

Local tools for testing and authoring the game. QA is a Codex browser skill. Story builds and validates local scenario directories.

```
agency/
  qa/SKILL.md   # Browser QA skill (Codex plays the visible web UI)
  story/SKILL.md # Story-team Codex skill (no CLI — invoked from a session)
  qa/           # Browser QA skill
  story/        # The Story team — authors scenario seeds (race / character / ...)
```

## Browser QA — Codex plays the visible UI

Use `agency/qa/SKILL.md` when the goal is to find product improvements by playing the web client in an already-open browser. This is exploratory QA: Codex uses the real UI, records turn-by-turn observations, and reports issues with repro steps and evidence.

Example:

> "agency/qa/SKILL.md 보고 열린 브라우저에서 QA 해줘"

Output should go under `qa_test/browser/<run-id>/report.md` when a report file is useful.

## Story — scenario seed authoring

Single Codex skill (`agency/story/SKILL.md`) authors a complete scenario directory from one Korean prose `.md`. Codex itself writes the entity files; no external LLM call.

### Layout

```
agency/story/
  SKILL.md            # The skill — Codex reads this and follows the workflow
  tool.py             # Single CLI. Subcommands: decompose-{setup,cast,arc},
                      # check-entity, equip-fill, sweep
  tools/storage.py    # Release Supabase Storage upload/download
  harness/
    _common.py        # ID pattern, trigger map, EntityWriterError
    decompose.py      # Pydantic models + _check_setup/_check_cast/_check_arc
    records.py        # Cross-ref check helpers + SPECS metadata
    scenario.py       # fill_equipment — equipment slot derivation
```

### How to use

In a Codex session, point at the skill:

> "agency/story/SKILL.md 보고 path/to/prose.md 로 scenarios/foo 만들어줘"

Codex reads SKILL.md, drafts `.decomp/{setup,cast,arc}.json`, validates each phase via `tool.py`, then writes entity JSONs in the order race → location → character → skill → item, runs `equip-fill`, writes quests/chapters/meta, and runs `sweep`.

### env

`tool.py` loads `server/.env.shared` and `server/.env.<APP_ENV>` (default `dev`). Local story subcommands need no network. Release publish/download uses `APP_ENV=release .venv/bin/python -m agency.story.tools.storage upload|download ...` and requires `SUPABASE_URL` / `SUPABASE_SERVICE_KEY` / `SUPABASE_SCENARIO_BUCKET`.

### Limits

- Runtime entity injection during a game (adding a new NPC/item to a live save) belongs to the server and isn't designed yet.
