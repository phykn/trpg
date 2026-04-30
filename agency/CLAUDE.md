# CLAUDE.md

Read this when working under `agency/`. For usage, see [README.md](./README.md).

## Layout

- `agency/qa/` — AI-player game-test team.
- `agency/story/` — scenario-seed authoring team. Output goes to `scenarios/<name>/` at the repo root.
- A new team adds its own `agents/` + `harness/` directories; its entry point `run_<team>.py` sits directly under `agency/`. Run output lands under `reports/<team>/<ts>/` at the repo root.

`agency` is an in-process consumer of `server`. It imports `server/src/...` and `server/run_api.py` directly, so any PR that changes server code should also verify import paths and signatures still hold here.

## Run environment

- The Python venv is the repo root's `.venv` — there is no agency-local venv.
- `run_qa.py` auto-loads `server/.env`. No separate `.env` under `agency/`.
- Only `BASE_URL` is required. `BASIC_AUTH_USER` / `BASIC_AUTH_PASS` are overwritten with dummy values (`"qa"` / `"qa"`) by the harness, since calls run in-process.

## Conventions

### Korean-only text

Agent prompts (`agents/*.md`), transcripts, READMEs — all Korean, same rule as the server.

### Output locations

- **QA** uses `reports/qa/<timestamp>/<agent>/saves/` as its `SAVES_DIR` per run. Never repoint this at the repo-root `saves/` — an in-progress real game would be overwritten.
- **Story** writes directly into `scenarios/<scenario>/` (where `PROFILE_DIR` points), because the next new game consumes that seed. If `<id>.json` already exists, the writer aborts instead of overwriting (`harness/runner.py`). LLM exchange logs are kept separately under `reports/story/<ts>/<agent>/`.

## Story team

### Entry points

All story-team work runs through the local LLM via `agency/run_story.py`:

- `run_story.py <kind> --scenario <s>` — author one entity. The generic `write_entity` in `harness/runner.py` does 5 self-correction retries plus reference-integrity checks.
- `run_story.py scenario --name <new> --prose <path>` — full prose → scenario build. Decompose runs as **three sequential phases** (setup / cast / arc) — each phase is its own LLM call with a focused fragment (`_decompose_setup.md` etc.) and Pydantic model, so retries don't re-do the whole decomposition and per-call output stays well under the server ctx ceiling. Phases compose into one `Decomposition` and feed the per-kind pipeline.

`<kind>` ∈ `{race, skill, location, item, character, quest, chapter}`. The CLI subparser picks up new kinds from `SPECS` automatically.

### Adding a new entity kind

To extend beyond the current 7 kinds:

1. `agency/story/agents/<kind>.md` — schema, required fields, reference rules. Same length as the other fragments (1–2 screens).
2. One row in `SPECS` in `agency/story/harness/runner.py` (model · sub_dir · fragment · ref_kinds · check_refs).
3. If a new reference-validation function is needed, write `_check_<kind>_refs`. Plain id-collision and pattern checks are already handled by the generic path.
4. `_base.md` covers entity-agnostic rules (Korean-only, JSON-only output, id pattern, "honor any forced-id hint") — no edits needed there.

### id enforcement in scenario mode

`run_story.py scenario --name <new>` pre-decides every entity id during the decomposition step, and entity steps must match. `write_entity(force_id=X)` compares the LLM's id against `X` inside `_check_id`; on mismatch it raises `EntityWriterError` into the self-correction loop, which forces the next attempt to fix it. This is what keeps cross-references (`start_location_id`, quest `target_id`, chapter `quest_ids`) intact between the decomposition and entity steps.

Single-entity calls (e.g. `run_story.py race ...`) leave the id free — only id collisions are checked.

## QA team

### Agent set

9 phased agents × 25 turns. Each agent runs 2-4 turn-numbered phases inside one persona's arc. `AGENTS` in `run_qa.py` is the source of truth.

| agent | focus |
|---|---|
| `socialite` | 친교 → 의뢰·bluff → 적대전환·집착 (호감도 라이프사이클 + combat 가드) |
| `fighter` | victory → broken_off/flee → downed/death_save → non-combat flee 폴백 |
| `shopkeeper` | 인벤·거래·장비 → 성장·휴식·기술 학습 → 가드 (장착 중 sell·만피 use·affinity) |
| `scout` | 6 stat 강제 순환 → 환경 prop 수색 (hidden_items / hidden_connections) |
| `caster` | skill 의미 매칭 다양화 → MP·회피 표현 평타 폴백 → 회복 사이클 |
| `survivor` | rest 분기 (safe → risky → dangerous, sleep_encounter) |
| `questor` | 첫 퀘스트 완료 → 둘째 퀘스트·fail_trigger → 검증 불가 주장·chapter 경계 |
| `provocateur` | judge 15종 분기 fuzz (reject·chain·tail_intent·semantic 폴백) |
| `mourner` | 친교·살해 → 시체 호명·시신 검사 혼합 → off-screen 호명·복귀 (시체 발화 회귀) |

