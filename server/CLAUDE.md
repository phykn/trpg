# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

User-facing setup (env layout, routes, table schema) is in [README.md](./README.md). Design rationale and per-turn flow live in `../docs/01-overview.md` ~ `../docs/05-codemap.md`.

## Working tree layout

`server/` is the FastAPI service. The venv, `pyproject.toml`, and `requirements.txt` live at the repo root — always invoke Python via `../.venv/bin/python` from `server/` (or `.venv/bin/python` from root). **Never create `server/.venv`.**

- Run pytest from the repo root (pyproject pins `testpaths=server/tests`).
- Run `run_api.py` from `server/` so dotenv resolves `server/.env.<APP_ENV>` and `src` imports work.
- Scenarios are authored at `../scenarios/<profile>/` and uploaded to Supabase Storage via the agency story tool: `APP_ENV=release .venv/bin/python -m agency.story.tool upload scenarios/<profile>` (from repo root). The running server reads from the bucket, never the local tree.

## Commands

```bash
# from repo root
.venv/bin/python -m pytest -q                # unit (live skipped)
RUN_LIVE=1 .venv/bin/python -m pytest -q     # add live tests; needs reachable LLM at BASE_URL
.venv/bin/python -m pytest server/tests/game/flow/test_turn.py::test_X   # single test
.venv/bin/ruff check server/                 # lint
bash server/scripts/check_relational_ssot.sh # graph-SSOT guard (CI-equivalent)

# from server/
../.venv/bin/python run_api.py               # cwd must be server/ for dotenv + relative paths
# upload from repo root: APP_ENV=release .venv/bin/python -m agency.story.tool upload scenarios/<profile>
```

## Architecture

### Layer rule

```
api → game.flow → llm.calls/game.engines → llm/game.ontology/wire → db → game.domain/game.rules
```

Upper depends on lower, never the reverse. Concretely:

- `game/domain/` + `game/rules/` — pure data shapes and tunable knobs. No imports outside themselves.
- `game/engines/` — pure game logic (combat math, apply state_changes, growth, inventory, skill, quest, recovery, invariants). No LLM, no I/O.
- `llm/calls/` — LLM call modules (classify, narrate, combat_narrate, summon, recommend) under the `llm/` package. Each module dir = `schema.py` + `runner.py` (+ `semantics.py` where needed). Prompts live separately under `src/locale/prompts/<agent>/prompt.<locale>.md`; `src/locale/prompts/_kernel.<locale>.md` holds universal rules (output language, register, ID hygiene, world vocabulary). `llm/calls/_runner.py:get_prompt(agent, locale)` joins kernel + agent prompt with `---`, cached per (agent, locale). `_runner.py` also owns the shared 5-attempt self-correction loop.
- `game/ontology/` — derived relational view over `GameState`. **The single source of truth for relations.**
- `llm/context/` — prompt input builders under the `llm/` package (surroundings for judge, layered context for narrate).
- `db/` — `SaveRepo` / `ScenarioRepo` Protocols (all-async) + Supabase and LocalFs adapters. Holds all persistence concerns.
- `wire/` — server↔client interface. `wire/models/` Pydantic payloads (single source of typed shapes), `wire/export.py` JSON-Schema bundle codegen → client `wire.gen.d.ts`, `wire/emit.py` SSE event builders, `wire/to_front.py` GameState → flat dict + typed state-slot models (`hero / subject / quest / place / combat`) the client renders, `wire/labels.py` UI label catalog wrappers + badge combiners, `wire/story_graph.py` reachable-edges shaping. All Korean composed strings end here.
- `game/flow/` — per-turn orchestration. `turn.py` / `roll.py` / `intro.py` are entrypoints (each yields `AsyncIterator[dict]` of SSE events).
- `api/` — thin FastAPI adapter. Glue only, no business logic.

**Import convention:** within a bucket use relative (`from .X` / `from ..X`); cross-bucket use absolute (`from src.<bucket>.X`). The 6-fold partition is the boundary — absolute import is the visible signal that a line crosses it.

### Relational SSOT — graph or entity?

`game/ontology/graph.py` is the single source of truth for relations. Inside `game/flow/`, `llm/context/`, `wire/`:

