# Server

FastAPI + Pydantic v2. The design is in [docs/engine/](../docs/engine/): [02-api.md](../docs/engine/02-api.md) defines the HTTP boundary. For now the app answers only `GET /health`, without auth.

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

From the repository root:

```bash
.venv/bin/python -m pytest -q
.venv/bin/python -m ruff check server/
```

## Layout

```
server/
  run_api.py   app construction, --local defaults
  src/         config.py
  tests/
```
