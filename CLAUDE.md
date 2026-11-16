# CLAUDE.md

A story-agnostic Korean mystery TRPG. The player asks people questions in Korean and presents clues from the notebook; rules decide what opens and what is learned; local models only interpret and narrate.

## Layout

- **Design (source of truth, written in plain Korean)**: [docs/game/](docs/game/) (concept, loop, notebook, talk, blocks, time, screen, story format, authoring), [docs/data/](docs/data/) (ontology, story data, game state, changes, invariants and saves) and [docs/engine/](docs/engine/) (models, API, story checks). When they disagree, game wins over data, and data over engine.
- **Build plan**: [docs/groove/PLAN.md](docs/groove/PLAN.md) (git-ignored). A session continuing the build uses groove to do the first unchecked task.
- **Stories**: `scenarios/<folder>/story.yaml` ([docs/data/02-story.md](docs/data/02-story.md)). [scenarios/skeleton/](scenarios/skeleton/) is the smallest story using every device and lists last as `Dev:`; `arena/` is the prologue (the real-world tutorial that ends with the truck) and `dawn/` is chapter 1. Only these three are tracked, and the start screen lists stories by folder name.
- **Server** (`server/`): `run_api.py` (reads the arguments; before serving it checks every story, then checks and warms both models), `src/config.py` (every setting, read by pydantic-settings: the `--local` defaults, and the environment over the dotenv files), `src/story/` (`load.py` reads, checks references, compiles and marks a story; `check.py` runs the checks of docs/engine/03-check.md by playing the rules as a virtual player, for `python -m src.story` and for startup), `src/rules/` (pure rules: `state.py` holds the game state, what it shows, the writing step, the changes and the invariants; `act.py` turns one action into changes, with the time step and the dice; `guide.py` decides when the DM speaks, docs/game/07-screen.md 2). `src/save.py` (one atomic JSON file per game, reopened by replaying its recorded changes into the state after each turn), `src/service.py` (creates games, turns a command body into an action, runs one command per receipt), `src/view.py` (the `GameView`, its act ids and each turn's feed), `src/names.py` (what the screen calls a place, person, thing or line), `src/api.py` (the app, `/health`, the routes of docs/engine/02-api.md, Basic Auth and errors), `src/locale/ko.py` (server Korean), `src/models/` (`decision.py` for Kanana and `llm.py` for gemma4 through the openai SDK: the startup check and the calls), `src/interpret.py` (turns a typed sentence into a reading with Kanana, docs/engine/01-ai.md 1), `src/slots.py` (a turn's text slots, which the feed numbers and narration fills, and each slot's job: what is said and given), `src/narrate.py` (from a job alone: the prompts, Kanana's checks and up to two rewrites; the service streams them once per turn and saves them in the turn record), `src/story/evals.py` (the interpretation evals over `scenarios/<folder>/evals.yaml`, with `--held` over the held-out `evals-held.yaml`, and with `--text` the text evals).
- **Client** (`client/`): `app/index.tsx` (picks the screen from the game state), `screens/` (title, start, play, ending), `components/game/` (the frame, the play screen's top bar, chat log, people row and input, and the notebook, a drag sheet (@gorhom/bottom-sheet) that opens halfway and whose lines unfold in place, and the moves, conclusion and pick sheets), `components/ui/` (shared icon (lucide), button, sheet, dialog focus (focus-trap), the drag sheet and the resend row), `design/` (`tokens.js`: the raw colors, sizes and type; `ui.ts`: the shared looks built from them with class-variance-authority and tailwind-merge: text, surfaces, controls, tones and the one dimmed state), `logic/useGame.ts` (the screen's state machine: adopts each `view`, locks while sending or streaming, resends the identical command, gives each chat line its turn and slot), `logic/notebook.ts` (the notebook's group order and finding a line), `services/api.ts` and `types.ts` (docs/engine/02-api.md), `services/storage.ts` (the saved game pointer).
- **Mac app** (`app/`): `build.sh` builds `TRPG.app`, which starts and stops `npm run serve` and shows the phone address, passing the loaded models as `DECISION_MODEL` and `LLM_MODEL`. It reads how far `serve.cjs` got (ready, address, deploying, why it stopped) from `logs/serve.json`, never from its output. Its model bar reads the server's model tables and polls the same check routes.
- QA: [qa/README.md](qa/README.md) maps each kind of change to the checks to run, `qa/play/play.py` plays a game from the shell through the API, and [qa/findings.md](qa/findings.md) holds the open findings. Recordings, playtests and real-UI runs go to ignored `qa_test/runs/<run>/`.

## Models

Both models are required and run outside this repo. Never start or stop them (no `kevctl`/`llmctl`); assume they are up. Do not add a mode without models or replace narration with authored text. [docs/engine/01-ai.md](docs/engine/01-ai.md) defines how each is asked.

- **Decision model**: Kanana (`kakaocorp/kanana-2-v-decide-3b-2611`, `:8081`, `DECISION_MODEL=kanana`, checked through `GET /v1/info`). It answers closed questions the engine builds: which topic or place a sentence means, and whether a narration keeps to the facts. It never invents anything.
- **LLM**: gemma4 (`mlx-community/gemma-4-26B-A4B-it-qat-4bit`, `:8082`, `LLM_MODEL=gemma4`) narrates only what changed, and the decision model checks the text, with up to 2 rewrites. It is always non-thinking (`enable_thinking: false` on every request).

## Rules

- The engine knows no story. Story content lives only in `scenarios/<id>/`; no story id, name or sentence appears in engine code. Every story is validated at startup, and a broken one stops the server.
- Rules are pure functions. Dice derive from the seed and turn, and a step never mutates its input.
- The client adopts server responses as state and never duplicates game rules.
- Keep the public `/games/*` routes, the save `format`, request receipts and `trpg.game_id` compatible unless a migration is requested.
- Player-facing Korean uses `당신`, polite `합니다체`, and the words defined in [docs/game/03-notebook.md](docs/game/03-notebook.md). Server-composed strings render verbatim in the client. Client strings go in `client/locale/ko.ts`, server common text in `server/src/locale/ko.py`. Comments and code errors are English; story errors and check reports name the story's Korean keys and names ([docs/engine/03-check.md](docs/engine/03-check.md) 6).
- Client UI: a fixed viewport-height mobile frame with no illustrations and no scrolling outside the chat log (the same narrow frame on desktop), using NativeWind classes. A look used in more than one place is a variant in `client/design/ui.ts`, never spelled out again in a component; extra classes go through its `cn`, so tailwind-merge settles any that fight. Reach for a maintained library (focus-trap, lucide icons, the openai SDK, pydantic-settings) before writing the same thing by hand. Commands stay locked while narration streams. A missing response freezes commands until the identical command is retried. Never clear the saved pointer on a failed restore. Dialogs close with Escape, trap focus and return it to the opener.
- Preserve personal env files (`server/.env.*`, `client/.env.*`).

## Commands (Unix; use the root `.venv`, never `server/.venv`)

```bash
.venv/bin/python server/run_api.py --local          # API on 127.0.0.1:8000, Basic Auth local/local
cd client && npm run web                             # web UI on localhost:8090 (8081 is the decision model)
app/build.sh && open TRPG.app                        # Mac app: one-button npm run serve

.venv/bin/python -m pytest -q
.venv/bin/python -m ruff check server/ qa/
cd server && ../.venv/bin/python -m src.story ../scenarios/<folder>   # check a story
cd server && ../.venv/bin/python -m src.story.evals ../scenarios/<folder> --out ../qa_test/runs/<run>   # interpretation evals (Kanana); --held for the held-out set, never fitted to
cd server && ../.venv/bin/python -m src.story.evals ../scenarios/<folder> --text --out ../qa_test/runs/<run>   # text evals (gemma4 and Kanana)

cd client && npm test -- --runInBand                 # single: npx jest path/to/file.test.ts
cd client && npx tsc --noEmit && npm run lint
cd client && npm run build:web                       # after routing/config changes
cd client && npm run web -- --clear                  # after token/Tailwind/Babel/Metro changes
```

## Verification

Run focused tests first, then the checks for each boundary you touched. Validate any story you edit. For browser changes, operate the real UI at 320×568, 412×915 and desktop width, covering the affected flows. Record numbered turns and screenshots in ignored `qa_test/runs/<run>/` and cite turn numbers. Passing automated tests does not show the game is fun; for that, someone who did not write the story plays a game.
