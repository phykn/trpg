# AGENTS.md

This file provides guidance to Codex (Codex.ai/code) when working with code in this repository.

User-facing setup, full directory map, and the per-agent persona summary live in [README.md](./README.md). This file covers what's not derivable from a quick read of the source.

## Working tree

`agency/` is a Python package that imports the server's `src.*` directly. `run_qa.py` injects the repo root and `server/` into `sys.path` and reads `server/.env.<APP_ENV>` → `.env.llama_cpp` → `.env.google` (mirrors `server/run_api.py`). The venv, `pyproject.toml`, and `requirements.txt` live at the repo root — invoke Python via `.venv/bin/python` from the repo root. **Never create `agency/.venv`.**

## Commands

```bash
# from repo root
.venv/bin/python agency/run_qa.py                                    # all 9 QA agents × 25 turns, profile=default
.venv/bin/python agency/run_qa.py --agent socialite --turns 25       # one agent
.venv/bin/python agency/run_qa.py --agent all --profile <profile>    # different scenario

# Story building — invoke from a Codex session, no CLI:
#   "agency/story/SKILL.md 보고 path/to/prose.md 로 scenarios/<name> 만들어줘"
#
# Helper CLI (검사·attach·sweep·upload):
.venv/bin/python -m agency.story.tool decompose-setup <setup.json>
.venv/bin/python -m agency.story.tool decompose-cast  <setup.json> <cast.json>
.venv/bin/python -m agency.story.tool decompose-arc   <setup.json> <cast.json> <arc.json>
.venv/bin/python -m agency.story.tool check-entity    <kind> <scenario_dir> <entity.json> [--decomp <dir>] [--skeleton]
.venv/bin/python -m agency.story.tool equip-fill      <scenario_dir>
.venv/bin/python -m agency.story.tool sweep           <scenario_dir>
APP_ENV=release .venv/bin/python -m agency.story.tool upload <scenario_dir>
APP_ENV=release .venv/bin/python -m agency.story.tool download <profile> [--out <dir>]
```

Single QA run output lands at the repo root `qa_test/<agent>/` (gitignored): `transcript.md` (human review), `sse.jsonl` (event replay), `final_state.json`, `saves/` (per-agent `LocalFsSaveRepo`), `llm/` (per-call request/response pairs). The runner wipes **only the targeted agent's directory** at session start, so re-running `socialite` doesn't touch `fighter`'s artifacts from an earlier full-suite run.

QA env: needs `BASE_URL` (LLM) plus `SUPABASE_URL` / `SUPABASE_SERVICE_KEY` / `SUPABASE_SCENARIO_BUCKET`. Story tool (`tool.py`): local subcommands need no network; `upload` needs `APP_ENV=release` + Supabase keys.

## Architecture

### QA — in-process FastAPI, real LLM

`qa/harness/runner.py` wraps the server with `httpx.ASGITransport(app=build_app(...))`. No port, no second process — the request still travels through the real auth/SSE/error surface, but responses come back in-memory. The LLM stack is the same external server (`BASE_URL`, llama.cpp or Gemini) production uses.

Two hard isolation rules:

- **Saves go to `qa_test/<agent>/saves/` via `LocalFsSaveRepo`.** Production Supabase save tables are never written. The runner builds the app with explicit `save_repo=LocalFsSaveRepo(...)`, bypassing the factory.
- **Scenarios are read from the production Supabase Storage bucket (read-only)** via `SupabaseStorageScenarioRepo`. QA exercises the exact same scenario data the live server sees; do not point this at a different bucket to "fix" a missing profile — upload it to the prod bucket via `APP_ENV=release .venv/bin/python -m agency.story.tool upload scenarios/<profile>`.

There is no automated reviewer. A previous local-LLM reviewer hallucinated turn numbers and misclassified normal `pending_check` waits as desyncs, so it was removed. **Codex reads `qa_test/<agent>/transcript.md` in chat and writes the verdict there** (PASS / WARN / FAIL, 1–3 wins, 1–3 issues with severity + turn-numbered evidence, then a cross-agent summary). When asked to evaluate a QA run, do not skim — open the transcripts directly and cite turn numbers.

