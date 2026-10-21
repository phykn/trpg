# Words and Dice

A web TRPG engine. The player types any action as a Korean sentence, the rules decide the outcome, and local models write the scene. Stories are data in `scenarios/`; the engine code contains none.

- The **decision model** (`malkuth`, `:8081`) maps the sentence to a closed option: an action possible right now. It never invents anything.
- The **rules** roll 2d6 plus modifiers against a target of 7, 8 or 9 set by risk, then apply progress, risk clocks, tags and costs.
- The **narration model** (`gemma4`, `qwen` or `minicpm`, `:8082`, always non-thinking) writes only what changed. The decision model checks the text against the facts, with up to two rewrites.

## Design docs

| Doc | Defines |
|---|---|
| [ontology.md](docs/ontology.md) | World state, observation, change operations, saves |
| [story.md](docs/story.md) | Story file format and validation |
| [rule.md](docs/rule.md) | Candidate actions, rolls, time, people |
| [engine.md](docs/engine.md) | Interpretation, cards, narration, turn protocol |
| [api.md](docs/api.md) | HTTP routes and response shapes |
| [ui.md](docs/ui.md) | Screens, the roll, client state |
| [fun.md](docs/fun.md) | Fun metrics and hypotheses |

## Setup

Both models are required and run outside this repository ([local-models](https://github.com/phykn/local-models)). Start them first; the server checks them at startup and refuses to start if either runs a different model.

Install once from the repository root (Python 3.13, Node):

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
(cd client && npm i)
```

## Run locally

In two terminals from the repository root:

```bash
.venv/bin/python server/run_api.py --local
```

```bash
cd client && npm run web
```

Open http://localhost:8090. `--local` needs no env file; the API is on `127.0.0.1:8000` with auth `local/local`. The web client reloads on its own; restart the API after changing server code or a story. Other models and settings: [server/README.md](server/README.md). Phone and public access: [client/README.md](client/README.md).

On a Mac, `app/build.sh && open TRPG.app` builds a small app that runs `npm run serve` ([client/README.md](client/README.md#public-serving-workersdev)) with one button and shows the phone address with a QR code. It runs the API with whichever models the model servers have loaded, keeps output in `logs/server.log`, and quitting it stops the server.

## Play

1. On the title screen pick a story, then set a name, stats and traits.
2. Type an action as a sentence. Tapping a name in the scene starts the sentence for you. One sentence can chain up to three actions.
3. An action that rolls opens a roll card with the target and modifiers. Choose what to rely on, then press and release the dice.
4. Filling an obstacle's boxes gets you past it; a full risk clock makes things worse. The story's conditions decide the ending.

Each turn is saved before its narration is written. The browser keeps only the game id and the chat history.

## Write a story

Write `scenarios/<folder>/story.yaml` in the format of [docs/story.md](docs/story.md), starting from [scenarios/skeleton/story.yaml](scenarios/skeleton/story.yaml). No code changes are needed. The server validates every story at startup and refuses to start if one fails; to validate earlier, use the command in [server/README.md](server/README.md#commands).

## Where to change things

| Goal | Location |
|---|---|
| Story, people, obstacles, endings | `scenarios/<folder>/story.yaml` |
| Rolls, costs, tags, conversation rules | [server/src/rules/](server/src/rules/) |
| Sentence interpretation | [server/src/interpret.py](server/src/interpret.py) |
| Narration and its check | [server/src/narrate.py](server/src/narrate.py) |
| Turn order, saves | [server/src/service.py](server/src/service.py) (engine.md 7) |
| Screens | [client/screens/](client/screens/), [client/components/](client/components/) |

## Checks

[qa/README.md](qa/README.md) lists the checks to run for each kind of change.
