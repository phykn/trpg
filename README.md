# 말과 주사위

*(Words and Dice)*

A web TRPG engine where the player tries anything by typing a Korean sentence, rules decide the outcome, and local models write the scene. Stories are data files in `scenarios/`; the code runs any story.

- The **decision model** (`:8081`, `malkuth` or `kev`) reads the sentence as closed options: an action available right now, or improvise. It never invents anything.
- The **rules** check whether 2d6 plus modifiers reaches the target (7, 8 or 9 by risk), then compute and save progress boxes, risk clocks, tags and costs.
- The **narration model** (`:8082`, `gemma4`, `qwen` or `minicpm`, always non-thinking) writes only what changed as a scene, and the decision model checks it against the facts (up to 2 rewrites).

The design is in [docs/](docs/): world ([ontology.md](docs/ontology.md)), story format ([story.md](docs/story.md)), rules ([rule.md](docs/rule.md)), engine ([engine.md](docs/engine.md)), [api.md](docs/api.md), screens ([ui.md](docs/ui.md)), fun ([fun.md](docs/fun.md)).

## Setup

Both models are required and run outside this repository ([local-models](https://github.com/phykn/local-models)). The engine never starts or switches models. At startup the server checks that both servers run the configured models, and refuses to start otherwise.

Install once from the repository root (developed and verified with Python 3.13 and Node):

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
(cd client && npm i)
```

## Run locally

```bash
.venv/bin/python server/run_api.py --local
```

```bash
cd client && npm run web
```

Run each command from the repository root in its own terminal, then open **http://localhost:8090** in a browser. `--local` needs no personal env file and uses `127.0.0.1:8000`, auth `local/local`, decision model `malkuth` (`:8081`) and narration model `gemma4` (`:8082`). Pick other models with `DECISION_MODEL` and `LLM_MODEL` ([server/README.md](server/README.md)). If a server runs a different model than configured, the startup error names the model currently loaded. The web port is 8090 because the decision model uses 8081.

## Play

1. On the title screen, pick a story, then set a name, stats and traits.
2. Type actions as sentences in the input line. Tapping a name in a scene line starts a sentence: a destination fills in the whole "…로 간다" ("go to …"), people, things and obstacles fill in the opening, and a blocked destination starts with the obstacle blocking it. One sentence can chain up to three steps.
3. An action that rolls opens a roll card. It shows the target, modifiers and what you can lean on; press and release the dice to roll.
4. Filling an obstacle's boxes opens the way; when a risk clock fills, things get worse. The story's conditions decide the ending.

Every turn is saved before narration, without waiting for it. If narration breaks off, only the rewrite is requested again.

## Write a new story

Write `scenarios/<folder>/story.yaml` in the format of [docs/story.md](docs/story.md). The only example is [scenarios/skeleton/story.yaml](scenarios/skeleton/story.yaml). No code changes are needed. The server validates every story at startup and will not start if any fails; you can also validate ahead of time:

```bash
cd server && ../.venv/bin/python -m src.story ../scenarios/<folder>
```

## Where to change things

| Goal | Location |
|---|---|
| Story, people, obstacles, endings | `scenarios/<folder>/story.yaml` ([docs/story.md](docs/story.md)) |
| Checks, costs, tags, conversation rules | [server/src/rules/](server/src/rules/) |
| Sentence interpretation | [server/src/interpret.py](server/src/interpret.py) |
| Narration and checking | [server/src/narrate.py](server/src/narrate.py) |
| API, saves, the order of a turn | [docs/api.md](docs/api.md), [docs/engine.md](docs/engine.md) section 7 |
| Screens | [client/screens/](client/screens/), [client/components/](client/components/) ([docs/ui.md](docs/ui.md)) |

## Verification

```bash
.venv/bin/python -m pytest -q
.venv/bin/python -m ruff check server/
cd client && npm test -- --runInBand && npx tsc --noEmit && npm run lint
```

Passing automated tests is not evidence that the game is fun. For checking the real UI, follow section 6.2 of [docs/ui.md](docs/ui.md).

## Saves

A single file, `saves/engine/g_<id>.json`, atomically stores the world, turn log, narration cache, random seed and request receipts. The browser keeps only `trpg.game_id` and the chat history. File saves are meant for a single server process.
