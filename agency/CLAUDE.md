# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

User-facing setup, full directory map, and the per-agent persona summary live in [README.md](./README.md). This file covers what's not derivable from a quick read of the source.

## Working tree

`agency/` is a Python package that imports the server's `src.*` directly. Both runners (`run_qa.py`, `run_story.py`) inject the repo root and `server/` into `sys.path` and read `server/.env.<APP_ENV>` → `.env.llama_cpp` → `.env.google` (mirrors `server/run_api.py`). The venv, `pyproject.toml`, and `requirements.txt` live at the repo root — invoke Python via `.venv/bin/python` from the repo root. **Never create `agency/.venv`.**

## Commands

```bash
# from repo root
.venv/bin/python agency/run_qa.py                                    # all 9 QA agents × 25 turns, profile=default
.venv/bin/python agency/run_qa.py --agent socialite --turns 25       # one agent
.venv/bin/python agency/run_qa.py --agent all --profile <profile>    # different scenario

.venv/bin/python agency/run_story.py character --scenario <name> --hint "은퇴한 노검사"   # one entity
.venv/bin/python agency/run_story.py scenario  --name <new> --prose path/to/prose.md     # whole scenario from prose
```

Single QA run output lands at the repo root `qa_test/<agent>/` (gitignored): `transcript.md` (human review), `sse.jsonl` (event replay), `final_state.json`, `saves/` (per-agent `LocalFsSaveRepo`), `llm/` (per-call request/response pairs). The runner wipes **only the targeted agent's directory** at session start, so re-running `socialite` doesn't touch `fighter`'s artifacts from an earlier full-suite run.

QA env: needs `BASE_URL` (LLM) plus `SUPABASE_URL` / `SUPABASE_SERVICE_KEY` / `SUPABASE_SCENARIO_BUCKET`. Story env: only `BASE_URL`.

## Architecture

### QA — in-process FastAPI, real LLM

`qa/harness/runner.py` wraps the server with `httpx.ASGITransport(app=build_app(...))`. No port, no second process — the request still travels through the real auth/SSE/error surface, but responses come back in-memory. The LLM stack is the same external server (`BASE_URL`, llama.cpp or Gemini) production uses.

Two hard isolation rules:

- **Saves go to `qa_test/<agent>/saves/` via `LocalFsSaveRepo`.** Production Supabase save tables are never written. The runner builds the app with explicit `save_repo=LocalFsSaveRepo(...)`, bypassing the factory.
- **Scenarios are read from the production Supabase Storage bucket (read-only)** via `SupabaseStorageScenarioRepo`. QA exercises the exact same scenario data the live server sees; do not point this at a different bucket to "fix" a missing profile — upload it to the prod bucket via `server/scripts/upload_scenarios.py`.

There is no automated reviewer. A previous local-LLM reviewer hallucinated turn numbers and misclassified normal `pending_check` waits as desyncs, so it was removed. **Claude Code reads `qa_test/<agent>/transcript.md` in chat and writes the verdict there** (PASS / WARN / FAIL, 1–3 wins, 1–3 issues with severity + turn-numbered evidence, then a cross-agent summary). When asked to evaluate a QA run, do not skim — open the transcripts directly and cite turn numbers.

Per-turn loop in `runner.py`: read `/state` → `PlayerAgent.next_input(state_summary, last_gm)` → `POST /turn` (drain SSE) → if `pending_check` event seen, auto `POST /roll`. Stops on the first `error` event (continuing past one is meaningless because state diverges from narrative). The agent's system prompt has a **Priority guards** block layered on top of the persona — level-up trigger (`레벨업 가능` in state) and skill-candidate trigger force a one-turn override — so persona schedules never block growth/learning that the engine has already exposed.

### Story — write entity, build scenario

`story/harness/runner.py:write_entity` is the single-entity primitive: build system prompt (`_base.md` + per-kind fragment + scenario `world.md` + existing instances + referenced kinds) → LLM → strip fences → `Model.model_validate_json` → ID pattern check → cross-ref check (manifest IDs only — see `_check_*_refs`) → entity invariants from `server/src/engines/invariants.py` → optional one-shot critic (`_critic.md`, `think=False`, advisory). Failure appends the bad answer + error to messages and retries, **trimming back to base + latest attempt** so retry context never exceeds the LLM ctx window. 5 retries, then raise.

`story/harness/scenario.py:build_scenario` is the prose-to-directory pipeline. It runs **three sequential decomposition phases** (setup → cast → arc, each with its own fragment + schema + validation) instead of one mega-call — single-decompose was fanning the LLM's attention across too many decisions and tripping the server's ctx ceiling on retries. Output composes into one `Decomposition` consumed by the rest of the pipeline.

Build order encodes the cross-ref dependency: `world.md → race (skeleton) → location (skeleton) → character (skeleton) → skill → item → attach → quest → chapter → meta → invariant sweep`. "Skeleton" means the LLM leaves cross-ref fields empty — `race.racial_skill_ids`, `location.connections`/`item_ids`, `character.{inventory_ids, equipment, racial_skill_ids, learned_skill_ids}` — and the `_attach_step` (pure data transform, no LLM) fills them after the referenced entities exist on disk. Attach order matters: races first (so character racial inheritance reads the final list), then locations, then characters.

Invariants split between cross-ref (manifest IDs in `runner.py`) and entity-level rules (stat pair-trade, HP/MP formula, slot-effect matching, carry weight; in `server/src/engines/invariants.py`). Don't duplicate logic — extend the server module if a new rule is needed.

Forced-ID enforcement: `write_entity(force_id=...)` raises if the LLM's emitted id differs by even one character. The decomposition phase fixes the ids; entity stages must respect them, and `_base.md` says so explicitly. Without this, the dependency graph collapses (race A's skill list points at skill X, but the skill writer emitted X' instead).

### Boundary

Entity-level rules and the engine's full invariant sweep live in `server/src/engines/invariants.py`; cross-ref between manifests is the only validation logic that lives here. New entity kinds → server first (model + invariant), then expose via `SPECS` here.

QA's loop intentionally stops on the first error — do not "retry past it." The transcript should reflect what actually happened, including the failure point.

## Cross-cutting conventions

- **Korean only for everything user-facing.** Persona prompts (`qa/agents/*.md`), entity fragments (`story/agents/*.md`), critic feedback, and any string that ends up in a transcript or scenario file are Korean. Engine-side narration uses **2인칭 존댓말 합니다체** — `당신` for the player, `~합니다 / ~ㅂ니다 / ~입니다` endings — and the user-facing skill term is **기술** (`스킬` survives only as a synonym in the dc_judge prompt). Code text (Python source, exception messages, validation errors) stays English.
- **Comments minimal, English-only.** Default to no comment — add one only when the *why* is non-obvious. Single short line. Korean is allowed inside an English comment only when quoting an in-game string the comment is reasoning about. No multi-paragraph docstrings, no multi-line `# ...` blocks. `# noqa` / `# type:` / shebangs aren't comments.
- **env is fail-fast.** `os.environ["BASE_URL"]` etc., never `os.environ.get(..., default)`. Missing keys must raise at startup, not later inside an LLM call.
- **Save-directory isolation.** QA always writes to `qa_test/<agent>/saves/` via `LocalFsSaveRepo`. Never repoint at production Supabase save tables. Scenarios are read-only from the prod bucket — fine to read, never write.
