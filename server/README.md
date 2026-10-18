# trpg-server

Story-agnostic engine for a Korean TRPG: FastAPI + Pydantic v2, two required local models (Kev decides, Qwen writes), one atomic JSON snapshot per game. The server agent guide is [AGENTS.md](./AGENTS.md).

## Turn flow

```
text ─► interpret (one Kev call) ─► confirm card if high risk ─► resolve (pure rules) ─► save ─► respond
button ───────────────────────────┘
                                   narration stream (Qwen) ─► Kev check ─► rewrite ≤2 ─► cache in save
```

- `scene.build` extracts only what the player knows; interpretation, narration and the view all read it.
- `rules.candidates` lists legal actions (`move:`, `inspect:`, `talk:`, `take:`, `give:`, `act:`; button-only `solve:`, `use_tag:`, `topic:`; and `improvise`).
- `interpret` asks Kev closed questions (steps 1–3, improvise details, talk details) and assembles steps. Unsure targets come back as a clarify list; unsure actions become improvisation; impossible ones are rejected without using a turn.
- `rules.resolve` runs up to three steps on a copy of the state, stops on a miss, settles full obstacles, danger, wounds, quests, chapter goals and endings, and never mutates the input.
- `narrate` streams Qwen text, hides `@<tag> name` lines, and asks Kev whether the text contradicts the facts or invents new things. A failed check emits `reset` and rewrites.

## Run

From the repository root:

```bash
.venv/bin/python server/run_api.py --local    # 127.0.0.1:8000, local/local, Kev :8081, Qwen :8082
```

Without `--local`, `run_api.py` loads `server/.env.shared` then `server/.env.<APP_ENV>` (default `dev`); process env wins, missing keys fail at startup:

```
HOST=127.0.0.1
PORT=8000
BASIC_AUTH_USER=<id>
BASIC_AUTH_PASS=<pass>
CORS_ORIGINS=http://localhost:8090
SCENARIO_DIR=../scenarios
SAVE_DIR=../saves/engine
KEV_BASE_URL=http://127.0.0.1:8081
KEV_MIN_CONFIDENCE=0.5         # optional; answers below are "unsure"
KEV_TARGET_MASS=0.6            # optional; verb probability needed to ask back instead of improvising
KEV_API_KEY=                   # optional
QWEN_BASE_URL=http://127.0.0.1:8082/v1
QWEN_MODEL=auto                # optional; auto picks the model /v1/models marks loaded
QWEN_SAMPLING={"temperature": 0.7, "top_p": 0.8, "top_k": 20, "presence_penalty": 1.5}   # optional
```

Startup validates every story folder (a broken story stops the server) and checks both models. Qwen always gets `enable_thinking: false` (top level for mlx-vlm, `chat_template_kwargs` for mlx-lm); there is no thinking switch.

## Routes

`/health` is public; everything else needs Basic Auth.

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | `{"ok": true, "mode": "engine"}` |
| GET | `/catalog` | Stories (folders starting with `_` are hidden) and their creation options |
| POST | `/games` | `{story, approaches?, traits?}` → `GameView` |
| GET | `/games/{id}` | Saved `GameView` |
| POST | `/games/{id}/act` | `{revision, request_id}` + one of `{text}`, `{action_id}`, `{confirm, accept}` → `{kind, view, turn, options, reason}`; kind is `turn`, `confirm`, `clarify`, `rejected` or `cancelled` |
| GET | `/games/{id}/turns/{n}/narration` | NDJSON events `delta`, `reset`, `done {text, tags}`, `error {retry}`; only the latest turn is generated, older ones come from the cache |

Errors: 404 missing game, 409 stale revision or story version, 422 bad request, 503 model or save failure. A reused `request_id` with the same body replays the saved result.

## Stories

A story folder holds `scenario.json` (schema in `src/content/schema.py`) and `world.md` (style notes passed to the narrator). Validate before running:

```bash
cd server && ../.venv/bin/python -m src.content validate ../scenarios/<name>
```

The validator checks ids, references, 3–5 senses per place, two or more solutions per obstacle, two or more free paths per topic, six traits, the +2/+1/+1/0 spread, and optimistic reachability of every chapter and ending. `scenarios/_template/` is the minimal example and the fixture every test uses.

## Scripts

From `server/`, with both models running:

- `scripts/bench_kev.py --story harbor --state prison`: Kev latency at 10, 20 and all questions.
- `scripts/eval_interpret.py --story harbor`: accuracy, clarify, wrong-commit and improvise rates over `scenarios/<story>/evals/interpret.jsonl`; writes `qa_test/agency/<run>/interpret.json`.
- `scripts/play.py --story harbor`: terminal play with timings in `qa_test/agency/<run>/transcript.jsonl`.

## Tests

```bash
.venv/bin/python -m pytest -q        # from the repo root; fake Kev/Qwen, template story
```

## Layout

```
server/
  run_api.py           app construction, --local defaults, story loading
  src/
    api.py service.py store.py config.py
    content/           schema, load, validate, CLI
    world/             graph, query, state models
    rules/             dsl, candidates, check, costs, talk, chapter, resolve, recommend
    scene/             build (known facts), render (Kev/Qwen text), view (GameView)
    interpret.py narrate.py
    models/            kev, qwen
    locale/ko.py       engine-owned Korean
  scripts/ tests/
```
