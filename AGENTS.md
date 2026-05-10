# AGENTS.md

This file provides guidance to Codex (Codex.ai/code) when working with code in this repository.

Repo-root guide. After moving into the directory you want to work in, also read its `AGENTS.md`.

## Layout

Korean-language TRPG. The LLM handles narrative and difficulty judgment; the engine handles state, rules, and time. Three pieces in one bundle:

- `server/` — FastAPI + Pydantic v2 + OpenAI-compatible LLM. Game engine, Supabase-backed persistence. See [server/AGENTS.md](./server/AGENTS.md).
- `client/` — Expo (RN 0.81 / React 19) single-screen app. Uses graph REST responses from the server. [client/AGENTS.md](./client/AGENTS.md).
- `agency/` — LLM-staffed in-process QA + Story harness driving the server with `LocalFsGraphRepo`. See `agency/README.md`.
- `scenarios/<name>/` — gitignored. Local seed source authored on dev fs and uploaded to a Supabase Storage bucket via `agency.story.tool upload` (run with APP_ENV=release); the running server reads from Storage, not this dir. Tree: `profile.json`, `world.md`, `start.json`, `player_template.json`, `races/`, `characters/`, `locations/`, `items/`, `quests/`, `chapters/`, `skills/`.
- `docs/` — target design contract (`01-contract` → `05-interfaces`). Design rationale lives here, not in code.
- Runtime graph saves live in Supabase Postgres graph tables; scenarios live in Supabase Storage.

The venv, pyproject, and requirements are a single set at the repo root. **Never create per-package venvs (`server/.venv`, `agency/.venv`, etc.) — always use the root `.venv/`.**

## Commands

```bash
# from repo root
.venv/bin/python -m pytest -q                     # unit. pyproject pins testpaths=server/tests
.venv/bin/python server/scripts/smoke_classify.py # one-shot env-routed classify sanity check
.venv/bin/python -m pytest server/tests/flow/test_turn.py::test_X -q   # single test
.venv/bin/ruff check server/                      # lint
bash server/scripts/check_relational_ssot.sh      # graph-SSOT guard (CI-equivalent)

# API server (cwd must be server/ so dotenv reads server/.env.<APP_ENV>; default APP_ENV=dev → .env.dev)
cd server && ../.venv/bin/python run_api.py

# client (separate from the venv, just npm — see client/AGENTS.md for full surface)
cd client && npm start            # Expo Go via QR
cd client && npm run web          # web on localhost:8081
cd client && npm run deploy       # export with .env.release → wrangler deploy
```

Env files mirror on both sides: `server/.env.{dev,release}` and `client/.env.{dev,release}`. Backend deploys to Render on push to `main` (`APP_ENV=release`); frontend deploys to Cloudflare Workers via `npm run deploy`.

## Cross-cutting conventions

Apply repo-wide. When a sub-AGENTS.md repeats a rule, the sub version is just more specific — not in conflict.

- **Korean only — with one client-side exception.** Every piece of text that reaches the user (LLM prompts, logs, NPC lines, error messages, agent prompts, scenario data, anything composed from server data) is in Korean. No localization layer. In-game prose and engine-side log lines use **2인칭 존댓말 합니다체** — `당신` for the player, `~합니다 / ~ㅂ니다 / ~입니다` endings. The user-facing skill term is **기술** (`스킬` survives only as a synonym in the classify prompt). Code text — server source, tests, validation error messages, structural prompts — stays English. **Exception: visual-system meta-labels** in the client UI may be short uppercase English when they function as part of the GeistMono typographic atom — narrowly, **form section labels** in character creation (`NAME` / `GENDER` / `WORLD` / `RACE`). These are pure category markers, not localized prose, and act as visual atoms in the design system. **Action buttons stay Korean** (`시작` / `굴리기` / `멈추기` / `빠르게` / `정확하게`). **Stat keys stay Korean** (`체력` / `마나` / `경험` / `소생`); some terms (notably 소생) don't translate intuitively for players. **Inline log markers are visual-only** — GM narration, player input, and dice rolls are distinguished by typographic form (font size, accent border, mono box) rather than text labels. Game content (narration, NPC lines, scenario text) stays Korean.
- **Comments minimal, English-only.** Default to no comments — add one only when the *why* is non-obvious (hidden constraint, subtle invariant, bug workaround); single short line. Korean is allowed inside an English comment only when quoting an in-game string the comment is reasoning about; never as the prose. No multi-paragraph docstrings, no multi-line `# ...` blocks. `# type:` / `# noqa` / `# pragma:` directives and shebangs aren't comments — leave them.
- **env is fail-fast.** No `??` defaults, no silent defaults. Missing keys throw at startup. Applies to both `server/.env` and `client/.env`.
- **Display data is built on the server and shipped over.** Korean dates, durations, composed strings, conditional labels, confirmations, and log entries are built in the server graph runtime or `server/src/wire/graph_to_front.py`. Client types only carry the fields the UI renders.
- **Save-directory isolation.** The running server writes graph state to Supabase unless `GRAPH_REPO=local` is set for dev. Local QA harnesses write into `qa_test/<agent>/saves/` via `LocalFsGraphRepo`; never repoint QA at the production Supabase graph tables.

## Stack

- Python 3.12+, Pydantic v2, FastAPI, async/await throughout, uvicorn, httpx.
- **Supabase Postgres + Storage** is the runtime store. Graph saves use `game_progress`, `graph_nodes`, `graph_edges`, `log_entries`, `history_entries`, and `dialogue_entries`; scenarios use a Storage bucket mirroring the local `scenarios/<profile>/...` tree 1:1. The running server goes through `SupabaseGraphRepo` + `SupabaseStorageScenarioRepo` unless dev env sets `GRAPH_REPO=local` or `SCENARIO_REPO=local`.
- LLM is OpenAI-compatible. `LLM_ROUTE_<AGENT> = <provider>/<model>` per agent; active server agents are `classify`, `graph_intro`, and `graph_narrate`. Unmatched agents fall back to `default`. Provider blocks (llama.cpp local, Gemini hosted) layer on top of `.env.<APP_ENV>`.
- Expo SDK 54 / RN 0.81 / React 19, NativeWind v4, expo-router with typedRoutes, `expo/fetch` for server calls. Web export deploys to Cloudflare Workers via `npm run deploy`.

The persistence seam is `GraphRepo` / `ScenarioRepo` in `server/src/db/repo.py`. `asyncio.Lock` serialization in the LocalFs graph adapter is single-process only; multi-isolate Supabase deploys need DB-level locking if two requests can mutate the same `game_id` concurrently.
