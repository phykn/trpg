# CLAUDE.md

Guidance for Claude Code working in this directory.

## Layout

`back/` is the FastAPI backend. Run all backend commands from here.

- `src/` — application code (see Architecture below).
- `tests/` — pytest suite (`asyncio_mode=auto`, marker `live` for tests that hit the local LLM).
- `config/profiles/<profile>/` — game seeds (world.md, start.json, player_template.json, races/, locations/, items/, characters/, quests/, chapters/).
- `../data/` — runtime save dir (repo root, peer of `back/`). Gitignored. Layout per game: `games/<game_id>/{meta.json, characters/<id>.json, items/<id>.json, ..., log.jsonl, history.jsonl, dialogue.jsonl}`.
- `run_api.py` — entry point. Reads env, builds FastAPI app, runs uvicorn.
- `.env` — required (no fallbacks; missing keys raise KeyError).

Authoritative design docs live in `../docs/` (01-plan, 02-runtime, 03-features, 04-boundary).

## Commands

```bash
.venv/bin/python -m pytest tests/ -q                  # unit tests (skips live)
RUN_LIVE=1 .venv/bin/python -m pytest tests/ -q       # include live tests (LLM must be up)
.venv/bin/python run_api.py                            # boot server (env loaded via dotenv)
```

## Stack constraints

- **Python 3.12+**. Pydantic v2, FastAPI, async/await throughout. uvicorn dev server.
- **OpenAI-compatible LLM** at `BASE_URL` (currently llama.cpp). `LLMClient.chat_stream` is the streaming primitive; agents wrap it with their own schemas + retry.
- **Pydantic models are the schema**. Every state file is `GameState.model_validate_json(...)`. No manual JSON munging.
- **Single-process** save lock (`asyncio.Lock` in `state/store.py`); horizontal scaling out of scope for P1.

## Architecture (layered)

Higher layers depend on lower; never the reverse. From edges in:

1. `api/` — FastAPI surface. `routes.py` defines the protected router (basic auth via `auth.py`). `sse.py` wraps any `AsyncIterator[dict]` into `text/event-stream`. `schema.py` holds the request/response models. **No business logic** beyond glue.
2. `pipeline/` — orchestration of one player turn. `turn.py` exposes `run_turn`, `run_roll`, `run_intro` (each an `AsyncIterator[dict]` of SSE events). `judge.py`, `narrate.py`, `apply.py`, `memory_writer.py`, `dc.py`, `context.py` are the building blocks called from `turn.py`.
3. `llm_client/` — the LLM transport (`client.py`) plus per-agent dirs (`agents/dc_judge/`, `agents/narrate/`). Each agent dir has `prompt.md` (system prompt), `schema.py` (input/output models), `runner.py` (retry-corrected call loop), `__init__.py` (public exports).
4. `ontology/` — derived views over `GameState`. `graph.py` builds a typed edge graph from entity relations (located_at, equips, carries, connects_to, unlocks, gives_quest, kill_target_of, reward_of). `target_view.py` summarizes one entity for narrate/judge prompts.
5. `mapping/to_front.py` — projects `GameState` → flat dict the frontend expects (`hero`, `subject`, `quest`, `place`, `log`). **All Korean date/period/composition strings are produced here**, not on the frontend.
6. `state/` — `models.py` is `GameState` (the single root container). `init.py` builds a fresh `GameState` from a profile seed. `store.py` is atomic IO (`.tmp` + `os.replace`) plus the `.current` file lifecycle.
7. `domain/` — pure data shapes. `entities.py` (Character, Item, Location, Race, Quest, Chapter, Campaign), `memory.py` (Memory, PendingCheck, LogEntry union, TurnLogEntry, DialoguePair), `types.py` (StatKey, Tier, Grade, Intent, Action literals).
8. `rules.py` — single frozen `RULES` instance (DC tiers, affinity deltas, memory caps, log size, time per turn). Tunable knobs live here, not scattered in pipeline code.
9. `errors.py` — `DomainError` + 8 subclasses (CombatNotSupported, PendingCheckActive, JudgeMalformed, PersistenceFailed, ProfileNotFound, RaceNotFound, ...). Raised at the layer that detects, caught at the boundary that responds.

## Conventions

### Korean-only

All user-facing text (prompts, log entries, NPC dialogue, place names, error messages reaching the client) is Korean. There is no localization layer; legacy `LocalizedText{ko,en}` is gone.

