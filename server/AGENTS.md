# Server Agent Guide

Read [README.md](README.md) for the request flow, API and configuration. Run Python from the root `.venv`; do not create `server/.venv`.

## Responsibilities

- `run_api.py`: construction and local/configured startup.
- `src/api.py`: HTTP boundary; `src/service.py`: serialized commands.
- `src/game/`: data models and pure game rules; no network or file I/O.
- `src/game/graph/`: graph data, queries, changes and invariants.
- `src/store.py`: atomic snapshot persistence.
- `src/view.py`: public response; `src/content.py`: authored-content validation.
- `src/locale/ko.py`: common player text; scenario JSON: story text.

Read relationships through graph query helpers. Node properties contain attributes, not a second relation store. Apply graph changes through `GraphChange`; never use a client response as authoritative state. `scripts/check_relational_ssot.sh` guards this boundary.

## Behavior contracts

Keep the original state unchanged when a choice fails. Check conditions and calculate roll thresholds before deducting costs. Preserve deterministic saved random state, content/schema versions, per-game locks and command receipts. A response is successful only after its entire turn is saved. The file store supports one server process.

Keep secret graph knowledge and random state out of `GameView`. Preserve the `body / agility / mind / presence` stat keys. Korean uses `당신`, polite `합니다체`, and `기술`.

## Checks

From the root, run the applicable file under `server/tests/` before the full suite. Rules/content: `test_game.py`; API/save/retry: `test_api.py`; graph: `tests/graph/`; startup/env: `test_env.py`. Run the scenario validator for content changes and Ruff for server changes. Root [AGENTS.md](../AGENTS.md) lists exact commands.
