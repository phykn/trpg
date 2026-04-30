# CLAUDE.md

User-facing setup is in [README.md](./README.md); design intent starts at `../docs/01-overview.md` (single-turn flow `02-runtime.md`, code map `05-codemap.md`).

## Layout

`server/` is the FastAPI service. The venv, pyproject, and requirements live at the repo root. Run pytest from the root; run `run_api.py` from `server/` so dotenv resolves `server/.env` and src imports work.

```
src/
  api/         FastAPI surface — routes/, auth.py, sse.py, schema.py, deps.py. Glue only, no business logic.
  flow/        Turn orchestration. turn.py / roll.py / intro.py are the entrypoints (each yields an AsyncIterator[dict] of SSE events). The rest are helpers: combat_auto, combat_phase, encounter, rest, judge, narrate, memory_writer, actions, subject, dirty, format, skill_recommend.
  agents/      LLM agents — one dir per agent (dc_judge, narrate, combat_narrate, encounter_summon, skill_recommend), each with prompt.md / schema.py / runner.py. _runner.py is the shared retry-and-self-correct loop.
  llm/         OpenAI-compatible transport (client.py). Agents wrap chat_stream with their own schemas.
  engines/     Pure rule engines: apply (state_changes), combat, growth, inventory/, quest, recovery, skill, invariants. No LLM, no IO.
  ontology/    Derived views over GameState. graph.py builds typed-edge relations (located_at, equips, carries, connects_to, unlocks, gives_quest, kill_target_of, reward_of); target_view.py summarises one entity for prompts.
  context/     Prompt-facing context builders (surroundings, layered context).
  mapping/     to_front.py — GameState → flat dict the client renders. Korean dates, durations, composed strings, conditional labels are all built here.
  persistence/ init.py builds a new GameState from a profile + player input. store.py does atomic IO (.tmp + os.replace).
  domain/      Pure data shapes. entities.py (Character, Item, Location, Race, Skill, Quest, Chapter, Campaign), memory.py (Memory, PendingCheck, LogEntry union, TurnLogEntry, DialoguePair), state.py (GameState, CombatState), types.py (StatKey, Tier, Grade, Intent, Action), errors.py (DomainError + subclasses).
  rules/       config.py exposes the frozen RULES singleton (DC, social, memory, log, time, recovery, growth, skill, carry, trade, flee, combat, death). dc.py has roll math.
tests/         pytest, asyncio_mode=auto, live marker for LLM-required tests.
run_api.py     Entrypoint — loads env, builds the FastAPI app, runs uvicorn.
.env           Required. No fallbacks; missing keys raise at startup.
```

Layer rule: upper depends on lower, never the reverse. The dependency direction goes api → flow → agents/engines → llm/ontology/context/mapping → persistence → domain/rules.

`../scenarios/<profile>/` is the seed source (`world.md`, `start.json`, `player_template.json`, `profile.json`, plus `races/ characters/ items/ locations/ quests/ chapters/`); shared with `agency/story`. `../saves/` is the runtime store, gitignored. Per-game layout: `games/<game_id>/{meta.json, characters/<id>.json, items/<id>.json, ..., log.jsonl, history.jsonl, dialogue.jsonl}`. The active `game_id` is held by the client (browser localStorage), so a single server can host multiple users without one user's `init` clobbering another's "last game" pointer.

## Commands

```bash
# from repo root
.venv/bin/python -m pytest -q                # unit (live skipped). pyproject pins testpaths=server/tests.
RUN_LIVE=1 .venv/bin/python -m pytest -q     # add live tests; needs BASE_URL reachable.

# from server/
../.venv/bin/python run_api.py               # cwd must be server/ so dotenv reads server/.env.
```

## Stack and env

- Pydantic models *are* the schema. Every state file round-trips through `GameState.model_validate_json(...)`. Don't hand-munge JSON.
- `LLMClient.chat_stream` is the streaming primitive; agents wrap it with their schema and retry loop.
- One process, one save lock (`asyncio.Lock` in `persistence/store.py`). Horizontal scaling is out of scope.
- Required env vars: `HOST PORT BASE_URL BASIC_AUTH_USER BASIC_AUTH_PASS SAVES_DIR PROFILE_DIR CORS_ORIGINS`. Missing any → `KeyError` at startup. No silent defaults. `CORS_ORIGINS` is a comma-separated list of exact origins (scheme + host) the web client may load from.

## Stats / tiers / grades

- Stat keys are ASCII abbreviations: `STR / DEX / CON / INT / WIS / CHA`. The judge's `stat` enum uses the same keys.
- Tiers are seven Korean labels: `매우 쉬움 / 쉬움 / 보통 / 어려움 / 매우 어려움 / 전설 / 신화`. No English aliases.
- Internal grade is five-way (`critical_success / success / partial_success / failure / critical_failure`). The client's `RollLogEntry.result` collapses to `success | partial | fail`.

## Prose voice

All player-facing Korean text — narrate / combat_narrate bodies, the deterministic `잠시 정적이 흐릅니다` fallback in `flow/narrate.py`, every engine-side log line built in `flow/format.py` · `flow/error_phrases.py` · `flow/actions.py` · `flow/combat_phase.py` · `flow/turn.py` · `flow/roll.py` · `mapping/to_front.py` — uses **2인칭 존댓말 합니다체**: `당신` for the player, `~합니다 / ~ㅂ니다 / ~입니다` endings. Plain `-다` form has been retired from output.

