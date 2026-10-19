# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

Read [AGENTS.md](AGENTS.md) first, then the deepest applicable guide: [server/AGENTS.md](server/AGENTS.md) or [client/AGENTS.md](client/AGENTS.md). Those files hold the binding rules; this file summarizes them and adds Unix commands. Design intent is in [plan.md](plan.md), the implementation plan (file budgets, types, algorithms) in [code.md](code.md).

## What this is

A story-agnostic Korean web TRPG engine. The player types a Korean sentence (or presses one of 3 recommended buttons); rules decide the outcome; local models only interpret and narrate.

- **Kev** (`:8081`, decision model) maps the sentence to closed options: legal candidate actions or `improvise`. It never invents anything.
- **Rules** (`server/src/rules/`) compute 2d6 checks, progress, danger, tags and costs.
- **Qwen** (`:8082`, always non-thinking: `enable_thinking: false` on every request) narrates only what changed; Kev then checks the text for contradictions/inventions, with up to 2 rewrites.

Both models are required and run outside this repo. Never start or stop them (no `kevctl`/`llmctl`); assume they are up. The server refuses to start if either is missing.

## Commands (Unix; use the root `.venv`, never `server/.venv`)

```bash
.venv/bin/python server/run_api.py --local          # API on 127.0.0.1:8000, Basic Auth local/local
cd client && npm run web                             # web UI on localhost:8090 (8081 is Kev)

.venv/bin/python -m pytest -q                        # all server tests (fake Kev/Qwen, _template story)
.venv/bin/python -m pytest -q server/tests/test_rules.py::test_name   # single test
.venv/bin/python -m ruff check server/
bash server/scripts/check_relational_ssot.sh         # edge traversal only in world/graph.py, world/query.py
cd server && ../.venv/bin/python -m src.content validate ../scenarios/harbor ../scenarios/_template

cd client && npm test -- --runInBand                 # single: npx jest path/to/file.test.ts
cd client && npx tsc --noEmit && npm run lint
cd client && npm run build:web                       # after routing/config changes
cd client && npm run web -- --clear                  # after token/Tailwind/Babel/Metro changes
```

Real-model scripts, run from `server/` with both models up: `scripts/play.py --story harbor` (terminal play), `scripts/eval_interpret.py --story harbor` (interpretation accuracy on `scenarios/<story>/evals/interpret.jsonl`), `scripts/bench_kev.py --story harbor --state prison` (Kev latency vs question count). Outputs go to ignored `qa_test/agency/<run>/`.

## Architecture

Turn flow (`server/src/service.py` orchestrates, under a per-game lock with revisions and request receipts):

```
text ─► interpret (Kev: steps, then details) ─► confirm card if high risk ─► resolve (pure rules) ─► save ─► respond
button ─────────────────────────────────────────┘
then: GET /games/{id}/turns/{n}/narration (NDJSON) ─► Qwen stream ─► Kev check ─► rewrite ≤2 ─► cache in save
```

- **Story content lives only in `scenarios/<name>/`** (`scenario.json` + `world.md`). `src/` must contain no story id, name or sentence; `tests/test_boundaries.py` enforces this. New stories copy `scenarios/_template/` (which is also the test fixture) and require no code changes. Every story is validated at server startup; a broken one stops the server.
- **`src/content/`**: schema (`schema.py`), loading (only `load.py` reads files), validation (ids, references, ≥2 solutions per obstacle, trait spread, reachability of chapters/endings).
- **`src/world/`**: graph of nodes/edges plus saved state models. Relation traversal is confined to `graph.py`/`query.py`.
- **`src/rules/`**: pure functions. Every state change is an op in `rules/dsl.py` emitting a `Change`. `candidates.py` lists legal action ids (`move:`, `inspect:`, `talk:`, `take:`, `give:`, `act:`, button-only `solve:`/`use_tag:`/`topic:`, plus `improvise`). `resolve.py` runs up to 3 steps on a copy and never mutates input; dice derive from `(seed, turn, step)`.
- **`src/scene/`**: `build` extracts only what the player knows; `render` turns it into Kev/Qwen text; `view` builds the client `GameView`.
- **`src/interpret.py` and `src/narrate.py`** are the only model callers (besides the startup ping). Kev latency grows with question count, so interpretation asks steps first and details only when needed. Close same-kind options produce a `clarify` list. Kev (0.8B) is weak on details, so `interpret.assemble` corrects it with plain-word rules (named solution/action labels, `…에게` addressee, named topics, routes to named places, approach and giving verbs in `locale/ko.py`); `narrate` adds rule checks (합니다체 conversion via `ko.polite`, unearned rewards, held items handed over) before Kev's check. Measure interpretation changes with `scripts/eval_interpret.py` (`interpret.jsonl` plus `interpret_holdout*.jsonl` via `--file`; on 2026-10-19 fresh sets scored 65–87% before tuning and 90–100% after). Measure a new held-out set before tuning rules again, and report the untuned number. When Kev's best first step is below 0.5, Qwen picks from the same closed list (`second_opinion`; `--kev-only` in the eval script turns it off). A story's `impossible` phrases and requests to the game (`ko.META_ENDINGS`) are turned back before Kev is asked.
- **Persistence**: one atomic JSON snapshot per game at `saves/engine/g_<id>.json` (graph, turn log, narration cache, RNG seed, receipts). A turn is saved before responding; narration is generated afterwards. Single server process only.
- **Client** (Expo 54 / RN 0.81 / Expo Router / NativeWind, web target): `app/index.tsx` → `screens/GameScreen.tsx` → `logic/useGame.ts` (all server state, command lifecycle, recovery) → `services/api.ts` (the only HTTP/`expo/fetch` boundary). The browser stores only `trpg.game_id`. The client must not duplicate game rules; it adopts server responses as state.

## Invariants to preserve

- Keep the public `/games/*` routes, snapshot `schema_version`, request receipts and `trpg.game_id` compatible unless a migration is requested. A reused `request_id` with the same body replays the saved result.
- Do not add a mode without models or replace narration with authored text.
- Player-facing Korean uses `당신`, polite `합니다체`, and `기술` for skill. Server-composed strings render verbatim in the client. Client strings go in `client/locale/ko.ts`, server common text in `server/src/locale/ko.py`. Comments and validation errors are English.
- Client UI: a fixed viewport-height mobile frame with no scrolling and no illustrations (same narrow frame on desktop). Use NativeWind classes and shared tokens in `client/design/`. Commands stay locked while narration streams. A missing response freezes commands until the identical command is retried. Never clear the saved pointer on a failed restore.
- Preserve user saves (`saves/`) and personal env files (`server/.env.*`).

## Verification expectations

Run focused tests first, then the checks for each boundary you touched, and validate any story you edit. For browser changes, operate the real UI at 412×915 and desktop width (client guide also requires 320×568), covering the affected flows (free text, buttons, streaming, confirm, clarify, growth, ending, restore, error recovery). Record numbered turns and screenshots in `qa_test/agency/<run>/` and cite turn numbers. Passing automated tests does not show the game is fun.
