# CLAUDE.md

A story-agnostic Korean web TRPG engine. The player types a Korean sentence (or presses a recommended button); rules decide the outcome; local models only interpret and narrate.

## Current state

The engine is rebuilt from the theory in [plan.md](plan.md) (stages 1–8 done).

- **Design (source of truth)**: [docs/](docs/) — `ontology.md` (world, invariants, operations, save format), `story.md` (story format and validation), `rule.md` (candidates, rolls, time, people), `engine.md` (interpretation, cards, narration, turn protocol), `api.md`, `ui.md`, `fun.md` (metrics).
- **Story**: [scenarios/skeleton/](scenarios/skeleton/) (`story.yaml` with id `lighthouse`, and `evals.yaml` for interpretation) is the only story.
- **Server** (`server/src/`): `onto/` (world, log, saves), `rules/` (pure rules), `story/` (loading, validation, evals), `interpret.py`, `narrate.py`, `cards.py`, `view.py`, `service.py`, `api.py`, `fun.py` (offline metrics).
- **Client** (`client/`): `logic/useGame.ts` (state machine), `logic/reveal.ts`, `components/game/`, `screens/`.
- Real-UI QA runs and interpretation evals live in ignored `qa_test/agency/` (`ui-1/turns.md` lists the open findings).

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
cd server && ../.venv/bin/python -m src.story.evals ../scenarios/skeleton --out ../qa_test/agency/<run>   # needs the models
cd server && ../.venv/bin/python -m src.fun ../saves/engine                                             # fun.md metrics
.venv/bin/python -m ruff check server/

cd client && npm test -- --runInBand                 # single: npx jest path/to/file.test.ts
cd client && npx tsc --noEmit && npm run lint
cd client && npm run build:web                       # after routing/config changes
cd client && npm run web -- --clear                  # after token/Tailwind/Babel/Metro changes
```

## Verification

Run focused tests first, then the checks for each boundary you touched. Validate any story you edit. For browser changes, operate the real UI at 320×568, 412×915 and desktop width, covering the affected flows. Record numbered turns and screenshots in ignored `qa_test/agency/<run>/` and cite turn numbers. Passing automated tests does not show the game is fun.
