# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

Repo-root guide. After moving into the directory you want to work in, also read its `CLAUDE.md`.

## Layout

Korean-language TRPG. Three pieces in one bundle:

- `server/` — FastAPI + Pydantic v2 + OpenAI-compatible LLM. Game engine. See [server/CLAUDE.md](./server/CLAUDE.md).
- `client/` — Expo (RN 0.81 / React 19) single-screen app. Streams from the server over SSE. [client/CLAUDE.md](./client/CLAUDE.md).
- `agency/` — LLM agent office. QA team (in-process game playthroughs) + Story team (writes seeds into `scenarios/<name>/`). [agency/CLAUDE.md](./agency/CLAUDE.md).
- `docs/` — North-star design notes in 5 chapters (`01-overview` / `02-runtime` / `03-features` / `04-boundary` / `05-codemap`). Index is `docs/01-overview.md`.
- `scenarios/<name>/` — scenario seeds. The server's `PROFILE_DIR` points here, and agency/story builds new ones here. Tree: `profile.json`, `world.md`, `start.json`, `player_template.json`, `races/`, `characters/`, `locations/`, `items/`, `quests/`, `chapters/`, `skills/`.
- `saves/` — gitignored. One directory per game (`games/<game_id>/...` + `.current`).

The venv, pyproject, and requirements are a single set at the repo root. All Python code (server, agency, tests) shares the same `.venv/`.

## Commands

```bash
# from repo root
.venv/bin/python -m pytest -q                     # unit (live skipped). pyproject pins testpaths=server/tests
RUN_LIVE=1 .venv/bin/python -m pytest -q          # only when the LLM is up (BASE_URL must be reachable)

# single test
.venv/bin/python -m pytest server/tests/test_apply.py::test_name -q

# API server (cwd must be server/ so dotenv reads server/.env)
cd server && ../.venv/bin/python run_api.py

# one QA agent run
.venv/bin/python agency/run_qa.py --agent diplomat --turns 20

# client (separate from the venv, just npm)
cd client && npx expo start
```

## Cross-cutting conventions

Apply repo-wide. When a sub-CLAUDE.md repeats the same rule, the sub version is just more specific — not in conflict.

- **Korean only.** Every piece of text that reaches the user (LLM prompts, logs, NPC lines, error messages, agent prompts) is in Korean. No localization layer. The old `LocalizedText{ko,en}` is gone. In-game prose and engine-side log lines use **2인칭 존댓말 합니다체** — `당신` for the player, `~합니다 / ~ㅂ니다 / ~입니다` endings — and avoid the `박-` root entirely. The user-facing skill term is **기술** (`스킬` survives only as a synonym in the dc_judge prompt). Code text — server/agency/test source, validation error messages, structural prompts — stays English.
- **env is fail-fast.** No `??` defaults, no silent defaults. Missing keys throw at startup. Applies to both `server/.env` and `client/.env`.
- **Display data is built on the server and shipped over.** Korean dates, durations, composed strings, conditional labels — all built in `server/src/mapping/to_front.py` and rendered as-is on the client. Client types only carry the fields the UI renders.
- **LLM agent retry = 5-shot self-correction loop.** judge and friends append the previous response + error to the message stream on `ValidationError` or semantic-check failure, so the next attempt corrects itself. After 5 attempts, the loop raises by the last error type. **narrate is an exception**: body tokens stream to the client live, so it retries (up to 5×) only on stream-transport errors or an empty body — once any body delta has been sent, a later failure raises.
- **Stats keys = ASCII abbreviations** (`STR/DEX/CON/INT/WIS/CHA`). The judge's stat enum uses the same keys.
- **Save-directory isolation.** Production saves go in the repo-root `saves/`. Agency QA runs use the repo-root `reports/qa/<ts>/<agent>/saves/` — keep them separate, never repoint at the production `saves/`.

## Stack

- Python 3.12+, Pydantic v2, FastAPI, async/await throughout, uvicorn.
- An OpenAI-compatible LLM server pointed at by `BASE_URL` (currently llama.cpp).
- Single process + `asyncio.Lock` to serialize file writes. No DB — game state is per-entity JSON plus append-only JSONL.
- Expo SDK 54 / RN 0.81 / React 19, NativeWind v4, expo-router with typedRoutes, `expo/fetch` for SSE streaming (standard `fetch` doesn't support SSE body streaming on RN).