The canonical user-facing term for skills is **기술**. The dc_judge prompt accepts `스킬` as a synonym from player input, but every other prompt and engine string says `기술`. Code identifiers and the `skills/` entity directory keep the English `skill`.

## Affinity

Scale is `-100..+100`. With `social.friendly_threshold = 50`, a target at or above the threshold gives the actor `+social.roll_bonus = 2`. Post-roll delta = `affinity_<grade>`, mirrored onto `intent`: hostile flips the sign; deceptive zeroes the success branch and doubles the failure one.

Two paths feed `relations`:
- **Narrate** emits an `affinity` state_change for social acts (praise, insult, bribe, threaten, deceive). One actor → target update per change. The narrate prompt now requires emission for verbal social acts even on the `pass` branch — `intent` picks `friendly | hostile | deceptive`, `grade` is read off the prose tone.
- **Engine** deducts `social.combat_affinity_drop` bidirectionally inside `emit_attack` and `emit_skill_cast` (offensive types only) — combat never reaches narrate, so without this hook attacks would leave `npc.relations[player]` (which gates trade) and `player.relations[npc]` (which feeds `social_bonus`) untouched.

Trade gating: `_merchants_payload` filters out NPCs whose `disposition.aggressive >= social.hostile_aggressive_threshold` regardless of `relations[player]`. Without it, a hostile seed (bandit, wolf) carrying equipment in its inventory would surface as a merchant on first sight, since `relations[player]` defaults to 0 — which satisfies `trade_threshold = 0`.

## Persistence

- Per-game dir: `../saves/games/<game_id>/`.
  - `meta.json` — singletons (`game_id, profile, player_id, turn_count, pending_check, pending_skill_candidates, combat_state, active_*_id, next_log_id`). Rewritten every turn end as the commit point. `combat_state` must round-trip through meta — without it, `/turn` reloads as combat-cleared and the engine restarts the fight every turn.
  - `<kind>/<id>.json` for `kind ∈ {characters, items, locations, races, skills, quests, chapters, campaigns}`. Only entities mutated this turn are rewritten.
  - `log.jsonl / history.jsonl / dialogue.jsonl` — append-only, one line per entry. No on-disk cap. In-memory caps (`RULES.log.display_turns`, `memory.turn_log_size`, `memory.recent_dialogue_turns`) only apply on tail-load and prompt assembly.
- `init_game` copies `../scenarios/<profile>/`'s seed entity dirs verbatim into the game dir, then writes the new player character + meta.
- Dirty tracking: `flow/dirty.py` collects `(kind, id)` writes plus appended log/history/dialogue entries. Finalize flushes entity files and jsonl appends first, `meta.json` last — a crash mid-flush leaves entity/jsonl committed and only `meta.json` stale, recoverable next turn.
- Per-entity `memories` cap is `RULES.memory.cap`, applied at write time inside the entity model so the cap travels with the file.
- Log entries get a monotonic id (`GameState.next_log_id`); the client dedupes between `log_entry` SSE and `state.log` by id.

## Memory writes (post-turn)

- Per-entity: `NarrateOutput.memory: dict[entity_id, "one-line POV recall"]`. **Player memory is first-person ("내가 …")**; NPC memory is from that NPC's POV. Don't write the same string into both.
- The LLM stays faithful to `player_input` — no escalation, no embellishment.
- `memorable=true` is for scene-shifting events (decisions, promises, threats, deals, first impressions). Small talk is `false`.
- `memory_links: {entity_id: target_id}` decides which Subject panel surfaces each memory. Omitted entries default to `target_id=None`.

## Agent retry

Each agent (judge, ...) runs a self-correction loop with `retries=5`. On `ValidationError` or semantic-check failure, the previous response and the error are appended to the message stream so the next attempt can correct itself. After 5 attempts, the loop raises by the last error type; flow code maps that to a domain error.

`narrate` is the exception. Body tokens stream to the client live, so a self-correction loop with appended error messages isn't possible — once a body delta has been sent the client can't take it back. It retries (up to 5×) only when the stream errors out before any body delta or yields zero body content; if any body delta has already been streamed, a later failure raises.

## state_changes

Four kinds only: `set / move / move_item / affinity`. Each has its own permission matrix in `engines/apply.py`. Forbidden `set` fields are silently dropped per change; the rest of the batch still applies.

## Time

There is no minute/hour clock. `state.turn_count` is the sole time variable; `domain/clock.py:day_phase` derives one of `새벽 / 오전 / 오후 / 밤` from it (4 phases × `RULES.time.phase_turns = 10` turns each = 40-turn day cycle). Sleep recovery (`engines/recovery.py`) jumps `turn_count` to the next 새벽 boundary via `next_dawn_turn`. The narrate prompt sees the current phase only — no absolute date or hour exists.

## SSE event shape

`{"type": "...", "data": {...}}` per event. Types: `judge / pending_check / narrative_delta / suggestions / log_entry / state / combat_start / combat_turn / combat_end / done / error`. The three `combat_*` types come from `combat_phase.py`; the client currently ignores their payload (state + log_entry are authoritative for UI), but tests use them as observable signals. **`done` is not auto-appended** — `run_turn`'s roll branch ends after `pending_check`, and the client treats stream-close as the signal.

## Tests

- Unit tests run without an LLM. Live tests need `RUN_LIVE=1` and `BASE_URL` (env, default `http://localhost:8000/v1`) reachable.
- `tests/conftest.py` exposes `fresh_state` (an empty `GameState`).
