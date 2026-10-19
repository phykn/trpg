# trpg-server

Story-agnostic engine for a Korean TRPG: FastAPI + Pydantic v2, two required local models (one decides, one writes), one atomic JSON snapshot per game. The design is in [docs/](../docs/); this file covers running it.

## Turn flow

```
text ─► interpret (decision model picks closed options) ─┐
button / card answer ────────────────────────────────────┴─► roll or confirm card if needed ─► resolve (pure rules) ─► save ─► respond
                                     narration stream (LLM) ─► claim check (decision model) ─► rewrite ≤ 2 ─► cache in the save
```

- `interpret.py` maps a sentence to legal candidate actions or `improvise`, up to three steps (engine.md 3). An unclear approach takes the player's strongest stat; only real ambiguity becomes a clarify card.
- `rules/` are pure: candidates, the roll (2d6 + modifiers against a target of 7/8/9 by risk), costs, triggers. A step never mutates its input and dice come from the seed and turn.
- `cards.py` builds clarify, roll and confirm cards; `view.py` builds the `GameView` and step records; `service.py` runs the turn protocol (lock, revision, request receipts).
- `narrate.py` writes only what changed, checks claims against the facts, and rewrites up to twice; the narration and chapter recaps stream as NDJSON.

## Run

From the repository root:

```bash
.venv/bin/python server/run_api.py --local    # 127.0.0.1:8000, local/local, decision :8081, LLM :8082
```

`--local` reads only `DECISION_MODEL` (default `malkuth`), `LLM_MODEL` (default `gemma4`), their `*_BASE_URL` and `DECISION_API_KEY` from the process environment. Without `--local`, `run_api.py` loads `server/.env.shared` then `server/.env.<APP_ENV>` (default `dev`); process env wins, missing keys fail at startup:

```
HOST=127.0.0.1
PORT=8000
BASIC_AUTH_USER=<id>
BASIC_AUTH_PASS=<pass>
CORS_ORIGINS=http://localhost:8090
SCENARIO_DIR=../scenarios
SAVE_DIR=../saves/engine
DECISION_MODEL=malkuth         # kev or malkuth: the model the decision server runs
DECISION_BASE_URL=http://127.0.0.1:8081
DECISION_MIN_CONFIDENCE=0.5    # optional; the model's own default otherwise
DECISION_API_KEY=              # optional
LLM_MODEL=gemma4               # qwen, gemma4 or minicpm: must be loaded on the LLM server
LLM_BASE_URL=http://127.0.0.1:8082/v1
LLM_SAMPLING={"temperature": 0.7}   # optional; the model card's non-thinking sampling otherwise
```

Startup validates every story folder (a broken story stops the server) and checks that the decision server runs the configured model and the LLM server has the configured model loaded; the engine never loads or switches models. The model names and their sampling live in `src/models/decision.py` and `src/models/llm.py`. The LLM always gets `enable_thinking: false` (top level for mlx-vlm, `chat_template_kwargs` for mlx-lm).

## Routes

`/health` is public; everything else needs Basic Auth. Bodies and responses are in [docs/api.md](../docs/api.md).

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | `{"ok": true, "mode": "engine"}` |
| GET | `/stories` | Stories and their creation options |
| POST | `/games` | `{request_id, story, creation}` → `{game_id, view}` |
| GET | `/games/{id}` | The saved `view` |
| POST | `/games/{id}/commands` | `{request_id, revision}` + one of `{text}`, `{action}`, `{card, pick}`, `{card, cancel: true}` → `{kind, turn, steps, reason, view}` |
| GET | `/games/{id}/turns/{n}/narration` | NDJSON narration of turn `n` |
| GET | `/games/{id}/chapters/{k}/recap` | NDJSON recap of chapter `k` |

Errors: 404 missing game, 409 stale revision (`{view}`) or incompatible save (`{reason: "incompatible"}`), 422 bad request. A reused `request_id` with the same body replays the saved result.

## Stories

A story folder holds `story.yaml` (format in [docs/story.md](../docs/story.md)) and optionally `evals.yaml` for interpretation evals. Validate before running:

```bash
cd server && ../.venv/bin/python -m src.story ../scenarios/<name>
cd server && ../.venv/bin/python -m src.story.evals ../scenarios/<name> --out ../qa_test/agency/<run>   # needs the models
cd server && ../.venv/bin/python -m src.fun ../saves/engine                                           # fun.md metrics
```

## Tests

```bash
.venv/bin/python -m pytest -q          # from the repo root; fake models, the skeleton story
.venv/bin/python -m ruff check server/
```

## Layout

```
server/
  run_api.py           app construction, --local defaults, model checks
  src/
    onto/              atoms.py cond.py change.py log.py save.py universe.py
                       view.py (what one observer sees: Obs, Seen; not the GameView)
    rules/             acts.py candidates.py roll.py costs.py schemas.py triggers.py resolve.py recommend.py
    story/             load.py (YAML), compile.py (story → Universe), validate.py (V1–V6), evals.py, __main__.py (CLI)
    lang/              context (ρ), claims (κ), polite (합니다체)
    models/            decision.py, llm.py
    locale/ko.py       engine-owned Korean
    interpret.py cards.py narrate.py service.py api.py config.py fun.py
    view.py            the GameView and step records sent to the client (docs/api.md)
  tests/
```
