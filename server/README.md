# Server

FastAPI + Pydantic v2. The design is in [docs/engine/](../docs/engine/): [02-api.md](../docs/engine/02-api.md) defines the HTTP boundary. Every route but `GET /health` needs Basic Auth. Startup checks both models ([01-ai.md](../docs/engine/01-ai.md)) and warms them, which can take a minute; a typed question still answers 503 and no narration is written.

## Run

From the repository root:

```bash
.venv/bin/python server/run_api.py --local
```

`--local` serves `127.0.0.1:8000` with Basic Auth `local/local`, stories from `scenarios/` and saves in `saves/game/`. It reads only these from the process environment: `DECISION_MODEL` (default `kanana`), `LLM_MODEL` (default `gemma4`), `DECISION_BASE_URL` (default `http://127.0.0.1:8081`) and `LLM_BASE_URL` (default `http://127.0.0.1:8082/v1`).

Without `--local`, `run_api.py` loads `server/.env.shared`, then `server/.env.<APP_ENV>` (default `dev`). Process variables win, and a missing key stops startup.

```
HOST=127.0.0.1
PORT=8000
BASIC_AUTH_USER=<id>
BASIC_AUTH_PASS=<pass>
CORS_ORIGINS=http://localhost:8090
SCENARIO_DIR=../scenarios
SAVE_DIR=../saves/game
DECISION_MODEL=kanana
DECISION_BASE_URL=http://127.0.0.1:8081
LLM_MODEL=gemma4
LLM_BASE_URL=http://127.0.0.1:8082/v1
```

The server never starts, stops or switches models.

## Commands

From the repository root unless the line starts with `cd server`:

```bash
.venv/bin/python -m pytest -q
.venv/bin/python -m ruff check server/
cd server && ../.venv/bin/python -m src.story ../scenarios/<folder>   # check a story (docs/engine/03-check.md)
```

## Layout

```
server/
  run_api.py   app construction, --local defaults
  src/         config.py, story/ (reading, references, compiling, checks), rules/ (game state and changes), save.py, service.py, view.py, api.py, locale/ko.py, models/
  tests/
```