전체 9 × 25T 한 번 = ~1h wall-clock.

### Running a full QA pass — playbook

This is the reproducible recipe Claude Code should follow whenever the user asks to "run QA" or "test the QA team". Single-agent runs (`--agent <name>`) are short enough to stay in the foreground; everything below is for `--agent all`.

**1. Launch in background, attach a persistent Monitor.**

The runner takes ~1 hour for the full pass (9 × 25T), so it must run in background. Output goes to `/tmp/qa_run.log`; the Monitor `tail -F`s that file with a tight grep filter, so each agent's boundary lines arrive as chat notifications without flooding context.

```
# Bash with run_in_background=true:
rm -f /tmp/qa_run.log && .venv/bin/python agency/run_qa.py \
  --agent all --profile <scenario_id> > /tmp/qa_run.log 2>&1

# Monitor (persistent=true, timeout_ms=3600000):
tail -F /tmp/qa_run.log 2>/dev/null | grep --line-buffered -E \
  "━━|→|Done\.|Error|Traceback|FAILED|HTTPError|ConnectionError|PersistenceFailed"
```

The agent emits `━━ <name> start ━━` then `→ done (turns=…, errors=…)` per agent, and `Done. Results: …/index.md` at the end. After the background task's completion notification fires, `TaskStop` the Monitor.

**2. Read the artifacts directly.** Per agent under `reports/qa/<ts>/<agent>/`:

- `transcript.md` — turn-by-turn human-readable log.
- `sse.jsonl` — raw event stream, one JSON object per line. Useful patterns:
  - judge action distribution: `python3 -c "import json; [print(ev['turn'], ev['data']) for line in open(p) if (ev:=json.loads(line)) and ev['type']=='judge']"` (replace `p`).
  - combat lifecycle: grep for `combat_start` / `combat_end` event types — repeated `combat_start` on consecutive turns is a red flag (combat state not persisting).
  - errors: events with `"type":"error"` carry `code` and `message`.
- `final_state.json` — full GameState dump. Check `turn_count`, `combat_state`, `player_01.hp/location_id/inventory_ids`, NPC `memories[]`.
- top-level `index.md` — turn counts, error counts, transcript links per agent.

**3. Write the review in chat.** No LLM reviewer — Claude Code reads the files and writes the review directly (the local model hallucinates turn numbers and confuses pending_check waits with state desyncs, which is why we removed it).

Per agent: one verdict, 1–3 wins, 1–3 issues with severity + turn-numbered evidence. Then a cross-agent summary that calls out repeated patterns — same persistence error in two agents, same narrative repeat in three — those are the worth-fixing ones.

**Verdict grading:**

- **PASS** — no error events, transcript reads naturally, final state matches the transcript's last explicit action.
- **WARN** — narrative-quality issue, mild state/narrative mismatch, but the run completed without errors.
- **FAIL** — error event mid-run (e.g. `PersistenceFailed`, `JudgeMalformed`), or final state actively contradicts the transcript at high confidence.

**Reviewer pitfalls (don't repeat):**

- `state.turn_count` is *not* the player-input count. Turns where `/turn` ended in a `pending_check` and was resolved by `/roll` (stat / combat_roll / death_save) don't double-bump it, and `chain` parts collapse into one bump. Don't flag the gap as desync.
- A `failure`/`critical_failure` roll where the GM still hands over information *is* a real issue (see `narrate/prompt.md`'s grade table) — flag it as narrative.
- Combat is one-shot cinematic ([docs/03-features.md §1](../docs/03-features.md)): `combat_start` → one `pending_check kind="combat_roll"` → `/roll` → `combat_end`. Repeated `combat_start` events on the same enemies on consecutive `/turn` calls means engine state didn't persist — real bug. But `combat_start` on one turn followed by `combat_end` on the next `/roll` is the normal shape, not a desync.
- Self-target combat (`targets=[player_id]`) should already be rejected upstream; if it slips through, that's a regression.

### Adding a new agent

1. `agency/qa/agents/<name>.md` — one page of system prompt: what kind of personality, what kind of behavior to focus on.
2. Add the name to the `AGENTS` list in `agency/run_qa.py`.

`PlayerAgent` uses the prompt verbatim as the system message; each turn it appends `state_summary` + `last_gm` + the recent flow as the user message (`harness/agent.py`).

## Adding a new team

Mirror the layout under `agency/<team>/`: an `agents/` + `harness/` pair, plus an entry point at `agency/run_<team>.py`. If the team needs the server FastAPI app, reuse the in-process pattern (`build_app` + `httpx.ASGITransport`, the QA way). If it only needs to author seeds, `LLMClient` + Pydantic validation is enough (the Story way). Drop run output under `reports/<team>/<ts>/` — the repo-root `.gitignore`'s `reports/` rule already covers it.

## Limits

- LLM call volume is heavy. Default to short runs for fast feedback.
- Non-deterministic. Pinning regressions precisely needs a scenario mode (explicit input sequence) — not implemented yet.
- `reports/` content isn't tracked in git. Move runs you want to keep into a separate folder.
