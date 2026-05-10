# AGENTS.md

This file provides guidance to Codex (Codex.ai/code) when working with code in this repository.

User-facing setup, full directory map, and the per-agent persona summary live in [README.md](./README.md). This file covers what's not derivable from a quick read of the source.

## Working tree

`agency/` is a Python package that imports the server's `src.*` directly. `run_qa.py` injects the repo root and `server/` into `sys.path` and reads `server/.env.<APP_ENV>` plus optional `.env.local` / `.env.google` provider overlays. The venv, `pyproject.toml`, and `requirements.txt` live at the repo root — invoke Python via `.venv/bin/python` from the repo root. **Never create `agency/.venv`.**

## Commands

```bash
# from repo root
.venv/bin/python agency/run_qa.py                                    # all 9 QA agents × 25 turns, profile=dev_test
.venv/bin/python agency/run_qa.py --agent socialite --turns 25       # one agent
.venv/bin/python agency/run_qa.py --agent all --profile <profile>    # different scenario

# Story building — invoke from a Codex session, no CLI:
#   "agency/story/SKILL.md 보고 path/to/prose.md 로 scenarios/<name> 만들어줘"
#
# Local scenario helper CLI:
.venv/bin/python -m agency.story.tool decompose-setup <setup.json>
.venv/bin/python -m agency.story.tool decompose-cast  <setup.json> <cast.json>
.venv/bin/python -m agency.story.tool decompose-arc   <setup.json> <cast.json> <arc.json>
.venv/bin/python -m agency.story.tool check-entity    <kind> <scenario_dir> <entity.json> [--decomp <dir>] [--skeleton]
.venv/bin/python -m agency.story.tool equip-fill      <scenario_dir>
.venv/bin/python -m agency.story.tool sweep           <scenario_dir>

# Story release storage tools:
APP_ENV=release .venv/bin/python -m agency.story.tools.storage upload <scenario_dir>
APP_ENV=release .venv/bin/python -m agency.story.tools.storage download <profile> [--out <dir>]
```

Single QA run output lands at the repo root `qa_test/agency/<agent>/` (gitignored): `transcript.md` (human review), `sse.jsonl` (event replay), `final_state.json`, `saves/` (per-agent `LocalFsGraphRepo`), `llm/` (per-call request/response pairs). The runner wipes **only the targeted agent's directory** at session start, so re-running `socialite` doesn't touch `fighter`'s artifacts from an earlier full-suite run.

QA env: needs `BASE_URL` (LLM) and local scenario env from `server/.env.dev` (`SCENARIO_REPO=local`, `SCENARIO_DIR=../scenarios`). Story tool (`tool.py`) is local-only. Release storage publish/download lives in `agency.story.tools.storage` and needs `APP_ENV=release` + Supabase keys.

## Architecture

### QA — in-process FastAPI, real LLM

`qa/harness/runner.py` wraps the server with `httpx.ASGITransport(app=build_app(...))`. No port, no second process — the request still travels through the real auth/error surface, but responses come back in-memory. The LLM stack is the same external server (`BASE_URL`, local OpenAI-compatible server or Gemini) production uses.

Two hard isolation rules:

- **Graph saves go to `qa_test/agency/<agent>/saves/` via `LocalFsGraphRepo`.** Production Supabase graph tables are never written.
- **Scenarios are read from local `SCENARIO_DIR` via `LocalFsScenarioRepo`.** QA is dev/local by design. If a profile is missing, create or restore it under `scenarios/<profile>/`; do not point QA at release Storage.

There is no automated reviewer. A previous local-LLM reviewer hallucinated turn numbers and misclassified normal waiting states as desyncs, so it was removed. **Codex reads `qa_test/agency/<agent>/transcript.md` in chat and writes the verdict there** (PASS / WARN / FAIL, 1–3 wins, 1–3 issues with severity + turn-numbered evidence, then a cross-agent summary). When asked to evaluate a QA run, do not skim — open the transcripts directly and cite turn numbers.

Per-turn loop in `runner.py`: read `/session/{id}/graph/state` → `PlayerAgent.next_input(state_summary, last_gm)` → `POST /session/{id}/graph/input` → if a pending confirmation appears, auto-confirm through `/session/{id}/graph/confirm`. Stops on the first error response because continuing past one would hide the failure point. The agent's system prompt has a **Priority guards** block layered on top of the persona, so persona schedules never block growth that the engine has already exposed.

### Story — SKILL.md driven scenario build

`agency/story/SKILL.md`는 Codex 세션이 산문(prose) 한 편으로 시나리오 디렉토리 한 개를 빌드하기 위한 절차서다. 외부 LLM 호출 없음 — Codex 자체가 작성자다.

`tool.py`는 로컬 검증·자동채우기를 모은 단일 CLI. SKILL.md가 각 단계에서 호출한다. 종료 코드 0(OK)/1(검증 실패)/2(usage 오류) + 사람이 읽을 수 있는 stderr 메시지.

빌드 흐름: decompose 3-phase → world.md → race(full) → location(full) → character(--skeleton) → skill → item → equip-fill → quest → chapter → meta → sweep. Release publish는 별도 `agency.story.tools.storage upload` 단계다.

시나리오 작성자(Codex)가 각 단계에서 `check-entity --decomp .decomp/` 로 자기 글을 검증. 풀-의존 검사(character의 inventory) 는 `--skeleton` 으로 sweep까지 미룸.

검사 깨졌을 때: 같은 파일 2회까지만 자동 수정, 그 이상은 사용자에게 보고. 위쪽 단계 실수가 늦게 드러나면 `.decomp/` JSON부터 고치고 영향받는 파일 재검사 — 가짜 ID 같은 우회는 금지.

기존 LLM 호출 루프(`runner.write_entity`, `decompose._decompose_phase`, `critic.run_critic`)와 LLM 전용 프롬프트 (`agents/*.md`)는 모두 제거됨. `harness/decompose.py` 의 Pydantic 모델 + `_check_*` 함수, `harness/runner.py`의 cross-ref 검사 + SPECS, `harness/scenario.py`의 `fill_equipment` 만 남아 `tool.py`가 쓰는 헬퍼다.

### Boundary

Scenario files are raw seed records. Cross-ref checks and the final sweep use `server/src/game/seed/validation.py`; runtime behavior starts after those records are converted into the graph seed.

QA's loop intentionally stops on the first error — do not "retry past it." The transcript should reflect what actually happened, including the failure point.

## Cross-cutting conventions

- **Korean only for everything user-facing.** Persona prompts (`qa/agents/*.md`), the story SKILL (`story/SKILL.md`), and any string that ends up in a transcript or scenario file are Korean. Engine-side narration uses **2인칭 존댓말 합니다체** — `당신` for the player, `~합니다 / ~ㅂ니다 / ~입니다` endings — and the user-facing skill term is **기술** (`스킬` survives only as a synonym in the classify prompt). Code text (Python source, exception messages, validation errors) stays English.
- **Comments minimal, English-only.** Default to no comment — add one only when the *why* is non-obvious. Single short line. Korean is allowed inside an English comment only when quoting an in-game string the comment is reasoning about. No multi-paragraph docstrings, no multi-line `# ...` blocks. `# noqa` / `# type:` / shebangs aren't comments.
- **env is fail-fast.** `os.environ["BASE_URL"]` etc., never `os.environ.get(..., default)`. Missing keys must raise at startup, not later inside an LLM call.
- **Save-directory isolation.** QA always writes to `qa_test/agency/<agent>/saves/` via `LocalFsGraphRepo`. Never repoint at production Supabase graph tables. Scenarios are read from local `SCENARIO_DIR`.
