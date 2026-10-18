# Server Agent Guide

Read [README.md](README.md) for the turn flow, routes and configuration. Run Python from the root `.venv`; do not create `server/.venv`.

## Responsibilities

- `run_api.py`: app construction, `--local` defaults, story loading and validation at startup.
- `src/api.py`: HTTP boundary; `src/service.py`: locks, revisions, receipts, the order of a turn.
- `src/content/`: story schema, loading, validation and the `validate` CLI. Only `load.py` reads files.
- `src/world/`: graph, edge queries and saved state models. Edge traversal stays in `graph.py` and `query.py`.
- `src/rules/`: pure rules. Every state change goes through an op in `rules/dsl.py` and emits a `Change`.
- `src/scene/`: what the player knows (`build`), its text for models (`render`), and the client view (`view`).
- `src/interpret.py` and `src/narrate.py`: the only model callers besides service startup; `src/models/`: Kev and Qwen clients.
- `src/locale/ko.py`: engine-owned Korean. Story text lives only in `scenarios/`.

## Behavior contracts

- The engine knows no story. No story id, name or sentence appears in `src/`; `tests/test_boundaries.py` enforces it.
- Both models are required. Do not add a mode that runs without them or replaces narration with authored text.
- Models never create places, people, items or knowledge. Kev only picks from closed options; rules decide every outcome.
- `resolve` works on a copy and leaves the original state unchanged on any error. Dice come from `(seed, turn, step)`.
- A turn is saved before its response; narration is generated afterwards, checked by Kev, and cached in the same save.
- Qwen runs non-thinking only. Keep `enable_thinking: false` on every request.
- Korean uses `당신`, polite `합니다체`, and `기술`. Comments and validation errors stay English.

## Checks

From the root: `.venv/bin/python -m pytest -q`, `.venv/bin/ruff check server/`, `bash server/scripts/check_relational_ssot.sh`. Validate any story you touch with `python -m src.content validate`. Real-model behavior needs the scripts in `server/scripts/`; record runs under `qa_test/agency/<run>/` and cite turn numbers.
