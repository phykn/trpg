# trpg

한국어 TRPG. LLM 이 이야기·난이도 판정을 맡고, 엔진이 상태·규칙·시간을 다룬다.

```
trpg/
  backend/    FastAPI + Pydantic v2 + OpenAI 호환 LLM. 게임 엔진. → backend/README.md
  frontend/   Expo (React Native) 단일 화면 클라이언트. → frontend/README.md
  agency/     백엔드를 in-process 호출하는 LLM 직원 사무실 (현재 QA 팀). → agency/README.md
  docs/       설계 노트 (01-overview / 02-runtime / 03-features / 04-boundary / 05-codemap)
  saves/      런타임 게임 저장소 (gitignored)
```

자세한 셋업·실행은 각 하위 README, 설계 의도는 `docs/01-overview.md` 부터.

## 빠른 시작

LLM 서버 (예: llama.cpp) 가 어딘가에서 돌고 있어야 함.

```bash
# 루트에서 (한 번만)
python3.12 -m venv .venv
.venv/bin/pip install -r requirements.txt

# backend/.env 작성 후
cd backend && ../.venv/bin/python run_api.py

# 다른 터미널에서, frontend/.env 작성 후
cd frontend && npm install && npx expo start
```

env 변수는 fail-fast — 누락 시 즉시 throw. 사양은 각 하위 README.

## 테스트

```bash
# 루트에서
.venv/bin/python -m pytest -q                  # unit
RUN_LIVE=1 .venv/bin/python -m pytest -q       # LLM 도달 가능할 때만
```

## 스택

Python 3.12+ · Pydantic v2 · FastAPI · async/await · OpenAI 호환 LLM · Expo SDK 54 / RN 0.81 / React 19 · NativeWind v4 · expo-router. DB 없음 — 게임 상태는 entity 별 JSON + append-only JSONL (`saves/games/<game_id>/`).
