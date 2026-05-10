# trpg-server

Engine for a Korean-language TRPG. FastAPI + Pydantic v2 + an OpenAI-compatible LLM. One game lives in graph Postgres tables keyed on `game_id` (`game_progress / graph_nodes / graph_edges / log_entries / history_entries / dialogue_entries`); scenario seeds live in a Supabase Storage bucket.

Design notes start at `../docs/README.md`; the per-turn flow is in `../docs/02-runtime.md`; the interface and ownership map is in `../docs/05-interfaces.md`. The server agent guide is [AGENTS.md](./AGENTS.md).

## Stack

- Python 3.12+, Pydantic v2, FastAPI, uvicorn, httpx, async/await
- OpenAI-compatible LLM via `LLM_ROUTE_<AGENT> = <provider>/<model>` (local OpenAI-compatible server or Gemini hosted; provider blocks live alongside the routes in `.env.<APP_ENV>`)
- **Supabase Postgres + Storage** for graph saves + scenarios. Dev can set `GRAPH_REPO=local` or `SCENARIO_REPO=local`; tests use LocalFs adapters against `tmp_path`.
- Single process. LocalFs writes use per-game locks; Supabase deploys need DB-level locking if two requests can mutate the same `game_id` concurrently.

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
# Active server agents: graph_intro, classify, graph_narrate.
# Optional LLM_ROUTE_<AGENT>_FALLBACK engages on quota.
LLM_ROUTE_DEFAULT=google/gemma-4-26b-a4b-it
LLM_ROUTE_GRAPH_NARRATE=google/gemma-4-31b-it
LLM_ROUTE_GRAPH_NARRATE_FALLBACK=google/gemma-4-26b-a4b-it

# Provider block(s) — declare each provider referenced by the routes.
LLM_GOOGLE_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai/
LLM_GOOGLE_API_KEYS=<key1>,<key2>
LLM_GOOGLE_THINK_OFF=gemma-3-27b-it
LLM_GOOGLE_THINK_OPT=gemini-3.1-flash-lite-preview
LLM_GOOGLE_THINK_OPT_ON=gemma-4-31b-it,gemma-4-26b-a4b-it
LLM_GOOGLE_NO_SYSTEM=gemma-3-27b-it
```

For a local OpenAI-compatible server, add an `LLM_LOCAL_*` block with the same shape and set `LLM_ROUTE_DEFAULT = local/<model>`, then run the model server alongside.

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
| POST | `/session/graph/init` | Create a graph game |
| GET  | `/session/{game_id}/graph/state` | Load graph game state |
| POST | `/session/{game_id}/graph/input` | Classify free text and execute graph action |
| POST | `/session/{game_id}/graph/turn` | Execute explicit graph action |
| POST | `/session/{game_id}/graph/confirm` | Resolve pending graph confirmation |
| POST | `/session/{game_id}/graph/level_up` | Apply graph level-up |
| POST | `/debug/complete` | One-shot LLM call for debugging |

## Tests

```bash
# from repo root (pyproject pins testpaths=server/tests)
.venv/bin/python -m pytest -q                   # unit
```

`pytest-asyncio` auto-mode. End-to-end LLM verification is via manual play after merge — see `server/scripts/smoke_classify.py` for a one-shot env-routed sanity check.

## Layout

```
server/
  run_api.py                       # entrypoint
  .env.dev                         # required for local dev (.env.release for prod), gitignored
  scripts/                         # one-off tools (classify_stress.py, smoke_classify.py, ...)
  src/                             # code (ownership map in ../docs/05-interfaces.md)
  tests/                           # pytest
../scenarios/<profile>/            # local seed source (world.md, start.json, player_template.json, races/, locations/, characters/, items/, quests/, chapters/, skills/). Authored locally, uploaded to Supabase Storage; the running server reads from the bucket.
```

Runtime state lives in Supabase Postgres:

| Table | PK | Notes |
|---|---|---|
| `game_progress` | `(game_id)` | `progress jsonb` carries player id, locale, active quest, pending confirmation, combat state, and `next_log_id` |
| `graph_nodes` | `(game_id, node_id)` | one row per graph node |
| `graph_edges` | `(game_id, edge_id)` | one row per graph edge |
| `log_entries` | `(game_id, log_id)` | `log_id = entry.id` (app-managed monotonic) |
| `history_entries` | `(game_id, seq)` | `bigserial`, append-only turn summaries |
| `dialogue_entries` | `(game_id, seq)` | `bigserial`, append-only dialogue |

Runtime child tables should FK → `game_progress(game_id) ON DELETE CASCADE`. RLS enabled with no policies — the server uses the service-role key, anon/auth keys see nothing.