### Stats / tiers / grades

- Stats keys are ASCII abbreviations only: `STR/DEX/CON/INT/WIS/CHA`. The judge `stat` enum uses the same keys.
- Tier is one of seven Korean labels: `매우 쉬움 / 쉬움 / 보통 / 어려움 / 매우 어려움 / 전설 / 신화`. No English aliases.
- Grade is 5-level (`critical_success / success / partial_success / failure / critical_failure`) internally; the front-facing `RollLogEntry.result` collapses to `success | fail`.

### Affinity

Range `-100..+100` (legacy 0..100 is gone). `social.friendly_threshold = 50` triggers the `+social.roll_bonus = 2` modifier. Delta on a roll = `affinity_<grade>` mirrored by `intent` (hostile flips sign; deceptive zeros success and doubles failure).

### Environment

`.env` is required; missing keys raise `KeyError` at startup. No silent defaults. Required: `HOST PORT BASE_URL BASIC_AUTH_USER BASIC_AUTH_PASS DATA_DIR PROFILE_DIR`.

### Persistence

- Per-game directory: `../data/games/<game_id>/`. Layout:
  - `meta.json` — singleton fields (game_id, profile, player_id, world_time, turn_count, pending_check, active_*_id, next_log_id). Always rewritten at end of turn (commit point).
  - `<kind>/<id>.json` for each `kind` in `characters / items / locations / races / quests / chapters / campaigns`. Only entities mutated this turn are rewritten.
  - `log.jsonl`, `history.jsonl`, `dialogue.jsonl` — append-only one-line-per-entry. Disk has no cap; the in-memory caps (`RULES.log.display_turns` / `memory.turn_log_size` / `memory.recent_dialogue_turns`) only apply when loading the tail or feeding the prompt.
- `init_game` copies the seed entity dirs from `config/profiles/<profile>/` into the game dir verbatim, then writes the new player character + meta.
- Dirty tracking: `pipeline.turn._Dirty` accumulates `(kind, id)` pairs (from `apply_changes` and `write_memories`) plus the new log/history/dialogue entries; `_finalize` flushes them — entities + jsonl appends first, meta last.
- `data/.current` holds the latest `game_id`; `GET /session/current` reads it.
- Log entries carry monotonic ids (`GameState.next_log_id`). Frontend can dedupe by id when both `log_entry` SSE events and `state.log` arrive.
- Per-entity `memories` cap is from `RULES.memory.cap`, applied at write time inside the entity model (so the cap travels with the entity file).
- Single-process save lock (`asyncio.Lock` in `state/store.py`) serializes file writes within a process; horizontal scaling is out of scope for P1. Crash mid-flush leaves entity/jsonl writes committed but `meta.json` stale, recoverable by replaying the next turn.

### Memory writes (post-turn)

- Per-entity viewpoint: `NarrateOutput.memory: dict[entity_id, "그 시점 한 줄"]`. **Player memory is first-person ("내가 …")**; NPC memory is from the NPC's POV. Never write the same string into both sides.
- LLM must stay faithful to `player_input` (no escalation/embellishment).
- `memorable=true` is reserved for scene-shifting events (decisions, promises, threats, deals, first impressions). Small talk → `false`.
- `memory_links: {entity_id: target_id}` controls which Subject panel surfaces the memory; missing entries become `target_id=None`.

### Agent retry policy

Each agent (judge, narrate) has a self-correction loop (`retries=5`). On `ValidationError` or semantic check failure, the previous bad response and the error are appended to the message stream so the next attempt can correct itself. After 5 attempts the original error type is raised; the pipeline maps it to a domain error.

### state_changes

Five types only (`set / set_time / move / move_item / affinity`), each with its own permission matrix in `pipeline/apply.py`. Forbidden `set` fields are silently rejected per-change; the rest of the batch still applies. Time may not move backward.

### SSE event shapes

`{"type": "...", "data": {...}}` per event. Types: `judge / pending_check / narrative_delta / log_entry / state / done / error`. `done` is **not** auto-appended; the `roll` branch of `run_turn` ends after `pending_check` and the client treats stream-close as the signal.

### Tests

- Unit tests run without the LLM; live tests are skipped unless `RUN_LIVE=1`.
- Live tests assume `BASE_URL` reachable (env var `BASE_URL` or default `http://localhost:8000/v1`).
- `tests/conftest.py` provides `fresh_state` (empty `GameState`).