- **Asking who-relates-to-whom** must go through `GameGraph` — never via `state.characters.items()` fullscans, and never via direct relation fields (`char.location_id`, `char.inventory_ids`, `char.equipment.weapon`, `char.racial_skill_ids`, `char.learned_skill_ids`, `char.race_id`, `char.companions`, `quest.giver_id`, `quest.triggers[*].target_id`, `quest.rewards.items`, `loc.connections`, `loc.item_ids`, `chapter.quest_ids`). Prefer named helpers in `game/ontology/queries.py` (`inhabitants_of`, `inventory_of`, `equipment_of`, `connections_of`, `race_of`, `quests_given_by`, …); fall back to `graph.get_edges(...)` only when no helper fits.
- **Asking the value of an entity attribute** (HP, MP, stats, level, alive, disposition, mood, name, gender, status, memories, quest.status, quest.title) is fine via direct read.
- **Writing** stays on entities — `game/engines/apply.py`, `game/engines/combat.py` mutate fields. After a mutation that touches a relation field, the caller in flow calls `state.invalidate_graph()`; the next `state.graph()` rebuilds.
- **Graph caching:** `state.graph()` returns a lazily-built `GameGraph` cached on the state via `PrivateAttr` (does not round-trip through `model_dump_json`; `load_game` starts cold). Read paths just call `state.graph()`. Write paths in flow that touch relation fields must `state.invalidate_graph()` before re-reading or downstream consumers see stale edges.
- **Exceptions** that may read relation fields directly: `db/`, `game/domain/`, `game/engines/apply.py`, pure numeric engines (combat damage math, recovery, dc), and `game/ontology/graph.py` itself.

`scripts/check_relational_ssot.sh` enforces this by greppable patterns (list-shaped relation fields and `.characters.items()/.values()` iterations in `game/flow|llm/context|wire`). Whitelist a justified single line with a trailing `# ssot-allow: <reason>` comment.

### Persistence

The repo Protocols (`SaveRepo`, `ScenarioRepo`) are all-async. **The running server always uses Supabase**, regardless of `APP_ENV` — env files differ only in config knobs (basic auth, CORS, LLM routes), not in storage choice. Tests bypass the factory and use `LocalFsSaveRepo` / `LocalFsScenarioRepo` against `tmp_path`.

Five tables, all keyed on `game_id`:

- `games(game_id PK, meta jsonb, updated_at)` — `meta` carries `turn_count, pending_check, combat_state, active_*_id, next_log_id`. **`combat_state` must round-trip through meta** — without it, `/turn` reloads as combat-cleared and the engine restarts the fight every turn.
- `entities(game_id, kind, id, data jsonb)` PK `(game_id, kind, id)` — only entities mutated this turn are upserted.
- `log_entries(game_id, log_id int, entry jsonb)` — `log_id = entry.id` (app-managed monotonic).
- `history_entries(game_id, seq bigserial, entry jsonb)` — append-only turn summaries.
- `dialogue_entries(game_id, seq bigserial, entry jsonb)` — append-only dialogue.

All four child tables FK → `games(game_id) ON DELETE CASCADE`. RLS enabled with no policies (server uses service-role key, anon/auth keys see nothing).

**Per-turn flush order:** entity upserts + jsonl appends → `games.meta` last. A crash mid-flush leaves entity/jsonl committed and only meta stale, recoverable on next reload via `next_log_id` self-heal in `load_game`.

`SupabaseStorageScenarioRepo` caches `world.md` per profile (process-lifetime; restart to reload) and lazily materializes `local_profile_path` to a tempdir so `game/engines/invariants.Scenario.from_dir` can walk a real fs tree. `read_world_md(missing_ok=True)` does **not** cache empty results — a strict caller after a missing-ok caller will still raise.

`game_id` shape: `game_YYMMDD_HHMMSS_<6hex>` (UTC + `secrets.token_hex(3)`) so concurrent inits across isolates can't collide.

### LLM routing and thinking modes

- `LLM_ROUTE_<AGENT> = <provider>/<model>` resolves to an `LLMProfile` keyed by lowercased agent name. `LLM_ROUTE_DEFAULT` is required; matched agents (`classify`, `narrate_body`, `narrate_extract`, `combat_narrate`, `summon`, `recommend`) route per-agent, others fall back to default. Optional `LLM_ROUTE_<AGENT>_FALLBACK = <provider>/<model>` declares a secondary profile that engages once on `RateLimitError` (quota) and stays for the rest of that agent's retry loop.
- Provider blocks (`LLM_<NAME>_*` keys) live in the same `.env.<APP_ENV>` file and declare each provider's `BASE_URL`, `API_KEYS` (comma-separated, rotated round-robin per call), and `_THINK_OFF / _THINK_OPT / _THINK_ON` model lists. The three lists must be disjoint and together name every model the provider serves. Listed names must appear in exactly one THINK_* list.
- `LLM_<NAME>_NO_SYSTEM` lists models that reject `role: system` (Gemma via Gemini OpenAI-compat returns "Developer instruction is not enabled"); `LLMClient` folds the system prompt into the first user message for them.
- Per-call thinking behavior is driven by the model's THINK_* category: `OFF` sends no `extra_body`; `OPT` honors caller's `think` flag (default off) via `extra_body.chat_template_kwargs.enable_thinking` (llama.cpp) or `extra_body.reasoning_effort=medium` (Gemini 3.x, detected from `googleapis.com` in `base_url`); `OPT_ON` is the inverse (default on, opt out via `extra_body.reasoning_effort=minimal` on Gemini — Gemma 4 via Gemini lives here because it accepts only `minimal` to disable); `ON` always thinks.
- Provider-style logic lives in `src/llm/llama_cpp.py` and `src/llm/gemini.py`; `client.py` only dispatches.
- Inline `<thought>...</thought>` at the head of the answer (Gemma 4) is auto-routed to the think channel by `gemini.ThoughtSplitter` in both `chat` and `chat_stream` whenever the model is actively thinking.
- Missing required env keys → `KeyError` at startup. No silent defaults.

