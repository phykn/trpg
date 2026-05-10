# AGENTS.md

This file provides guidance to Codex (Codex.ai/code) when working with code in this repository.

User-facing setup (env layout, routes, table schema) is in [README.md](./README.md). Design rationale and per-turn flow live in `../docs/README.md` and `../docs/02-runtime.md`.

## Working tree layout

`server/` is the FastAPI service. The venv, `pyproject.toml`, and `requirements.txt` live at the repo root — always invoke Python via `../.venv/bin/python` from `server/` (or `.venv/bin/python` from root). **Never create `server/.venv`.**

- Run pytest from the repo root (pyproject pins `testpaths=server/tests`).
- Run `run_api.py` from `server/` so dotenv resolves `server/.env.<APP_ENV>` and `src` imports work.
- Scenarios are authored at `../scenarios/<profile>/`. Dev can read them locally with `SCENARIO_REPO=local`; release reads Supabase Storage after publish via `APP_ENV=release .venv/bin/python -m agency.story.tools.storage upload scenarios/<profile>` (from repo root).

## Commands

```bash
# from repo root
.venv/bin/python -m pytest -q                # unit (live skipped)
RUN_LIVE=1 .venv/bin/python -m pytest -q     # add live tests; needs reachable LLM at BASE_URL
.venv/bin/python -m pytest server/tests/api/test_graph_session_routes.py::test_X   # single test
.venv/bin/ruff check server/                 # lint
bash server/scripts/check_relational_ssot.sh # graph-SSOT guard (CI-equivalent)

# from server/
../.venv/bin/python run_api.py               # cwd must be server/ for dotenv + relative paths
# upload from repo root: APP_ENV=release .venv/bin/python -m agency.story.tools.storage upload scenarios/<profile>
```

## Architecture

### Layer rule

```
api → game.runtime → llm.calls/game.engines → llm/wire → db → game.domain/game.rules
```

Upper depends on lower, never the reverse. Concretely:

- `game/domain/` + `game/rules/` — pure data shapes and tunable knobs. No imports outside themselves.
- `game/engines/` — pure game logic (combat math, graph changes, growth, inventory, skill, quest, recovery, invariants). No LLM, no I/O.
- `llm/calls/` — structured LLM call modules under the `llm/` package. `classify` is the only module here right now; graph narration uses runtime prompts with agents `graph_intro` and `graph_narrate`. Structured prompts live under `src/locale/prompts/<agent>/prompt.<locale>.md`; `src/locale/prompts/_kernel.<locale>.md` holds universal rules (output language, register, ID hygiene, world vocabulary). `llm/calls/_runner.py:get_prompt(agent, locale)` joins kernel + agent prompt with `---`, cached per (agent, locale). `_runner.py` also owns the shared 3-attempt self-correction loop.
- `game/domain/graph.py` + `game/domain/graph_query.py` — graph data and relation queries. **The graph is the runtime source of truth.**
- `llm/context/` — prompt input builders under the `llm/` package (graph surroundings for classify and narration).
- `db/` — `GraphRepo` / `ScenarioRepo` Protocols (all-async) + Supabase and LocalFs adapters. Holds persistence concerns.
- `wire/` — server↔client interface. `wire/models/` Pydantic payloads and `wire/graph_to_front.py` carry the graph runtime state the client renders.
- `game/runtime/` — graph-native session orchestration for init, input, explicit actions, confirmations, combat, level-up, and state loading.
- `api/` — thin FastAPI adapter. Glue only, no business logic.

**Import convention:** within a bucket use relative (`from .X` / `from ..X`); cross-bucket use absolute (`from src.<bucket>.X`). The 6-fold partition is the boundary — absolute import is the visible signal that a line crosses it.

### Relational SSOT — graph or entity?

The runtime `Graph` is the single source of truth for relations. Inside `game/runtime/`, `llm/context/`, and `wire/`:

- **Asking who-relates-to-whom** must go through graph query helpers such as `characters_at`, `inventory_of`, `equipment_of`, `connections_of`, and `known_skills_of`.
- **Asking the value of a node attribute** reads `GraphNode.properties`.
- **Writing** returns or applies `GraphChange` objects; do not mutate client payloads or prompt payloads as state.
- **Exceptions** that may touch row shapes directly: `db/`, row codec modules, and graph query/building helpers.

