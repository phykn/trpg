# Words and Dice

A Korean mystery TRPG for the web. The player questions people in Korean and presents clues from the notebook to break lies and open what is held back. The rules decide what opens and what is learned, and local models only interpret the sentence and voice the answer. Stories are data in `scenarios/`; the engine code contains none.

- The **decision model** (Kanana, `:8081`) answers closed questions the engine builds, such as which topic a sentence asks about. It never invents anything.
- The **narration model** (gemma4, `:8082`, always non-thinking) voices only what the rules decided. The decision model checks the text against the facts, with up to two rewrites.

The game is being rebuilt. The old engine is gone; for now the server answers only `GET /health` and the client shows an empty title screen.

## Design docs

| Folder | Defines |
|---|---|
| [docs/game/](docs/game/01-concept.md) | The game: concept, loop, notebook, talk, blocks, time, screen, story format, authoring, the first story |
| [docs/data/](docs/data/01-ontology.md) | The data: ontology, story file, game state, changes, invariants and saves |
| [docs/engine/](docs/engine/01-ai.md) | The engine: models, API, story checks, implementation order |
| [docs/old/](docs/old/) | The removed engine, for reference only |

## Setup

Both models are required and run outside this repository ([local-models](https://github.com/phykn/local-models)). Start them first.

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

Open http://localhost:8090. `--local` needs no env file; the API is on `127.0.0.1:8000`. Other settings: [server/README.md](server/README.md). Phone and public access: [client/README.md](client/README.md).

On a Mac, `app/build.sh && open TRPG.app` builds a small app that runs `npm run serve` ([client/README.md](client/README.md#public-serving-workersdev)) with one button and shows the phone address with a QR code. It keeps output in `logs/server.log`, and quitting it stops the server.

## Checks

[qa/README.md](qa/README.md) lists the checks to run for each kind of change.
