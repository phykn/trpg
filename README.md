# trpg

Korean-language TRPG. The LLM handles narrative and difficulty judgment; the engine handles state, rules, and time.

```
trpg/
  backend/    FastAPI + Pydantic v2 + OpenAI-compatible LLM. Game engine. → backend/README.md
  frontend/   Expo (React Native) single-screen client. → frontend/README.md
  agency/     LLM-staffed office that drives the backend in-process (QA + Story teams). → agency/README.md
  scenarios/  Seed packs (one dir per profile). Shared by backend and agency/story.
  docs/       Design notes (01-overview / 02-runtime / 03-features / 04-boundary / 05-codemap)
  saves/      Runtime game store (gitignored)
```

Setup and run details are in each sub-README; design intent starts at `docs/01-overview.md`.

## Quick start

An LLM server (e.g. llama.cpp) must be running somewhere reachable.

```bash
# from repo root, once
python3.12 -m venv .venv
.venv/bin/pip install -r requirements.txt

# fill out backend/.env, then
cd backend && ../.venv/bin/python run_api.py

# in another terminal, fill out frontend/.env, then
cd frontend && npm install && npx expo start
```

env vars are fail-fast — anything missing throws at startup.

## Tests

```bash
# from repo root
.venv/bin/python -m pytest -q                  # unit
RUN_LIVE=1 .venv/bin/python -m pytest -q       # only when the LLM server is reachable
```

## Stack

Python 3.12+ · Pydantic v2 · FastAPI · async/await · OpenAI-compatible LLM · Expo SDK 54 / RN 0.81 / React 19 · NativeWind v4 · expo-router. No DB — game state is per-entity JSON plus append-only JSONL under `saves/games/<game_id>/`.