`scripts/check_relational_ssot.sh` guards graph source-of-truth boundaries. Prefer deleting stale entity scans over adding new allow comments.

### Persistence

The repo Protocols (`GraphRepo`, `ScenarioRepo`) are all-async. Repos default to Supabase; dev can set `GRAPH_REPO=local` or `SCENARIO_REPO=local`. Tests bypass the factory and use LocalFs adapters against `tmp_path`.

Graph runtime tables are all keyed on `game_id`:

- `game_progress(game_id PK, progress jsonb)` — player id, locale, active quest, pending confirmation, combat state, and `next_log_id`.
- `graph_nodes(game_id, node_id, node_type, properties jsonb)` PK `(game_id, node_id)`.
- `graph_edges(game_id, edge_id, edge_type, from_node_id, to_node_id, properties jsonb)` PK `(game_id, edge_id)`.
- `log_entries(game_id, log_id int, entry jsonb)` — `log_id = entry.id` (app-managed monotonic).
- `history_entries(game_id, seq bigserial, entry jsonb)` — append-only turn summaries.
- `dialogue_entries(game_id, seq bigserial, entry jsonb)` — append-only dialogue.

Runtime child tables should FK to `game_progress(game_id) ON DELETE CASCADE`. RLS enabled with no policies (server uses service-role key, anon/auth keys see nothing).

`load_runtime_state` bumps `next_log_id` past the highest loaded log id so a partial write cannot reuse a log id on the next turn.

`SupabaseStorageScenarioRepo` caches `world.md` per profile (process-lifetime; restart to reload). `read_world_md(missing_ok=True)` does **not** cache empty results — a strict caller after a missing-ok caller will still raise.

`game_id` shape: `game_YYMMDD_HHMMSS_<6hex>` (UTC + `secrets.token_hex(3)`) so concurrent inits across isolates can't collide.

### LLM routing and thinking modes

- `LLM_ROUTE_<AGENT> = <provider>/<model>` resolves to an `LLMProfile` keyed by lowercased agent name. `LLM_ROUTE_DEFAULT` is required; graph runtime currently calls `graph_intro`, `classify`, and `graph_narrate`. Optional `LLM_ROUTE_<AGENT>_FALLBACK = <provider>/<model>` declares a secondary profile that engages once on `RateLimitError` (quota) and stays for the rest of that agent's retry loop.
- Provider blocks (`LLM_<NAME>_*` keys) live in the same `.env.<APP_ENV>` file and declare each provider's `BASE_URL`, `API_KEYS` (comma-separated, rotated round-robin per call), and `_THINK_OFF / _THINK_OPT / _THINK_ON` model lists. The three lists must be disjoint and together name every model the provider serves. Listed names must appear in exactly one THINK_* list.
- `LLM_<NAME>_NO_SYSTEM` lists models that reject `role: system` (Gemma via Gemini OpenAI-compat returns "Developer instruction is not enabled"); `LLMClient` folds the system prompt into the first user message for them.
- Per-call thinking behavior is driven by the model's THINK_* category: `OFF` sends no `extra_body`; `OPT` honors caller's `think` flag (default off) via `extra_body.chat_template_kwargs.enable_thinking` (llama.cpp) or `extra_body.reasoning_effort=medium` (Gemini 3.x, detected from `googleapis.com` in `base_url`); `OPT_ON` is the inverse (default on, opt out via `extra_body.reasoning_effort=minimal` on Gemini — Gemma 4 via Gemini lives here because it accepts only `minimal` to disable); `ON` always thinks.
- Provider-style logic lives in `src/llm/llama_cpp.py` and `src/llm/gemini.py`; `client.py` only dispatches.
- Inline `<thought>...</thought>` at the head of the answer (Gemma 4) is auto-routed to the think channel by `gemini.ThoughtSplitter` in both `chat` and `chat_stream` whenever the model is actively thinking.
- Missing required env keys → `KeyError` at startup. No silent defaults.

### Agent retry

