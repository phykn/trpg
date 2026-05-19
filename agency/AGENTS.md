# AGENTS.md

This file provides guidance to Codex (Codex.ai/code) when working with code in this repository.

User-facing setup and the full directory map live in [README.md](./README.md). This file covers what's not derivable from a quick read of the source.

## Working tree

`agency/` is a Python package that imports the server's `src.*` directly for story tooling. The venv, `pyproject.toml`, and `requirements.txt` live at the repo root — invoke Python via `.venv/bin/python` from the repo root. **Never create `agency/.venv`.**

## Commands

```bash
# Browser QA — invoke from a Codex session, no CLI:
#   "agency/qa/SKILL.md 보고 열린 브라우저에서 QA 해줘"
#
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

Browser QA uses the already-running web client and server. Story tool (`tool.py`) is local-only. Release storage publish/download lives in `agency.story.tools.storage` and needs `APP_ENV=release` + Supabase keys.

## Architecture

### QA — browser skill only

`agency/qa/SKILL.md` is for exploratory browser QA. Codex uses the visible web client, plays through the real UI, and writes improvement findings with turn-numbered evidence. Do not replace browser observations with direct API calls. Save reports under `qa_test/browser/<run-id>/report.md` when a persistent report is useful.

### Story — SKILL.md driven scenario build

`agency/story/SKILL.md`는 Codex 세션이 산문(prose) 한 편으로 시나리오 디렉토리 한 개를 빌드하기 위한 절차서다. 외부 LLM 호출 없음 — Codex 자체가 작성자다.

`tool.py`는 로컬 검증·자동채우기를 모은 단일 CLI. SKILL.md가 각 단계에서 호출한다. 종료 코드 0(OK)/1(검증 실패)/2(usage 오류) + 사람이 읽을 수 있는 stderr 메시지.

빌드 흐름: decompose 3-phase → world.md → race(full) → location(full) → character(--skeleton) → skill → item → equip-fill → quest → chapter → meta → sweep. Release publish는 별도 `agency.story.tools.storage upload` 단계다.

시나리오 작성자(Codex)가 각 단계에서 `check-entity --decomp .decomp/` 로 자기 글을 검증. 풀-의존 검사(character의 inventory) 는 `--skeleton` 으로 sweep까지 미룸.

검사 깨졌을 때: 같은 파일 2회까지만 자동 수정, 그 이상은 사용자에게 보고. 위쪽 단계 실수가 늦게 드러나면 `.decomp/` JSON부터 고치고 영향받는 파일 재검사 — 가짜 ID 같은 우회는 금지.

기존 LLM 호출 루프(`runner.write_entity`, `decompose._decompose_phase`, `critic.run_critic`)와 LLM 전용 프롬프트 (`agents/*.md`)는 모두 제거됨. `harness/decompose.py` 의 Pydantic 모델 + `_check_*` 함수, `harness/runner.py`의 cross-ref 검사 + SPECS, `harness/scenario.py`의 `fill_equipment` 만 남아 `tool.py`가 쓰는 헬퍼다.

### Boundary

Scenario files are raw seed records. Cross-ref checks and the final sweep use `server/src/game/seed/validation.py`; runtime behavior starts after those records are converted into the graph seed.

Browser QA should reflect what actually happened in the UI, including the failure point.

## Cross-cutting conventions

- **Korean only for everything user-facing.** The QA skill (`qa/SKILL.md`), story skill (`story/SKILL.md`), and any string that ends up in a report or scenario file are Korean. Engine-side narration uses **2인칭 존댓말 합니다체** — `당신` for the player, `~합니다 / ~ㅂ니다 / ~입니다` endings — and the user-facing skill term is **기술** (`스킬` survives only as a synonym in the classify prompt). Code text (Python source, exception messages, validation errors) stays English.
- **Comments minimal, English-only.** Default to no comment — add one only when the *why* is non-obvious. Single short line. Korean is allowed inside an English comment only when quoting an in-game string the comment is reasoning about. No multi-paragraph docstrings, no multi-line `# ...` blocks. `# noqa` / `# type:` / shebangs aren't comments.
- **env is fail-fast.** Required keys should be read through strict env/profile parsing, never `os.environ.get(..., default)`. Missing keys must raise at startup, not later inside an LLM call.
