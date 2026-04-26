# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

레포 루트 가이드. 작업하려는 디렉터리에 진입한 뒤 그쪽 `CLAUDE.md` 도 같이 본다.

## Layout

한국어 TRPG. 셋이 한 묶음:

- `backend/` — FastAPI + Pydantic v2 + OpenAI 호환 LLM. 게임 엔진. 자세한 가이드는 [backend/CLAUDE.md](./backend/CLAUDE.md).
- `frontend/` — Expo (RN 0.81 / React 19) 단일 화면 앱. SSE 로 백엔드와 스트리밍. [frontend/CLAUDE.md](./frontend/CLAUDE.md).
- `agency/` — 백엔드를 in-process 로 호출하는 LLM 에이전트 사무실. 현재는 QA 팀만. [agency/CLAUDE.md](./agency/CLAUDE.md).
- `docs/` — 북극성 설계 노트 5장 (`01-overview` / `02-runtime` / `03-features` / `04-boundary` / `05-codemap`). 인덱스는 `docs/01-overview.md`.
- `saves/` — gitignored. 게임당 디렉터리 (`games/<game_id>/...` + `.current`).

venv·pyproject·requirements 는 루트 한 벌. 모든 파이썬 코드 (backend, agency, tests) 가 같은 `.venv/` 를 공유.

## Commands

```bash
# 루트에서
.venv/bin/python -m pytest -q                     # unit (live 스킵). pyproject 의 testpaths=backend/tests
RUN_LIVE=1 .venv/bin/python -m pytest -q          # LLM 살아 있을 때만 (BASE_URL 도달 가능해야 함)

# 단일 테스트
.venv/bin/python -m pytest backend/tests/test_apply.py::test_name -q

# backend 서버 (cwd 가 backend 여야 dotenv 가 backend/.env 를 잡음)
cd backend && ../.venv/bin/python run_api.py

# QA 에이전트 한 바퀴
.venv/bin/python agency/qa/run_qa.py --agent diplomat --turns 20

# frontend (별도 venv 무관, npm)
cd frontend && npx expo start
```

## Cross-cutting conventions

레포 전역으로 적용. 하위 CLAUDE.md 가 같은 규칙을 반복하면 그쪽이 더 자세할 뿐 충돌은 아님.

- **한국어 단일.** 사용자에게 도달하는 모든 텍스트 (LLM prompt, 로그, NPC 대사, 에러 메시지, agent prompt, reviewer 출력) 는 한국어. localization layer 없음. 옛 `LocalizedText{ko,en}` 폐기.
- **env 는 fail-fast.** `??` 기본값 / silent default 금지. 누락 시 startup 에서 throw. `backend/.env` 와 `frontend/.env` 둘 다.
- **표시 데이터는 백엔드가 만들어서 보냄.** 한국어 날짜·기간·합성 문자열·조건부 라벨 등 변환은 `backend/src/mapping/to_front.py` 한 곳에서 끝내고, 프론트는 그대로 표시. 프론트 타입은 UI 가 렌더하는 필드만 담는다.
- **LLM agent retry = 5회 자기교정 루프.** judge / narrate 등은 `ValidationError` / 의미 검증 실패 시 직전 응답+에러를 message stream 에 append → 다음 시도가 스스로 교정. 5회 후 마지막 에러 종류로 raise.
- **Stats key = ASCII 약어** (`STR/DEX/CON/INT/WIS/CHA`). judge stat enum 도 같은 키.
- **save 디렉터리 격리.** production save 는 루트의 `saves/`. agency QA run 은 `agency/qa/runs/<ts>/<agent>/saves/` 자체 분리 — 절대 `../saves/` 가리키게 바꾸지 말 것.

## Stack

- Python 3.12+, Pydantic v2, FastAPI, async/await throughout, uvicorn.
- OpenAI 호환 LLM 서버를 `BASE_URL` 로 지정 (현재 llama.cpp).
- 단일 프로세스 + `asyncio.Lock` 으로 파일 쓰기 직렬화. DB 없음 — 게임 상태는 entity 별 JSON + append-only JSONL.
- Expo SDK 54 / RN 0.81 / React 19, NativeWind v4, expo-router typedRoutes, `expo/fetch` 로 SSE 스트리밍 (표준 fetch 는 RN 에서 SSE body streaming 미지원).