### Agent retry

Each agent runs a self-correction loop with `retries=5`. On `ValidationError` or semantic-check failure, the previous response and the error are appended to the message stream so the next attempt can correct itself. After 5 attempts, the loop raises by the last error type; flow code maps that to a domain error.

`narrate_body` is the exception. Body tokens stream to the client live, so a self-correction loop with appended error messages isn't possible — once a body delta has been sent the client can't take it back. It retries (up to 5×) only when the stream errors out before any body delta or yields zero body content; if any body delta has already been streamed, a later failure raises. `narrate_extract` runs after streaming finishes and uses the standard self-correction loop.

### state_changes

Four kinds only: `set / move / move_item / affinity`. Each has its own permission matrix in `game/engines/apply.py` (single source: `game/rules/permissions.py`, shared with `llm/calls/narrate/body/runner.py` and `llm/calls/narrate/extract/runner.py` so the prompt and engine use the same frozenset). Forbidden `set` fields are silently dropped per change; the rest of the batch still applies.

### Affinity

Scale `-100..+100`. **Single direction:** affinity is always read and written as `target.relations[actor]` — how the *target* views the *actor*. The reverse direction is not tracked.

With `social.friendly_threshold = 50`, a target at or above the threshold gives the actor `+social.roll_bonus = 2` on social rolls. Post-roll delta = `affinity_<grade>`, mirrored onto `intent`: hostile flips the sign; deceptive zeroes the success branch and doubles the failure one.

Two paths feed `relations`:
- **Narrate** emits an `affinity` state_change for verbal social acts (praise/insult/bribe/threaten/deceive). Schema carries `actor` + `target`, but the engine writes the delta to `state.characters[target].relations[actor]` only. Narrate prompt requires emission for verbal social acts even on the `pass` branch; `intent` picks `friendly | hostile | deceptive`; `grade` is read off the prose tone.
- **Engine** deducts `social.combat_affinity_drop` inside `emit_attack` and `emit_skill_cast` (offensive types only) on the target's side. Combat never reaches narrate, so without this hook attacks would leave the NPC's view of the player unchanged and trade gating wouldn't react.

Trade gating: `_merchants_payload` filters out NPCs whose `disposition.aggressive >= social.hostile_aggressive_threshold` regardless of `npc.relations[player]`. Without it, a hostile seed (bandit, wolf) carrying equipment would surface as a merchant on first sight (default `relations[player] = 0` satisfies `trade_threshold = 0`).

### Time

There is no minute/hour clock. `state.turn_count` is the sole time variable; `game/domain/clock.py:day_phase` derives one of `새벽 / 오전 / 오후 / 밤` from it (4 phases × `RULES.time.phase_turns = 10` turns each = 40-turn day cycle). Sleep recovery (`game/engines/recovery.py`) jumps `turn_count` to the next 새벽 boundary via `next_dawn_turn`. The narrate prompt sees the current phase only — no absolute date or hour exists.

### SSE event shape

`{"type": "...", "data": {...}}` per event. Types: `judge / pending_check / narrative_delta / suggestions / log_entry / state / combat_start / combat_turn / combat_end / done / error`. **`done` is not auto-appended** — `run_turn`'s roll branch ends after `pending_check`, and the client treats stream-close as the signal. The three `combat_*` types come from `combat_phase.py`; the client ignores their payload (state + log_entry are authoritative for UI) but tests use them as observable signals.

### Diagnostic logging (`FLOW_DEBUG`)

`game/flow/_diag.py` emits one structured stderr line per key flow / LLM event so Render Logs can be grepped for post-mortem. **On by default** — set `FLOW_DEBUG=0` to mute. Production debugging used this end-to-end to pin the move bug down to gemma wrapping JSON in markdown fences.

Two entrypoints, both safe no-ops when disabled:

- `diag(state.game_id, state.turn_count, "category:event", **kv)` — flow-layer code with GameState in scope.
- `llm_diag("category:event", **kv)` — code under `_runner` / `narrate/body/runner` that doesn't see GameState; flow callers prime gid/turn via `set_diag_context` (already done at `turn.py` / `roll.py` / `level_up.py` entries).

