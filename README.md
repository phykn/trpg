# trpg

Korean-language TRPG. The LLM handles narrative and difficulty judgment; the engine handles state, rules, and time.

```
trpg/
  server/     FastAPI + Pydantic v2 + OpenAI-compatible LLM. Game engine. → server/README.md
  client/     Expo (React Native) single-screen client. → client/README.md
  agency/     LLM-staffed office that drives the server in-process (QA + Story teams). → agency/README.md
  scenarios/  Local seed source (one dir per profile). Uploaded to Supabase Storage via server/scripts/upload_scenarios.py for the running server.
  docs/       Design notes (01-overview / 02-runtime / 03-features / 04-boundary / 05-codemap)
```

Saves live in Supabase Postgres (schema: `server/migrations/001_init.sql`), not on disk. Setup and run details are in each sub-README; design intent starts at `docs/01-overview.md`.

## Quick start

A reachable LLM (local llama.cpp via `BASE_URL`, or hosted Gemini via `LLM_ROUTE_*`) and a Supabase project (URL + service-role key, plus a Storage bucket for scenarios) are required. Apply the schema once with `server/migrations/001_init.sql`, then upload a scenario tree with `server/scripts/upload_scenarios.py`.

```bash
# from repo root, once
python3.12 -m venv .venv
.venv/bin/pip install -r requirements.txt

# fill out server/.env.dev (or .env.release for prod), then
cd server && ../.venv/bin/python run_api.py

# in another terminal, fill out client/.env, then
cd client && npm install && npx expo start
```

env vars are fail-fast — anything missing throws at startup. `APP_ENV=dev` (default) loads `.env.dev`; `APP_ENV=release` loads `.env.release`. Both modes write to Supabase.

## Tests

```bash
# from repo root
.venv/bin/python -m pytest -q                  # unit
RUN_LIVE=1 .venv/bin/python -m pytest -q       # only when the LLM server is reachable
```

## Stack

Python 3.12+ · Pydantic v2 · FastAPI · async/await · OpenAI-compatible LLM (llama.cpp local / Gemini hosted) · Supabase Postgres + Storage for saves and scenarios · Expo SDK 54 / RN 0.81 / React 19 · NativeWind v4 · expo-router. Web export deploys to Cloudflare Workers.
