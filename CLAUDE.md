# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

Repo-root guide. After moving into the directory you want to work in, also read its `CLAUDE.md`.

## Layout

Korean-language TRPG. The LLM handles narrative and difficulty judgment; the engine handles state, rules, and time. Three pieces in one bundle:

- `server/` — FastAPI + Pydantic v2 + OpenAI-compatible LLM. Game engine, Supabase-backed persistence. See [server/CLAUDE.md](./server/CLAUDE.md).
- `client/` — Expo (RN 0.81 / React 19) single-screen app. Streams from the server over SSE. [client/CLAUDE.md](./client/CLAUDE.md).
- `agency/` — gitignored. LLM-staffed in-process QA + Story harness driving the server with `LocalFsSaveRepo`. See `agency/README.md`.
- `scenarios/<name>/` — gitignored. Local seed source authored on dev fs and uploaded to a Supabase Storage bucket via `agency.story.tool upload` (run with APP_ENV=release); the running server reads from Storage, not this dir. Tree: `profile.json`, `world.md`, `start.json`, `player_template.json`, `races/`, `characters/`, `locations/`, `items/`, `quests/`, `chapters/`, `skills/`.
- `docs/` — gitignored design notes (`01-overview` → `05-codemap`). Design rationale lives here, not in code.
- Saves live in Supabase Postgres (5 tables keyed on `game_id`), not on disk.

The venv, pyproject, and requirements are a single set at the repo root. **Never create per-package venvs (`server/.venv`, `agency/.venv`, etc.) — always use the root `.venv/`.**

## Commands

```bash
# from repo root
.venv/bin/python -m pytest -q                     # unit. pyproject pins testpaths=server/tests
.venv/bin/python server/scripts/smoke_judge.py    # one-shot Gemini-routed classify sanity check
.venv/bin/python -m pytest server/tests/flow/test_turn.py::test_X -q   # single test
.venv/bin/ruff check server/                      # lint
bash server/scripts/check_relational_ssot.sh      # graph-SSOT guard (CI-equivalent)

# API server (cwd must be server/ so dotenv reads server/.env.<APP_ENV>; default APP_ENV=dev → .env.dev)
cd server && ../.venv/bin/python run_api.py

# client (separate from the venv, just npm — see client/CLAUDE.md for full surface)
cd client && npm start            # Expo Go via QR
cd client && npm run web          # web on localhost:8081
cd client && npm run deploy       # export with .env.release → wrangler deploy
```

Env files mirror on both sides: `server/.env.{dev,release}` and `client/.env.{dev,release}`. Backend deploys to Render on push to `main` (`APP_ENV=release`); frontend deploys to Cloudflare Workers via `npm run deploy`.

## Cross-cutting conventions

Apply repo-wide. When a sub-CLAUDE.md repeats a rule, the sub version is just more specific — not in conflict.

- **Korean only — with one client-side exception.** Every piece of text that reaches the user (LLM prompts, logs, NPC lines, error messages, agent prompts, scenario data, anything composed from server data) is in Korean. No localization layer. In-game prose and engine-side log lines use **2인칭 존댓말 합니다체** — `당신` for the player, `~합니다 / ~ㅂ니다 / ~입니다` endings. The user-facing skill term is **기술** (`스킬` survives only as a synonym in the classify prompt). Code text — server source, tests, validation error messages, structural prompts — stays English. **Exception: visual-system meta-labels** in the client UI may be short uppercase English when they function as part of the GeistMono typographic atom — narrowly, **form section labels** in character creation (`NAME` / `GENDER` / `WORLD` / `RACE`). These are pure category markers, not localized prose, and act as visual atoms in the design system. **Action buttons stay Korean** (`시작` / `굴리기` / `멈추기` / `빠르게` / `정확하게`). **Stat keys stay Korean** (`체력` / `마나` / `경험` / `소생`); some terms (notably 소생) don't translate intuitively for players. **Inline log markers are visual-only** — GM narration, player input, and dice rolls are distinguished by typographic form (font size, accent border, mono box) rather than text labels. Game content (narration, NPC lines, scenario text) stays Korean.
- **Comments minimal, English-only.** Default to no comments — add one only when the *why* is non-obvious (hidden constraint, subtle invariant, bug workaround); single short line. Korean is allowed inside an English comment only when quoting an in-game string the comment is reasoning about; never as the prose. No multi-paragraph docstrings, no multi-line `# ...` blocks. `# type:` / `# noqa` / `# pragma:` directives and shebangs aren't comments — leave them.
- **env is fail-fast.** No `??` defaults, no silent defaults. Missing keys throw at startup. Applies to both `server/.env` and `client/.env`.
- **Display data is built on the server and shipped over.** Korean dates, durations, composed strings, conditional labels for the client payload are built in `server/src/wire/to_front.py`; engine-side log lines that thread through the SSE stream are built in `server/src/flow/{format,error_phrases,actions,combat_phase,turn,roll,rest}.py`. Both render as-is on the client. Client types only carry the fields the UI renders.
- **Save-directory isolation.** The running server writes saves to Supabase (both `APP_ENV=dev` and `release`). Local QA harnesses (e.g. agency) write into `qa_test/<agent>/saves/` via the LocalFs adapter — keep them separate, never repoint at the production Supabase project.

## Stack

- Python 3.12+, Pydantic v2, FastAPI, async/await throughout, uvicorn, httpx.
- **Supabase Postgres + Storage** is the runtime store. Saves → 5 tables keyed on `game_id` (`games / entities / log_entries / history_entries / dialogue_entries`); scenarios → Storage bucket mirroring the local `scenarios/<profile>/...` tree 1:1. The running server (both `APP_ENV=dev` and `release`) goes through `SupabaseSaveRepo` + `SupabaseStorageScenarioRepo`; tests bypass the factory and use `LocalFsSaveRepo` / `LocalFsScenarioRepo` against `tmp_path`.
- LLM is OpenAI-compatible. `LLM_ROUTE_<AGENT> = <provider>/<model>` per agent (`classify`, `narrate`, `combat_narrate`, `summon`, `recommend`); unmatched agents fall back to `default`. Provider blocks (llama.cpp local, Gemini hosted) layer on top of `.env.<APP_ENV>`.
- Expo SDK 54 / RN 0.81 / React 19, NativeWind v4, expo-router with typedRoutes, `expo/fetch` for SSE streaming (standard `fetch` doesn't support SSE body streaming on RN). Web export deploys to Cloudflare Workers via `npm run deploy`.

The persistence seam — `SaveRepo` / `ScenarioRepo` Protocols in `server/src/persistence/repo.py` — exists so the storage layer can be swapped without touching `flow/`, `context/`, or `engines/`. `asyncio.Lock` save serialization is single-process only; multi-isolate deploys would need DB-level locks (`SELECT ... FOR UPDATE`).