Each structured agent runs a self-correction loop with `retries=3`. On `ValidationError` or semantic-check failure, the previous response and the error are appended to the message list so the next attempt can correct itself. The same attempt counter also covers transient transport / 5xx errors (`OSError`, `asyncio.TimeoutError`, `openai.InternalServerError`, `openai.APIConnectionError`) — these `continue` instead of raising until the budget is spent, then map to `LLMUnavailable`. After 3 attempts, the loop raises by the last error type; runtime or route code maps that to a domain error.

### Diagnostic logging (`FLOW_DEBUG`)

`src/llm/diag.py` emits one structured stderr line per key runtime / LLM event so Render Logs can be grepped for post-mortem and per-step timing. **On by default** — set `FLOW_DEBUG=0` to mute.

Line shape: `[HH:MM:SS.mmm gid=XXX turn=Y t=N.NNNs LAYER] tag key=val ...`
- `t=` is wall-clock seconds since the previous diag line on this task; reset at every `set_diag_context` (turn entry). Read it as "this step took N seconds."
- `LAYER` is `engine` or `llm   ` so engine vs. LLM time can be told apart at a glance.

Three entrypoints, all safe no-ops when disabled:

- `set_diag_context(game_id, turn)` — primes contextvars and resets the timing clock.
- `engine_diag("category:event", **kv)` — runtime or route code.
- `llm_diag("category:event", **kv)` — LLM helper code.

Call `set_diag_context` at graph runtime entrypoints before downstream LLM or engine work if a new path needs tagged logs.

Existing tags live where they fire. Read `src/llm/diag.py` before adding new hooks.

## Stats / tiers / grades / prose voice

- Graph-facing stat keys are `body / agility / mind / presence`; do not introduce legacy six-stat payloads into graph code, seed data, tests, or client state.
- Tiers and grades should stay internal unless a graph payload explicitly needs them.
- All player-facing Korean built by graph runtime, LLM prompts, and `wire/graph_to_front.py` uses **2인칭 존댓말 합니다체**: `당신` for the player, `~합니다 / ~ㅂ니다 / ~입니다` endings.
- Canonical user-facing term for skills is **기술**. The classify prompt accepts `스킬` as a synonym from player input, but every other prompt and engine string says `기술`. Code identifiers and the `skills/` entity directory keep the English `skill`.

## Error hierarchy

`DomainError` (in `game/domain/errors.py`) splits two ways:

**Session lifecycle (HTTP error mapping):** graph route errors map to HTTP status codes in `api/routes/session_graph.py`. Missing games return 404; malformed profile/player input returns 422; pending-confirmation conflicts return 409 or 422.

**Action validation:** graph action errors should either return a graph log entry with no state-changing `GraphChange`, or raise a route-level 422 when the request shape cannot be applied.

Pydantic 422 (request-shape) and HTTP 404 (`game_id` not found) go through FastAPI's defaults — they are not `DomainError`.

## Stack notes

- Python 3.12+, Pydantic v2, FastAPI, uvicorn, httpx, async/await throughout.
- Pydantic models *are* the schema. Graph rows and progress rows round-trip through row codec models. Don't hand-munge JSON.
- Single process. Horizontal scaling is out of scope. The LocalFs graph adapter uses one `asyncio.Lock` in `db/store.py`; Supabase relies on per-row PostgREST upserts and should add DB-level locks before multi-isolate writes to one game are allowed.
- `run_api.py:_load_env` loads `.env.<APP_ENV>` if the file exists (default `APP_ENV=dev`); missing file is tolerated so managed envs (Render) can supply vars via OS env directly. Per-key fail-fast still happens at downstream `os.environ["..."]` reads. `APP_ENV=release` switches to `.env.release`. Supabase mode requires `SUPABASE_URL SUPABASE_SERVICE_KEY SUPABASE_SCENARIO_BUCKET`, plus `HOST PORT BASIC_AUTH_USER BASIC_AUTH_PASS CORS_ORIGINS LLM_ROUTE_DEFAULT` and the `LLM_<NAME>_*` provider block(s) referenced by the routes.
- End-to-end LLM verification is manual after merge; `scripts/smoke_classify.py` is a one-shot env-routed classify sanity check.