Existing tags live where they fire: `turn:start`, `classify -> ...`, `step:ok` / `step:fail`, `chain_step:*`, `roll:result`, `levelup:*`, `rest:*`, `combat:*`, `recruit:result`, `quest:action`, plus the LLM lifecycle (`llm:call/retry/fallback/done/fail`). The full inventory + add-a-hook pattern is in `_diag.py`'s module docstring — read that before adding new hooks.

### Memory writes (post-turn)

- Per-entity: `NarrateOutput.memory: dict[entity_id, "one-line POV recall"]`. **Player memory is first-person ("내가 …")**; NPC memory is from that NPC's POV. Don't write the same string into both.
- `memorable=true` is for scene-shifting events (decisions, promises, threats, deals, first impressions). Small talk is `false`.
- `memory_links: {entity_id: target_id}` decides which Subject panel surfaces each memory. Omitted entries default to `target_id=None`.
- Per-entity cap is `RULES.memory.cap`, applied at write time inside the entity model so the cap travels with the row.

## Stats / tiers / grades / prose voice

- Stat keys are ASCII abbreviations: `STR / DEX / CON / INT / WIS / CHA`. Judge's `stat` enum uses the same keys.
- Tiers are seven ASCII identifiers: `very_easy / easy / normal / hard / very_hard / legend / myth`. Korean display labels live in `src/locale/catalog/tier.toml`, accessed via `render(f"tier.{value}", "ko")`.
- Internal grade is five-way (`critical_success / success / partial_success / failure / critical_failure`). Client's `RollLogEntry.result` collapses to `success | partial | fail`.
- All player-facing Korean — narrate / combat_narrate bodies, the deterministic `잠시 정적이 흐릅니다` fallback in `game/flow/narrate.py`, every engine-side log line built in `game/flow/format.py` · `game/flow/error_phrases.py` · `game/flow/actions.py` · `game/flow/combat_phase.py` · `game/flow/turn.py` · `game/flow/roll.py` · `wire/to_front.py` — uses **2인칭 존댓말 합니다체**: `당신` for the player, `~합니다 / ~ㅂ니다 / ~입니다` endings.
- Canonical user-facing term for skills is **기술**. The classify prompt accepts `스킬` as a synonym from player input, but every other prompt and engine string says `기술`. Code identifiers and the `skills/` entity directory keep the English `skill`.

## Error hierarchy

`DomainError` (in `game/domain/errors.py`) splits two ways:

**Session lifecycle (HTTP/SSE error mapping):** `PendingCheckActive`, `PendingCheckExpected`, `JudgeMalformed`, `LLMUnavailable`, `PersistenceFailed`, `ProfileNotFound` (HTTP 422), `RaceNotFound` (422), `ProfileMalformed` (422).

**Action validation (absorbed into in-game GM log, no HTTP impact):** `LevelUpInvalid`, `InventoryInvalid`, `SkillInvalid`. `game/flow/actions.py` catches and runs through `game/flow/error_phrases.py:humanize_engine_error` for a Korean one-liner GM log entry. Turn ends normally.

Pydantic 422 (request-shape) and HTTP 404 (`game_id` not found) go through FastAPI's defaults — they are not `DomainError`.

## Stack notes

- Python 3.12+, Pydantic v2, FastAPI, uvicorn, httpx, async/await throughout.
- Pydantic models *are* the schema. Every state file round-trips through `GameState.model_validate_json(...)`. Don't hand-munge JSON.
- `LLMClient.chat_stream` is the streaming primitive; agents wrap it with their schema and retry loop.
- Single process. Horizontal scaling is out of scope. The LocalFs adapter uses one `asyncio.Lock` in `db/store.py`; Supabase relies on per-row PostgREST upserts plus the fixed flush order above.
- `run_api.py:_load_env` loads `.env.<APP_ENV>` if the file exists (default `APP_ENV=dev`); missing file is tolerated so managed envs (Render) can supply vars via OS env directly. Per-key fail-fast still happens at downstream `os.environ["..."]` reads. `APP_ENV=release` switches to `.env.release`. Both modes go through Supabase and require `SUPABASE_URL SUPABASE_SERVICE_KEY SUPABASE_SCENARIO_BUCKET`, plus `HOST PORT BASIC_AUTH_USER BASIC_AUTH_PASS CORS_ORIGINS LLM_ROUTE_DEFAULT` and the `LLM_<NAME>_*` provider block(s) referenced by the routes.
- `tests/conftest.py` exposes `fresh_state` (an empty `GameState`). End-to-end LLM verification is manual after merge; `scripts/smoke_judge.py` is a one-shot Gemini-routed classify sanity check.
