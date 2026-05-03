# Agency — LLM office

Where the LLM staff that helps run the game works in teams. Each team owns its own directory holding agent prompts, the harness, and run output.

```
agency/
  run_qa.py     # QA team CLI entrypoint
  story/SKILL.md # Story-team Claude Code skill (no CLI — invoked from a session)
  qa/           # The QA team — plays the game and catches regressions
  story/        # The Story team — authors scenario seeds (race / character / ...)
```

## QA — game testing via AI players

Works like hiring a QA tester to play the game. Each turn an LLM generates the next input, the harness hits the server API in-process via ASGI, and collects SSE events into a transcript. There is no LLM reviewer — Claude Code reads the transcripts in chat and writes the review there (the local model hallucinates turn numbers and misclassifies normal pending_check waits as desyncs, so we removed it).

### Layout

```
agency/run_qa.py        # CLI entrypoint
agency/qa/
  agents/               # 9 phased personas, one .md per agent (25 turns each)
    socialite.md        # 친교 → 의뢰·bluff → 적대전환·집착 (호감도 라이프사이클 + combat 가드)
    fighter.md          # victory → broken_off/flee → downed/death_save → non-combat flee 폴백
    shopkeeper.md       # 인벤·거래·장비 → 성장·휴식·기술 학습 → 가드 (장착 중 sell·만피 use·affinity)
    scout.md            # 6 stat 강제 순환 → 환경 prop 수색 (hidden_items / hidden_connections)
    caster.md           # skill 의미 매칭 다양화 → MP·회피 표현 평타 폴백 → 회복 사이클
    survivor.md         # rest 분기 (safe → risky → dangerous, sleep_encounter)
    questor.md          # 첫 퀘스트 완료 → 둘째 퀘스트·fail_trigger → 검증 불가 주장·chapter 경계
    provocateur.md      # judge 15종 분기 fuzz (reject·chain·tail_intent·semantic 폴백)
    mourner.md          # 친교·살해 → 시체 호명·시신 검사 혼합 → off-screen 호명 (시체 발화 회귀)
  harness/
    agent.py            # PlayerAgent — system prompt + per-turn LLM call
    state_view.py       # front_state → input text for the player LLM
    transcript.py       # SSE → markdown / jsonl
    runner.py           # runs one session for a single agent

# Run output lands at the repo root under qa_test/<agent>/ (gitignored). Each
# target agent's directory is wiped at session start, so re-running one agent
# doesn't clobber the rest.
```

`AGENTS` in `run_qa.py` is the source of truth for membership. See [agency/CLAUDE.md](./CLAUDE.md) for the full playbook.

### How it works

- `httpx.AsyncClient(transport=ASGITransport(app))` calls the FastAPI app in-process. No port, no separate process, but the HTTP surface (auth/SSE/error) still exercised end-to-end.
- The LLM is the same external server you'd use otherwise (`BASE_URL`, e.g. llama.cpp).
- Saves are isolated to `qa_test/<agent>/saves/` via the LocalFs adapter — production Supabase is never touched. Scenarios are read directly from the production Supabase Storage bucket (read-only), so QA needs `SUPABASE_URL` / `SUPABASE_SERVICE_KEY` / `SUPABASE_SCENARIO_BUCKET` in env.
- Per-session flow: `POST /session/init` → `POST /session/{id}/intro` (optional) → `(read state → agent picks the next input → POST /turn → if pending_check, auto POST /roll)` repeated.

### Run

```bash
# every agent once (default 25 turns) against the `default` profile
.venv/bin/python agency/run_qa.py

# a specific agent
.venv/bin/python agency/run_qa.py --agent socialite --turns 25

# a different profile
.venv/bin/python agency/run_qa.py --agent all --profile <scenario_id>
```

env is auto-loaded from `server/.env.<APP_ENV>` (default `dev`) → `.env.llama_cpp` → `.env.google`, mirroring `server/run_api.py`. QA needs `BASE_URL` (LLM) and `SUPABASE_URL` / `SUPABASE_SERVICE_KEY` / `SUPABASE_SCENARIO_BUCKET` (scenarios are read from the bucket, read-only). `--profile` defaults to `default` — make sure that profile exists in the Supabase Storage bucket, or pass `--profile <name>`.

### Output

```
qa_test/
  index.md                      # per-agent turn count + error count + transcript links
  socialite/
    transcript.md               # human-readable per-turn record
    sse.jsonl                   # raw SSE events (for replay/debugging)
    final_state.json            # the full GameState at the end
    saves/                      # per-agent isolated LocalFs saves (wiped at session start)
    llm/                        # per-LLM-call request/response JSON pairs (player + server-side agents)
  fighter/...
  scout/...
```

### Using the output to fix code

After a change, run `run_qa.py` and read the artifacts in chat. Per agent: one verdict (PASS / WARN / FAIL), 1–3 wins, 1–3 issues with severity + turn-numbered evidence. Then a cross-agent summary that calls out repeated patterns. The full playbook (background launch, Monitor filter, verdict grading, reviewer pitfalls) is in [agency/CLAUDE.md](./CLAUDE.md).

### Limits

- Real-time guidance, not authoritative QA. Reviews are written by Claude Code in chat — they're a summary of the artifacts, not a separate verification pass.
- LLM call volume is heavy (1 player per turn + the server's own judge / narrate / combat_narrate / encounter_summon / skill_recommend calls). Short runs and fast feedback work best.
- Non-deterministic. Identical prompts produce different transcripts. Pinning regressions precisely needs a scenario mode (an explicit input sequence), not implemented yet.

## Story — scenario seed authoring

Single Claude Code skill (`agency/story/SKILL.md`) authors a complete scenario directory from one Korean prose `.md`. Claude itself writes the entity files; no external LLM call.

### Layout

```
agency/story/
  SKILL.md            # The skill — Claude reads this and follows the workflow
  tool.py             # Single CLI. Subcommands: decompose-{setup,cast,arc},
                      # check-entity, equip-fill, sweep, upload
  harness/
    _common.py        # ID pattern, trigger map, EntityWriterError
    decompose.py      # Pydantic models + _check_setup/_check_cast/_check_arc
    runner.py         # Cross-ref check helpers + SPECS metadata
    scenario.py       # fill_equipment — equipment slot derivation
```

### How to use

In a Claude Code session, point at the skill:

> "agency/story/SKILL.md 보고 path/to/prose.md 로 scenarios/foo 만들어줘"

Claude reads SKILL.md, drafts `.decomp/{setup,cast,arc}.json`, validates each phase via `tool.py`, then writes entity JSONs in the order race → location → character → skill → item, runs `equip-fill`, writes quests/chapters/meta, runs `sweep`, and (with confirmation) `upload`s to prod Supabase Storage.

### env

`tool.py` loads `server/.env.<APP_ENV>` (default `dev`). `upload` subcommand requires `APP_ENV=release` and `SUPABASE_URL` / `SUPABASE_SERVICE_KEY` / `SUPABASE_SCENARIO_BUCKET`. Other subcommands are pure local — no network.

### Reference integrity

Cross-ref check rules (per entity kind) and which manifests they validate against — see `agency/CLAUDE.md`. The full design rationale is in `docs/superpowers/specs/2026-05-04-story-skill-rewrite-design.md`.

### Limits

- Runtime entity injection during a game (adding a new NPC/item to a live save) belongs to the server and isn't designed yet.
