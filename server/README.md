# trpg-server

Engine for a Korean-language TRPG. FastAPI + Pydantic v2 + an OpenAI-compatible LLM. One game lives in one directory (`saves/games/<id>/`) as a scatter of JSON + JSONL.

Design notes start at `../docs/01-overview.md`; the per-turn flow is in `../docs/02-runtime.md`; the module map is in `../docs/05-codemap.md`. The Claude Code guide is [CLAUDE.md](./CLAUDE.md).

## Stack

- Python 3.12+, Pydantic v2, FastAPI, uvicorn, httpx, async/await
- OpenAI-compatible LLM server (e.g. llama.cpp) pointed at by `BASE_URL`
- Game state is a pile of files (`SAVES_DIR/games/<game_id>/`). No DB.
- Single process (writes serialized via `asyncio.Lock`)

## Setup

The venv, `pyproject.toml`, and `requirements.txt` live at the repo root. From the root, once:

```bash
python3.12 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

Write `server/.env` (required, no fallbacks — missing keys raise `KeyError` at startup):

```
HOST=0.0.0.0
PORT=8001
BASE_URL=http://localhost:8000/v1        # llama.cpp or another OpenAI-compatible server
BASIC_AUTH_USER=<id>
BASIC_AUTH_PASS=<pass>
SAVES_DIR=../saves                       # peer of the repo root
PROFILE_DIR=../scenarios                 # peer of the repo root
```

The LLM server runs separately. Example: `llama-server -m <model.gguf> -c 8192 --port 8000`.

## Run

```bash
# from server/ (cwd must be server/ so dotenv and relative paths resolve)
../.venv/bin/python run_api.py
```

dotenv loads `server/.env` automatically and uvicorn binds to `HOST:PORT`.

### Routes (Basic Auth required)

| Method | Path | Purpose |
|---|---|---|
| GET  | `/health` | Health check (no auth) |
| GET  | `/profiles` | Scenario + race card list |
| GET  | `/session/current` | FrontState for the most recent game_id (404 if none) |
| POST | `/session/init` | New game (profile + player) |
| GET  | `/session/{id}/state` | Read FrontState |
| POST | `/session/{id}/turn` | One turn (SSE) |
| POST | `/session/{id}/roll` | Roll the pending_check (SSE) |
| POST | `/session/{id}/intro` | GM intro (SSE, fired once after init) |
| POST | `/debug/complete` | One-shot LLM call for debugging |

SSE event types: `judge / pending_check / narrative_delta / log_entry / state / combat_start / combat_turn / combat_end / done / error`. See `../docs/02-runtime.md` §2.4 for shapes.

## Tests

```bash
# from repo root (pyproject pins testpaths=server/tests)
.venv/bin/python -m pytest -q                   # unit (live skipped)
RUN_LIVE=1 .venv/bin/python -m pytest -q        # requires a live LLM
```

`pytest-asyncio` auto-mode. Tests marked `live` only run when `RUN_LIVE=1` (and `BASE_URL` is reachable).

## Layout

```
server/
  run_api.py                       # entrypoint
  .env                             # required, gitignored
  src/                             # code (layer breakdown in docs/05-codemap.md)
  tests/                           # pytest
  scripts/                         # one-off tools (judge_stress, etc.)
../scenarios/<profile>/            # scenario seed (world.md, start.json, races/, locations/, characters/, items/, quests/, chapters/, player_template.json). Peer of the repo root
../saves/                          # runtime store (gitignored)
  .current                           # one-line pointer to the most recent game_id
  games/<game_id>/
    meta.json                        # singleton fields (player_id, turn_count, pending_check, ...)
    characters/<id>.json             # one file per entity
    items/<id>.json
    locations/<id>.json
    races/<id>.json                  # ...
    log.jsonl                        # append-only log
    history.jsonl                    # append-only turn summaries
    dialogue.jsonl                   # append-only dialogue
```

Atomic writes (`.tmp` → `os.replace`) plus `asyncio.Lock` keep concurrent writes from clobbering each other.
