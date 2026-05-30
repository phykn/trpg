# trpg-server

Engine for a Korean-language TRPG. FastAPI + Pydantic v2 + an OpenAI-compatible LLM. One game lives in graph Postgres tables keyed on `game_id` (`game_progress / graph_nodes / graph_edges / log_entries / history_entries / memory_entries / exchange_entries / world_patch_entries`); scenario seeds live in a Supabase Storage bucket.

The server agent guide is [AGENTS.md](./AGENTS.md).

## Stack

- Python 3.12+, Pydantic v2, FastAPI, uvicorn, httpx, async/await
- OpenAI-compatible LLM via `LLM_ROUTE_<AGENT> = <provider>/<model>` (local OpenAI-compatible server or Gemini hosted; provider blocks live in the loaded server env files)
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
APP_ENV=release .venv/bin/python -m agency.story.tools.storage upload scenarios/<profile>
```

Write `server/.env.shared` for common server defaults and `server/.env.dev` for local dev. `APP_ENV=release` switches the environment-specific file to `.env.release`; no fallbacks, missing keys raise `KeyError` at startup. OS/Render dashboard env values have priority over dotenv files.

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
# Active server agents: classify, graph_narrate, combat_narrate, recommend,
# and story_write when a generated-story contract is active.
# Optional LLM_ROUTE_<AGENT>_FALLBACK engages on quota.
LLM_ROUTE_DEFAULT=google/gemma-4-26b-a4b-it
LLM_ROUTE_GRAPH_NARRATE=google/gemma-4-31b-it
LLM_ROUTE_GRAPH_NARRATE_FALLBACK=google/gemma-4-26b-a4b-it
LLM_CLASSIFY_TEMPERATURE=0.0              # optional; default 0.0
LLM_GRAPH_NARRATE_TEMPERATURE=1.0         # optional; default 1.0
LLM_CLASSIFY_LIMIT_RECENT_SCENE=3         # optional recent context caps
LLM_CLASSIFY_LIMIT_RECENT_EXCHANGES=3
MAX_PREVIOUS_SCENE=3
MAX_RECENT_EXCHANGES=3

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

dotenv loads `server/.env.shared` then `server/.env.<APP_ENV>` (default `dev`) automatically and uvicorn binds to `HOST:PORT`.

### Routes

`/health` and `/version` are public. All other routes require Basic Auth. The
`*/stream` graph action routes return newline-delimited JSON events:
`result`, zero or more `narration_delta`, then `final`; failures stream an
`error` event.

| Method | Path | Purpose |
|---|---|---|
| GET  | `/health` | Health check (no auth) |
| GET  | `/version` | Git SHA / local build marker (no auth) |
| GET  | `/profiles` | Scenario + race card list |
| POST | `/session/graph/init` | Create a graph game |
| POST | `/session/{game_id}/graph/intro` | Append the initial intro log if needed |
| POST | `/session/{game_id}/graph/intro/stream` | Stream initial intro result/delta/final |
| GET  | `/session/{game_id}/graph/state` | Load graph game state |
| POST | `/session/{game_id}/graph/input` | Classify free text and execute graph action |
| POST | `/session/{game_id}/graph/input/stream` | Streaming free-text graph action |
| POST | `/session/{game_id}/graph/turn` | Execute explicit graph action |
| POST | `/session/{game_id}/graph/turn/stream` | Streaming explicit graph action |
| POST | `/session/{game_id}/graph/combat` | Execute combat command |
| POST | `/session/{game_id}/graph/combat/stream` | Streaming combat command |
| POST | `/session/{game_id}/graph/confirm` | Resolve pending graph confirmation |
| POST | `/session/{game_id}/graph/confirm/stream` | Streaming pending confirmation resolution |
| POST | `/session/{game_id}/graph/roll` | Resolve pending graph roll |
| POST | `/session/{game_id}/graph/roll/stream` | Streaming pending roll resolution |
| GET  | `/session/{game_id}/graph/level_up/options` | Build level-up choices |
| POST | `/session/{game_id}/graph/level_up` | Apply graph level-up |
| GET  | `/session/{game_id}/story/patches` | Dev-only generated story patch ledger |
| GET  | `/session/{game_id}/story/timeline` | Dev-only alias for patch timeline review |
| GET  | `/session/{game_id}/story/debt` | Dev-only generated clue/NPC/item/quest debt report |
| GET  | `/session/{game_id}/story/dev/graph` | Dev-only raw graph inspector payload |
| GET  | `/session/{game_id}/story/dev/contract` | Dev-only active generated story contract |
| POST | `/session/{game_id}/story/dev/contract` | Dev-only apply a session-local generated story contract override |
| POST | `/session/{game_id}/story/rollback` | Dev-only rollback of the latest accepted generated patch |
| POST | `/session/{game_id}/story/dev/preview_contract` | Dev-only validate contract JSON without saving |
| POST | `/session/{game_id}/story/dev/preview_patch` | Dev-only validate/preview generated patch without saving |
| POST | `/session/{game_id}/story/dev/replay_prompt` | Dev-only rebuild story writer prompt payload without calling the LLM |

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
  .env.shared                      # shared server defaults, gitignored
  .env.dev                         # required for local dev (.env.release for prod), gitignored
  scripts/                         # seed checks and one-off LLM smoke tools
  src/                             # code
  tests/                           # pytest
../scenarios/<profile>/            # local seed source (world.md, start.json, player.json, races/, locations/, characters/, items/, quests/, chapters/, skills/). Authored locally, uploaded to Supabase Storage; the running server reads from the bucket.
```

Runtime state lives in Supabase Postgres:

| Table | PK | Notes |
|---|---|---|
| `game_progress` | `(game_id)` | `progress jsonb` carries player/profile ids, runtime content, optional story contract override, locale, active subject/quest, intro text, turn count, pending confirmation, pending roll, combat state, and `next_log_id` |
| `graph_nodes` | `(game_id, node_id)` | one row per graph node |
| `graph_edges` | `(game_id, edge_id)` | one row per graph edge |
| `log_entries` | `(game_id, log_id)` | `log_id = entry.id` (app-managed monotonic) |
| `history_entries` | `(game_id, seq)` | `bigserial`, append-only turn summaries |
| `memory_entries` | `(game_id, seq)` | `bigserial`, append-only target-indexed long-term memories. Rows also carry `target_id`, `turn`, `importance`, and `entry jsonb` |
| `exchange_entries` | `(game_id, seq)` | `bigserial`, append-only player input + narrator response exchanges |
| `world_patch_entries` | `(game_id, seq)` | `bigserial`, append-only accepted/rejected LLM story patch ledger |

Runtime child tables should FK → `game_progress(game_id) ON DELETE CASCADE`. RLS enabled with no policies — the server uses the service-role key, anon/auth keys see nothing. Add an index on `memory_entries(game_id, target_id, seq desc)` so NPC-specific recall does not scan the whole save.
