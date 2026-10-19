# trpg-server

Story-agnostic engine for a Korean TRPG: FastAPI + Pydantic v2, two required local models (Kev decides, Qwen writes), one atomic JSON snapshot per game.

## Turn flow

```
text ─► interpret (Kev: steps, then details if needed) ─► confirm card if high risk ─► resolve (pure rules) ─► save ─► respond
button ───────────────────────────┘
                                   narration stream (Qwen) ─► Kev check ─► rewrite ≤2 ─► cache in save
```

- `scene.build` extracts only what the player knows; interpretation, narration and the view all read it.
- `rules.candidates` lists legal actions (`move:`, `inspect:`, `talk:`, `take:`, `give:`, `act:`; button-only `solve:`, `use_tag:`, `topic:`; and `improvise`).
- `interpret` first turns back, without a turn, sentences with the story's `impossible` phrases and requests to the game that name nothing in the scene. It sends Kev only the player's sentence; when Kev's best first step is below 0.5, Qwen picks from the same closed options (a Qwen failure keeps Kev's answer). The first call asks which actions it holds (steps 1–3); a second call asks details only for improvise or talk steps, because Kev's latency grows with the question count. Two close options of the same kind come back as a clarify list; Kev's best guess is otherwise taken; only a confident "impossible" is rejected, without using a turn.
  Rules then correct Kev where the words are plain (`interpret.assemble`): a sentence that names an open solution's required item or clue, or nearly repeats a solution or authored action label, uses it; words to a named person (`…에게` plus a speech verb) are talk to that person, gift nothing to anyone else and walk nowhere; small talk aimed at an obstacle becomes an attempt on it; a named topic is that topic; a known place with a movement verb walks the open route (up to three moves); a gift needs a giving verb; a single approach verb (`APPROACH_CUES`) sets the approach and attitude verbs and first-person claims set the talk; a trait named by a word is used; taking what an obstacle guards attempts that obstacle; a bare look is a moment without a roll. When Kev's two best concrete readings are nearly tied and no rule settled it, the player is asked back. Only a confident "stretch" raises risk.
- `rules.resolve` runs up to three steps on a copy of the state, stops on a miss, settles full obstacles, danger, wounds, quests, chapter goals and endings, and never mutates the input.
- `narrate` streams Qwen text, hides `@<tag> name` lines, and asks Kev whether the text contradicts the facts or invents new things. A failed check emits `reset` and rewrites. Before the check, rules turn sentence-final plain verbs into 합니다체 (`ko.polite`) and ask for a rewrite on broken letters, the player called `너`, a sentence written twice, a held item handed over, or a reward named before its obstacle is overcome; out of attempts, the draft with the fewest such problems is kept. After a move the previous scene's last lines are not passed on; after a growth pick the new chapter opens with no player action. Lines starting with `- ` (an echoed change list) are dropped, and the scene is rewritten if `당신` handles a story item the turn never mentions or a companion appears when there is none.

## Run

From the repository root:

```bash
.venv/bin/python server/run_api.py --local    # 127.0.0.1:8000, local/local, decision :8081, LLM :8082
```

`--local` reads only `DECISION_MODEL` (default `kev`), `LLM_MODEL` (default `qwen`), their `*_BASE_URL` and `DECISION_API_KEY` from the process environment. Without `--local`, `run_api.py` loads `server/.env.shared` then `server/.env.<APP_ENV>` (default `dev`); process env wins, missing keys fail at startup:

```
HOST=127.0.0.1
PORT=8000
BASIC_AUTH_USER=<id>
BASIC_AUTH_PASS=<pass>
CORS_ORIGINS=http://localhost:8090
SCENARIO_DIR=../scenarios
SAVE_DIR=../saves/engine
DECISION_MODEL=kev             # kev or malkuth: the model the decision server runs
DECISION_BASE_URL=http://127.0.0.1:8081
DECISION_MIN_CONFIDENCE=0.5    # optional; the model's own default otherwise
DECISION_API_KEY=              # optional
LLM_MODEL=qwen                 # qwen, gemma4 or minicpm: must be loaded on the LLM server
LLM_BASE_URL=http://127.0.0.1:8082/v1
LLM_SAMPLING={"temperature": 0.7}   # optional; the model card's non-thinking sampling otherwise
```

Startup validates every story folder (a broken story stops the server) and checks that the decision server runs the configured model and the LLM server has the configured model loaded; the engine never loads or switches models. The model names and their sampling live in `src/models/decision.py` and `src/models/llm.py`. The LLM always gets `enable_thinking: false` (top level for mlx-vlm, `chat_template_kwargs` for mlx-lm); there is no thinking switch.

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
  tests/
```
