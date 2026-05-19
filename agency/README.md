# Agency

Local tools for testing and authoring the game. QA plays the dev build against local scenarios. Story builds and validates local scenario directories.

```
agency/
  run_qa.py     # QA team CLI entrypoint
  story/SKILL.md # Story-team Codex skill (no CLI — invoked from a session)
  qa/           # The QA team — plays the game and catches regressions
  story/        # The Story team — authors scenario seeds (race / character / ...)
```

## QA — game testing via AI players

Works like a QA tester playing the game. Each turn an LLM generates the next input, the harness hits the graph API in-process via ASGI, and records responses into a transcript. There is no LLM reviewer — Codex reads the transcripts in chat and writes the review there.

### Layout

```
agency/run_qa.py        # CLI entrypoint
agency/qa/
  agents/               # 9 phased personas, one .md per agent (25 turns each)
    socialite.md        # 친교 → 의뢰·bluff → 적대 전환
    fighter.md          # 짧은 전투와 도주·패배 경로
    shopkeeper.md       # 인벤·거래·장비 → 성장·휴식 가드
    scout.md            # 4스탯 행동 순환 → 환경 탐사
    caster.md           # 기술 사용·마나·회복 사이클
    survivor.md         # 휴식과 위험한 환경 반응
    questor.md          # 퀘스트 수락·진행·완료 경로
    provocateur.md      # 모호 입력·거절·분류 경계
    mourner.md          # NPC 사망 후 시체·기억 상호작용
  harness/
    agent.py            # PlayerAgent — system prompt + per-turn LLM call
    state_view.py       # front_state → input text for the player LLM
    transcript.py       # graph API responses → markdown / jsonl
    runner.py           # runs one session for a single agent

# Run output lands at the repo root under qa_test/agency/<agent>/ (gitignored). Each
# target agent's directory is wiped at session start, so re-running one agent
# doesn't clobber the rest.
```

`AGENTS` in `run_qa.py` is the source of truth for membership.

### How it works

- `httpx.AsyncClient(transport=ASGITransport(app))` calls the FastAPI app in-process. No port, no separate process, but the HTTP surface (auth/error) is still exercised end-to-end.
- The LLM uses the same env-profile routing as the server (`LLM_ROUTE_*` plus `LLM_<PROVIDER>_*`, e.g. a local OpenAI-compatible server or Gemini).
- Graph saves are isolated to `qa_test/agency/<agent>/saves/` via `LocalFsGraphRepo`; production Supabase is never touched.
- Scenarios are read from local `SCENARIO_DIR` through `LocalFsScenarioRepo`. The default dev profile is `dev_test`.
- Per-session flow: `POST /session/graph/init` → `(read graph state → agent picks the next input → POST /graph/input → if pending confirmation, auto POST /graph/confirm)` repeated.

### Run

```bash
# every agent once (default 25 turns) against the `dev_test` profile
.venv/bin/python agency/run_qa.py

# a specific agent
.venv/bin/python agency/run_qa.py --agent socialite --turns 25

# a different profile
.venv/bin/python agency/run_qa.py --agent all --profile <scenario_id>
```

env is auto-loaded from `server/.env.shared` → `server/.env.<APP_ENV>` (default `dev`) → `.env.local` → `.env.google`, mirroring `server/run_api.py`. QA needs `LLM_ROUTE_DEFAULT` and the referenced provider block (`LLM_<PROVIDER>_BASE_URL`, `LLM_<PROVIDER>_API_KEYS`, and THINK_* model lists), plus `SCENARIO_DIR` for local scenario files. `--profile` defaults to `dev_test`.

### Output

```
qa_test/
  agency/
    index.md                    # per-agent turn count + error count + transcript links
    socialite/
      transcript.md             # human-readable per-turn record
      sse.jsonl                 # raw graph API events (for replay/debugging)
      final_state.json          # final graph front-state payload
      saves/                    # per-agent isolated LocalFs graph saves
      llm/                      # per-LLM-call request/response JSON pairs
    fighter/...
    scout/...
```

### Using the output to fix code

After a change, run `run_qa.py` and read the artifacts in chat. Per agent: one verdict (PASS / WARN / FAIL), 1–3 wins, 1–3 issues with severity + turn-numbered evidence. Then a cross-agent summary that calls out repeated patterns.

### Limits

- Real-time guidance, not authoritative QA. Reviews are written by Codex in chat; they're a summary of the artifacts, not a separate verification pass.
- LLM call volume is heavy (1 player per turn + the server's classify / graph narration calls). Short runs and fast feedback work best.
- Non-deterministic. Identical prompts produce different transcripts. Pinning regressions precisely needs a scenario mode (an explicit input sequence), not implemented yet.

## Story — scenario seed authoring

Single Codex skill (`agency/story/SKILL.md`) authors a complete scenario directory from one Korean prose `.md`. Codex itself writes the entity files; no external LLM call.

### Layout

```
agency/story/
  SKILL.md            # The skill — Codex reads this and follows the workflow
  tool.py             # Single CLI. Subcommands: decompose-{setup,cast,arc},
                      # check-entity, equip-fill, sweep
  tools/storage.py    # Release Supabase Storage upload/download
  harness/
    _common.py        # ID pattern, trigger map, EntityWriterError
    decompose.py      # Pydantic models + _check_setup/_check_cast/_check_arc
    runner.py         # Cross-ref check helpers + SPECS metadata
    scenario.py       # fill_equipment — equipment slot derivation
```

### How to use

In a Codex session, point at the skill:

> "agency/story/SKILL.md 보고 path/to/prose.md 로 scenarios/foo 만들어줘"

Codex reads SKILL.md, drafts `.decomp/{setup,cast,arc}.json`, validates each phase via `tool.py`, then writes entity JSONs in the order race → location → character → skill → item, runs `equip-fill`, writes quests/chapters/meta, and runs `sweep`.

### env

`tool.py` loads `server/.env.shared` and `server/.env.<APP_ENV>` (default `dev`). Local story subcommands need no network. Release publish/download uses `APP_ENV=release .venv/bin/python -m agency.story.tools.storage upload|download ...` and requires `SUPABASE_URL` / `SUPABASE_SERVICE_KEY` / `SUPABASE_SCENARIO_BUCKET`.

### Reference integrity

Cross-ref check rules live in `agency/story/harness/runner.py`. Product-level seed invariants live in `docs/plan.md`.

### Limits

- Runtime entity injection during a game (adding a new NPC/item to a live save) belongs to the server and isn't designed yet.
