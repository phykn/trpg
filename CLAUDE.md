# CLAUDE.md

Repo-root guide. After moving into the directory you want to work in, also read its `CLAUDE.md`.

## Layout

Korean-language TRPG. Three pieces in one bundle:

- `server/` — FastAPI + Pydantic v2 + OpenAI-compatible LLM. Game engine, Supabase-backed persistence. See [server/CLAUDE.md](./server/CLAUDE.md).
- `client/` — Expo (RN 0.81 / React 19) single-screen app. Streams from the server over SSE. [client/CLAUDE.md](./client/CLAUDE.md).
- `scenarios/<name>/` — gitignored. Local seed source authored on dev fs and uploaded to a Supabase Storage bucket via `server/scripts/upload_scenarios.py`; the running server reads from Storage, not this dir. Tree: `profile.json`, `world.md`, `start.json`, `player_template.json`, `races/`, `characters/`, `locations/`, `items/`, `quests/`, `chapters/`, `skills/`.
- Saves live in Supabase Postgres (5 tables keyed on `game_id`), not on disk.

The venv, pyproject, and requirements are a single set at the repo root. **Never create per-package venvs (`server/.venv`, `agency/.venv`, etc.) — always use the root `.venv/`.**

## Commands

```bash
# from repo root
.venv/bin/python -m pytest -q                     # unit (live skipped). pyproject pins testpaths=server/tests
RUN_LIVE=1 .venv/bin/python -m pytest -q          # only when the LLM is up (BASE_URL must be reachable)

# single test
.venv/bin/python -m pytest server/tests/test_apply.py::test_name -q

# API server (cwd must be server/ so dotenv reads server/.env.<APP_ENV>; default APP_ENV=dev → .env.dev)
cd server && ../.venv/bin/python run_api.py

# client (separate from the venv, just npm)
cd client && npx expo start
```

## Cross-cutting conventions

Apply repo-wide. When a sub-CLAUDE.md repeats the same rule, the sub version is just more specific — not in conflict.

- **Korean only.** Every piece of text that reaches the user (LLM prompts, logs, NPC lines, error messages, agent prompts) is in Korean. No localization layer. In-game prose and engine-side log lines use **2인칭 존댓말 합니다체** — `당신` for the player, `~합니다 / ~ㅂ니다 / ~입니다` endings — and avoid the `박-` root entirely. The user-facing skill term is **기술** (`스킬` survives only as a synonym in the dc_judge prompt). Code text — server source, tests, validation error messages, structural prompts — stays English.
- **Comments minimal, English-only.** Default to no comments — add one only when the *why* is non-obvious (hidden constraint, subtle invariant, bug workaround); single short line. Korean is allowed inside an English comment only when quoting an in-game string the comment is reasoning about (`# "잠시 정적이 흐릅니다" fallback`); never as the prose. No multi-paragraph docstrings, no multi-line `# ...` blocks — collapse or delete. `# type:` / `# noqa` / `# pragma:` directives and shebangs aren't comments — leave them. Docstrings follow the same rule.
- **env is fail-fast.** No `??` defaults, no silent defaults. Missing keys throw at startup. Applies to both `server/.env` and `client/.env`.
- **Display data is built on the server and shipped over.** Korean dates, durations, composed strings, conditional labels for the client payload are built in `server/src/mapping/to_front.py`; engine-side log lines that thread through the SSE stream are built in `server/src/flow/{format,error_phrases,actions,combat_phase,turn,roll,rest}.py`. Both render as-is on the client. Client types only carry the fields the UI renders.
- **Save-directory isolation.** The running server writes saves to Supabase (both `APP_ENV=dev` and `release`). Local QA harnesses (e.g. agency) write into `qa_test/<agent>/saves/` via the LocalFs adapter — keep them separate, never repoint at the production Supabase project.

## Stack

- Python 3.12+, Pydantic v2, FastAPI, async/await throughout, uvicorn.
- **Supabase Postgres + Storage** is the runtime store. Saves → 5 tables keyed on `game_id` (`games / entities / log_entries / history_entries / dialogue_entries`); scenarios → Storage bucket mirroring the local `scenarios/<profile>/...` tree 1:1. The running server (both `APP_ENV=dev` and `release`) goes through `SupabaseSaveRepo` + `SupabaseStorageScenarioRepo`; tests bypass the factory and use `LocalFsSaveRepo` / `LocalFsScenarioRepo` against `tmp_path`.
- LLM is OpenAI-compatible. `LLM_ROUTE_<AGENT> = <provider>/<model>` per agent (`dc_judge`, `narrate`, `combat_narrate`, `encounter_summon`, `skill_recommend`); unmatched agents fall back to `default`. Provider blocks (llama.cpp local, Gemini hosted) layer on top of `.env.<APP_ENV>`.
- Expo SDK 54 / RN 0.81 / React 19, NativeWind v4, expo-router with typedRoutes, `expo/fetch` for SSE streaming (standard `fetch` doesn't support SSE body streaming on RN). Web export deploys to Cloudflare Workers via `npm run deploy`.

The persistence seam — `SaveRepo` / `ScenarioRepo` Protocols in `server/src/persistence/repo.py` — exists so the storage layer can be swapped without touching `flow/`, `context/`, or `engines/`. `asyncio.Lock` save serialization is single-process only; multi-isolate deploys would need DB-level locks (`SELECT ... FOR UPDATE`).
