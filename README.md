# trpg

Korean-language TRPG. The LLM classifies player intent and writes narration; the engine handles state, rules, rolls, and time.

```
trpg/
  server/     FastAPI + Pydantic v2 + OpenAI-compatible LLM. Game engine. → server/README.md
  client/     Expo (React Native) single-screen client. → client/README.md
  agency/     Local QA + Story tools that drive the server in-process. → agency/README.md
  scenarios/  Local seed source (one dir per profile). Uploaded to release Storage via agency.story.tools.storage upload.
  docs/       Target design contract and rebuild plan. Start at docs/plan.md.
```

Stack: Python 3.12+ · Pydantic v2 · FastAPI · OpenAI-compatible LLM (local OpenAI-compatible server / Gemini hosted) · Supabase Postgres + Storage · Expo SDK 54 / RN 0.81 / React 19 · NativeWind v4. Runtime graph saves live in Supabase Postgres by default; dev can use local graph/scenario repos through env. Setup details in each sub-README; design intent starts at `docs/README.md`.

Env files mirror on both sides: server loads `server/.env.shared` then `server/.env.dev` or `server/.env.release`; client uses `client/.env.dev` or `client/.env.release`. The active file is picked by mode — `dev` for local work, `release` for prod.

## Local dev

```bash
# backend — from server/. APP_ENV=dev is the default → loads server/.env.dev.
cd server && ../.venv/bin/python run_api.py

# frontend — from client/. loads client/.env.dev.
cd client && npm start          # Expo Go via QR (LAN / Tailscale Funnel — see client/README.md)
npm run web                     # web on localhost:8081
```

## Deploy

Backend → Render (Auto-Deploy on commit). Frontend → Cloudflare Workers.

```bash
# backend — push triggers Render to build + restart with APP_ENV=release (loads server/.env.release).
git push origin main

# frontend — from client/. Wipes dist/, expo export against client/.env.release, wrangler deploy.
npm run deploy
```

One-time setup: upload scenarios with `APP_ENV=release .venv/bin/python -m agency.story.tools.storage upload scenarios/<profile>`; install + auth wrangler with `npm install -g wrangler && wrangler login`; add the deploy URL to server `CORS_ORIGINS`.
