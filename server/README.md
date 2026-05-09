# trpg-server

Engine for a Korean-language TRPG. FastAPI + Pydantic v2 + an OpenAI-compatible LLM. One game lives in five Postgres tables keyed on `game_id` (`games / entities / log_entries / history_entries / dialogue_entries`); scenario seeds live in a Supabase Storage bucket.

Design notes start at `../docs/01-overview.md`; the per-turn flow is in `../docs/02-runtime.md`; the module map is in `../docs/05-codemap.md`. The Claude Code guide is [CLAUDE.md](./CLAUDE.md).

## Stack

- Python 3.12+, Pydantic v2, FastAPI, uvicorn, httpx, async/await
- OpenAI-compatible LLM via `LLM_ROUTE_<AGENT> = <provider>/<model>` (llama.cpp local or Gemini hosted; provider blocks live alongside the routes in `.env.<APP_ENV>`)
- **Supabase Postgres + Storage** for saves + scenarios. Both `APP_ENV=dev` and `APP_ENV=release` go through the Supabase adapters; tests bypass the factory and use `LocalFsSaveRepo` / `LocalFsScenarioRepo` against `tmp_path`.
- Single process. Per-turn flush order is entity upserts + jsonl appends → `games.meta` last, so a crash mid-flush is recoverable on reload via `next_log_id` self-heal.

## Setup

The venv, `pyproject.toml`, and `requirements.txt` live at the repo root. From the root, once:

```bash
python3.12 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt   # runtime + pytest/ruff; use requirements.txt for prod-only
```

Set up Supabase: apply the schema (table list under "Layout" below) via the dashboard SQL editor — schema isn't tracked in the repo — create a Storage bucket for scenarios, and upload a profile tree:

```bash
APP_ENV=release .venv/bin/python -m agency.story.tool upload scenarios/<profile>
```

Write `server/.env.dev` (required for local dev — `APP_ENV=release` switches to `.env.release` for prod; no fallbacks, missing keys raise `KeyError` at startup):

```
HOST=0.0.0.0
PORT=8001
BASIC_AUTH_USER=<id>
BASIC_AUTH_PASS=<pass>
CORS_ORIGINS=http://localhost:8081       # comma-separated exact origins (scheme + host)

# Supabase — service-role key bypasses RLS. Server-only secret.
SUPABASE_URL=https://<project>.supabase.co
SUPABASE_SERVICE_KEY=<service-role key>
SUPABASE_SCENARIO_BUCKET=scenarios

# LLM routing — DEFAULT required; LLM_ROUTE_<AGENT> overrides per agent
# (matched agents: classify, narrate_body, narrate_extract, combat_narrate,
# summon, recommend). Optional LLM_ROUTE_<AGENT>_FALLBACK engages on quota.
LLM_ROUTE_DEFAULT=google/gemma-4-26b-a4b-it
LLM_ROUTE_NARRATE_BODY=google/gemma-4-31b-it
LLM_ROUTE_NARRATE_BODY_FALLBACK=google/gemma-4-26b-a4b-it

# Provider block(s) — declare each provider referenced by the routes.
LLM_GOOGLE_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai/
LLM_GOOGLE_API_KEYS=<key1>,<key2>
LLM_GOOGLE_THINK_OFF=gemma-3-27b-it
LLM_GOOGLE_THINK_OPT=gemini-3.1-flash-lite-preview
LLM_GOOGLE_THINK_OPT_ON=gemma-4-31b-it,gemma-4-26b-a4b-it
LLM_GOOGLE_NO_SYSTEM=gemma-3-27b-it
```

For local llama.cpp, add an `LLM_LLAMA_CPP_*` block with the same shape and set `LLM_ROUTE_DEFAULT = llama_cpp/<model>`, then run the LLM server alongside (e.g. `llama-server -m <model.gguf> -c 8192 --port 8000`).

## Run

```bash
# from server/ (cwd must be server/ so dotenv and relative paths resolve)
../.venv/bin/python run_api.py
```

dotenv loads `server/.env.<APP_ENV>` (default `dev`) automatically and uvicorn binds to `HOST:PORT`.

### Routes (Basic Auth required)

| Method | Path | Purpose |
|---|---|---|
| GET  | `/health` | Health check (no auth) |
| GET  | `/profiles` | Scenario + race card list |
| POST | `/session/init` | New game (profile + player) |
| GET  | `/session/{id}/state` | Read FrontState |
| POST | `/session/{id}/turn` | One turn (SSE) |
| POST | `/session/{id}/roll` | Roll the pending_check (SSE) |
| POST | `/session/{id}/intro` | GM intro (SSE, fired once after init) |
| POST | `/debug/complete` | One-shot LLM call for debugging |

SSE event types: `judge / pending_check / narrative_delta / suggestions / log_entry / state / combat_start / combat_turn / combat_end / done / error`. See `../docs/02-runtime.md` §2.4 for shapes.

## Tests

```bash
# from repo root (pyproject pins testpaths=server/tests)
.venv/bin/python -m pytest -q                   # unit
```

`pytest-asyncio` auto-mode. End-to-end LLM verification is via manual play after merge — see `server/scripts/smoke_judge.py` for a one-shot Gemini-routed sanity check.

## Layout

```
server/
  run_api.py                       # entrypoint
  .env.dev                         # required for local dev (.env.release for prod), gitignored
  scripts/                         # one-off tools (judge_stress.py, smoke_judge.py, ...)
  src/                             # code (layer breakdown in docs/05-codemap.md)
  tests/                           # pytest
../scenarios/<profile>/            # local seed source (world.md, start.json, player_template.json, races/, locations/, characters/, items/, quests/, chapters/, skills/). Authored locally, uploaded to Supabase Storage; the running server reads from the bucket.
```

Runtime state lives in Supabase Postgres:

| Table | PK | Notes |
|---|---|---|
| `games` | `(game_id)` | `meta jsonb` carries session pointers (turn_count, pending_check, combat_state, active_*_id, next_log_id, ...) |
| `entities` | `(game_id, kind, id)` | one row per entity; `kind ∈ {characters, items, locations, races, skills, quests, chapters, campaigns}` |
| `log_entries` | `(game_id, log_id)` | `log_id = entry.id` (app-managed monotonic) |
| `history_entries` | `(game_id, seq)` | `bigserial`, append-only turn summaries |
| `dialogue_entries` | `(game_id, seq)` | `bigserial`, append-only dialogue |

All four child tables FK → `games(game_id) ON DELETE CASCADE`. RLS enabled with no policies — the server uses the service-role key, anon/auth keys see nothing.
