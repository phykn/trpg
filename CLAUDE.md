# CLAUDE.md

A story-agnostic Korean web TRPG engine. The player types a Korean sentence (or presses a recommended button); rules decide the outcome; local models only interpret and narrate.

## Current state

The engine is being rebuilt from theory.

- **Design (source of truth)**: [docs/theory/](docs/theory/) (ontology, rule, engine, fun) and [docs/implement/](docs/implement/) (implementation design, starting with the story format in `story.md`).
- **Story**: [scenarios/skeleton/story.yaml](scenarios/skeleton/story.yaml) is the only story, written in the new format. The current server does not read it.
- **Old engine** (`server/src/`, `server/tests/`, `client/`): kept as a reference for the rebuild. Its story fixtures were removed, so the server tests fail and the server does not start until the new engine lands. Reuse its outer layers (model clients, locking/receipts/persistence in `service.py`, API routes and NDJSON narration, the staged Kev questioning in `interpret.py`, the Kev check and rewrites in `narrate.py`, `locale/ko.py`, the client). Rewrite the content, world, rules and scene layers from the theory. Removed files remain in git history (`git show 679e486a:<path>`).

## Models

- **Kev** (`:8081`, decision model) maps the sentence to closed options: legal candidate actions or `improvise`. It never invents anything.
- **Qwen** (`:8082`) narrates only what changed. Kev checks the text, with up to 2 rewrites. Qwen is always non-thinking (`enable_thinking: false` on every request).

Both models are required and run outside this repo. Never start or stop them (no `kevctl`/`llmctl`); assume they are up. Do not add a mode without models or replace narration with authored text.

## Rules

- The engine knows no story. Story content lives only in `scenarios/<id>/`; no story id, name or sentence appears in engine code. Every story is validated at startup, and a broken one stops the server.
- Rules are pure functions. Dice derive from the seed and turn, and a step never mutates its input.
- The client adopts server responses as state and never duplicates game rules.
- Keep the public `/games/*` routes, snapshot `schema_version`, request receipts and `trpg.game_id` compatible unless a migration is requested.
- Player-facing Korean uses `당신`, polite `합니다체`, and `기술` for skill. Server-composed strings render verbatim in the client. Client strings go in `client/locale/ko.ts`, server common text in `server/src/locale/ko.py`. Comments and validation errors are English.
- Client UI: a fixed viewport-height mobile frame with no scrolling and no illustrations (the same narrow frame on desktop), using NativeWind classes and the tokens in `client/design/`. Commands stay locked while narration streams. A missing response freezes commands until the identical command is retried. Never clear the saved pointer on a failed restore. Dialogs close with Escape, trap focus and return it to the opener.
- Preserve personal env files (`server/.env.*`, `client/.env.*`).

## Commands (Unix; use the root `.venv`, never `server/.venv`)

```bash
.venv/bin/python server/run_api.py --local          # API on 127.0.0.1:8000, Basic Auth local/local
cd client && npm run web                             # web UI on localhost:8090 (8081 is Kev)

.venv/bin/python -m pytest -q
.venv/bin/python -m ruff check server/

cd client && npm test -- --runInBand                 # single: npx jest path/to/file.test.ts
cd client && npx tsc --noEmit && npm run lint
cd client && npm run build:web                       # after routing/config changes
cd client && npm run web -- --clear                  # after token/Tailwind/Babel/Metro changes
```

## Verification

Run focused tests first, then the checks for each boundary you touched. Validate any story you edit. For browser changes, operate the real UI at 320×568, 412×915 and desktop width, covering the affected flows. Record numbered turns and screenshots in ignored `qa_test/agency/<run>/` and cite turn numbers. Passing automated tests does not show the game is fun.
