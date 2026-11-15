# CLAUDE.md

A story-agnostic Korean mystery TRPG. The player asks people questions in Korean and presents clues from the notebook; rules decide what opens and what is learned; local models only interpret and narrate.

## Layout

- **Design (source of truth, written in plain Korean)**: [docs/game/](docs/game/) (concept, loop, notebook, talk, blocks, time, screen, story format, authoring, first story), [docs/data/](docs/data/) (ontology, story data, game state, changes, invariants and saves) and [docs/engine/](docs/engine/) (models, API, story checks, implementation order). When they disagree, game wins over data, and data over engine. [docs/old/](docs/old/) documents the removed engine; read it, and its code at commit `834ea7db`, for reference only.
- **Build plan**: [docs/groove/PLAN.md](docs/groove/PLAN.md) (git-ignored). A session continuing the build uses groove to do the first unchecked task.
- **Stories**: `scenarios/<folder>/story.yaml` ([docs/data/02-story.md](docs/data/02-story.md)). Only `skeleton/` and `dawn/` are tracked.
- **Server** (`server/`): `run_api.py` (the app and the `--local` defaults; for now it answers only `GET /health`), `src/config.py` (settings from the environment).
- **Client** (`client/`): `app/` (routes; for now an empty title screen), `components/ui/` (shared icon, button, sheet, motion, dialog, notice), `design/` (tokens), `logic/useViewportHeight.ts`, `services/storage.ts` (the saved game pointer).
- **Mac app** (`app/`): `build.sh` builds `TRPG.app`, which starts and stops `npm run serve` and shows the phone address, passing the loaded models as `DECISION_MODEL` and `LLM_MODEL`. Its model bar still reads the removed `server/src/models/` until plan task T9.
- QA: [qa/README.md](qa/README.md) maps each kind of change to the checks to run, and [qa/findings.md](qa/findings.md) holds the open findings. Recordings, playtests and real-UI runs go to ignored `qa_test/runs/<run>/`.

## Models

Both models are required and run outside this repo. Never start or stop them (no `kevctl`/`llmctl`); assume they are up. Do not add a mode without models or replace narration with authored text. [docs/engine/01-ai.md](docs/engine/01-ai.md) defines how each is asked.

- **Decision model**: Kanana (`kakaocorp/kanana-2-v-decide-3b-2611`, `:8081`, `DECISION_MODEL=kanana`, checked through `GET /v1/info`). It answers closed questions the engine builds: which topic or place a sentence means, and whether a narration keeps to the facts. It never invents anything.
- **LLM**: gemma4 (`mlx-community/gemma-4-26B-A4B-it-qat-4bit`, `:8082`, `LLM_MODEL=gemma4`) narrates only what changed, and the decision model checks the text, with up to 2 rewrites. It is always non-thinking (`enable_thinking: false` on every request).

## Rules

- The engine knows no story. Story content lives only in `scenarios/<id>/`; no story id, name or sentence appears in engine code. Every story is validated at startup, and a broken one stops the server.
- Rules are pure functions. Dice derive from the seed and turn, and a step never mutates its input.
- The client adopts server responses as state and never duplicates game rules.
- Keep the public `/games/*` routes, snapshot `schema_version`, request receipts and `trpg.game_id` compatible unless a migration is requested. The new game keeps these names but does not read the old engine's saves ([docs/data/05-save.md](docs/data/05-save.md)).
- Player-facing Korean uses `당신`, polite `합니다체`, and the words defined in [docs/game/03-notebook.md](docs/game/03-notebook.md). Server-composed strings render verbatim in the client. Client strings go in `client/locale/ko.ts`, server common text in `server/src/locale/ko.py`. Comments and validation errors are English.
- Client UI: a fixed viewport-height mobile frame with no illustrations and no scrolling outside the chat log (the same narrow frame on desktop), using NativeWind classes and the tokens in `client/design/`. Commands stay locked while narration streams. A missing response freezes commands until the identical command is retried. Never clear the saved pointer on a failed restore. Dialogs close with Escape, trap focus and return it to the opener.
- Preserve personal env files (`server/.env.*`, `client/.env.*`).

## Commands (Unix; use the root `.venv`, never `server/.venv`)

```bash
.venv/bin/python server/run_api.py --local          # API on 127.0.0.1:8000, Basic Auth local/local
cd client && npm run web                             # web UI on localhost:8090 (8081 is the decision model)
app/build.sh && open TRPG.app                        # Mac app: one-button npm run serve

.venv/bin/python -m pytest -q
.venv/bin/python -m ruff check server/

cd client && npm test -- --runInBand                 # single: npx jest path/to/file.test.ts
cd client && npx tsc --noEmit && npm run lint
cd client && npm run build:web                       # after routing/config changes
cd client && npm run web -- --clear                  # after token/Tailwind/Babel/Metro changes
```

## Verification

Run focused tests first, then the checks for each boundary you touched. Validate any story you edit. For browser changes, operate the real UI at 320×568, 412×915 and desktop width, covering the affected flows. Record numbered turns and screenshots in ignored `qa_test/runs/<run>/` and cite turn numbers. Passing automated tests does not show the game is fun; for that, someone who did not write the story plays a game.