Per-turn loop in `runner.py`: read `/state` → `PlayerAgent.next_input(state_summary, last_gm)` → `POST /turn` (drain SSE) → if `pending_check` event seen, auto `POST /roll`. Stops on the first `error` event (continuing past one is meaningless because state diverges from narrative). The agent's system prompt has a **Priority guards** block layered on top of the persona — level-up trigger (`레벨업 가능` in state) and skill-candidate trigger force a one-turn override — so persona schedules never block growth/learning that the engine has already exposed.

### Story — SKILL.md driven scenario build

`agency/story/SKILL.md`는 Codex 세션이 산문(prose) 한 편으로 시나리오 디렉토리 한 개를 빌드하기 위한 절차서다. 외부 LLM 호출 없음 — Codex 자체가 작성자다.

`tool.py`는 검증·자동채우기·업로드를 모은 단일 CLI. SKILL.md가 각 단계에서 호출한다. 종료 코드 0(OK)/1(검증 실패)/2(usage 오류) + 사람이 읽을 수 있는 stderr 메시지.

빌드 흐름: decompose 3-phase → world.md → race(full) → location(full) → character(--skeleton) → skill → item → equip-fill → quest → chapter → meta → sweep → upload.

엔티티 작성자(Codex)가 각 단계에서 `check-entity --decomp .decomp/` 로 자기 글을 검증. 풀-의존 검사(character의 inventory) 는 `--skeleton` 으로 sweep까지 미룸.

검사 깨졌을 때: 같은 파일 2회까지만 자동 수정, 그 이상은 사용자에게 보고. 위쪽 단계 실수가 늦게 드러나면 `.decomp/` JSON부터 고치고 영향받는 파일 재검사 — 가짜 ID 같은 우회는 금지.

기존 LLM 호출 루프(`runner.write_entity`, `decompose._decompose_phase`, `critic.run_critic`)와 LLM 전용 프롬프트 (`agents/*.md`)는 모두 제거됨. `harness/decompose.py` 의 Pydantic 모델 + `_check_*` 함수, `harness/runner.py`의 cross-ref 검사 + SPECS, `harness/scenario.py`의 `fill_equipment` 만 남아 `tool.py`가 쓰는 헬퍼다.

### Boundary

Entity-level rules and the engine's full invariant sweep live in `server/src/game/engines/invariants/`; cross-ref between manifests is the only validation logic that lives here. New entity kinds → server first (model + invariant), then expose via `SPECS` here.

QA's loop intentionally stops on the first error — do not "retry past it." The transcript should reflect what actually happened, including the failure point.

## Cross-cutting conventions

- **Korean only for everything user-facing.** Persona prompts (`qa/agents/*.md`), the story SKILL (`story/SKILL.md`), and any string that ends up in a transcript or scenario file are Korean. Engine-side narration uses **2인칭 존댓말 합니다체** — `당신` for the player, `~합니다 / ~ㅂ니다 / ~입니다` endings — and the user-facing skill term is **기술** (`스킬` survives only as a synonym in the dc_judge prompt). Code text (Python source, exception messages, validation errors) stays English.
- **Comments minimal, English-only.** Default to no comment — add one only when the *why* is non-obvious. Single short line. Korean is allowed inside an English comment only when quoting an in-game string the comment is reasoning about. No multi-paragraph docstrings, no multi-line `# ...` blocks. `# noqa` / `# type:` / shebangs aren't comments.
- **env is fail-fast.** `os.environ["BASE_URL"]` etc., never `os.environ.get(..., default)`. Missing keys must raise at startup, not later inside an LLM call.
- **Save-directory isolation.** QA always writes to `qa_test/<agent>/saves/` via `LocalFsSaveRepo`. Never repoint at production Supabase save tables. Scenarios are read-only from the prod bucket — fine to read, never write.
