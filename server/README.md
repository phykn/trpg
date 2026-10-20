# Server

FastAPI + Pydantic v2. It loads every story, runs the turn protocol against two local models, and keeps one atomic JSON save per game. The design is in [docs/](../docs/): [engine.md](../docs/engine.md) maps `src/` to it, and [api.md](../docs/api.md) defines the HTTP boundary.

## Run

From the repository root:

```bash
.venv/bin/python server/run_api.py --local
```

`--local` serves `127.0.0.1:8000` with Basic Auth `local/local`, stories from `scenarios/` and saves in `saves/engine/`. It reads only these from the process environment: `DECISION_MODEL` (default `malkuth`), `LLM_MODEL` (default `gemma4`), `DECISION_BASE_URL` (default `http://127.0.0.1:8081`), `LLM_BASE_URL` (default `http://127.0.0.1:8082/v1`) and `DECISION_API_KEY`.

Without `--local`, `run_api.py` loads `server/.env.shared`, then `server/.env.<APP_ENV>` (default `dev`). Process variables win, and a missing required key stops startup.

```
HOST=127.0.0.1
PORT=8000
BASIC_AUTH_USER=<id>
BASIC_AUTH_PASS=<pass>
CORS_ORIGINS=http://localhost:8090
SCENARIO_DIR=../scenarios
SAVE_DIR=../saves/engine
DECISION_MODEL=malkuth                 # must be running on the decision server
DECISION_BASE_URL=http://127.0.0.1:8081
DECISION_MIN_CONFIDENCE=0.5            # optional; the model's default otherwise
DECISION_API_KEY=                      # optional
LLM_MODEL=gemma4                       # qwen, gemma4 or minicpm; must be loaded on the LLM server
LLM_BASE_URL=http://127.0.0.1:8082/v1
LLM_SAMPLING={"temperature": 0.7}      # optional; the model's non-thinking sampling otherwise
```

Startup stops if any story fails validation, if the decision server runs a different model, or if the LLM server has not loaded the configured one. The server never starts, stops or switches models. Model names and sampling live in `src/models/decision.py` and `src/models/llm.py`. Every LLM request sets `enable_thinking: false` (top level for mlx-vlm, in `chat_template_kwargs` for mlx-lm).

Once it is up, `GET /health` answers without auth ([api.md](../docs/api.md) 1).

## Commands

Run from the repository root unless the line starts with `cd server`.

```bash
cd server && ../.venv/bin/python -m src.story ../scenarios/<folder>        # validate a story (docs/story.md 4)
cd server && ../.venv/bin/python -m src.story.evals ../scenarios/<folder> --out ../qa_test/runs/<run> [--decision malkuth --llm gemma4]   # interpretation evals; needs the models, named by flag
cd server && ../.venv/bin/python -m src.fun ../saves/engine                 # fun metrics (docs/fun.md 4)
.venv/bin/python -m pytest -q                                              # fake models, the skeleton story
.venv/bin/python -m ruff check server/
```

## Layout

```
server/
  run_api.py   app construction, --local defaults, model checks
  src/         the engine; module map in docs/engine.md
  tests/
```
