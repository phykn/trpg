# trpg-backend

한국어 TRPG 엔진. FastAPI + Pydantic v2 + OpenAI 호환 LLM. 한 게임은 한 디렉터리 (`saves/games/<id>/`) 에 흩뿌린 JSON + JSONL 로 저장.

설계 노트는 `../docs/01-overview.md`, 한 턴 내부 흐름은 `../docs/02-runtime.md`, 모듈 지도는 `../docs/05-codemap.md`. Claude Code 가이드는 [CLAUDE.md](./CLAUDE.md).

## 스택

- Python 3.12+, Pydantic v2, FastAPI, uvicorn, httpx, async/await
- OpenAI 호환 LLM 서버 (예: llama.cpp) 를 `BASE_URL` 로 가리킴
- 게임 상태는 파일 한 묶음 (`SAVES_DIR/games/<game_id>/`). DB 없음.
- 단일 프로세스 (`asyncio.Lock` 으로 저장 직렬화)

## 셋업

venv·`pyproject.toml`·`requirements.txt` 는 repo 루트. 루트에서 한 번만:

```bash
python3.12 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

`backend/.env` 작성 (필수, fallback 없음 — 누락 시 시작에서 KeyError):

```
HOST=0.0.0.0
PORT=8001
BASE_URL=http://localhost:8000/v1        # llama.cpp 등 OpenAI 호환 서버
BASIC_AUTH_USER=<id>
BASIC_AUTH_PASS=<pass>
SAVES_DIR=../saves                       # repo 루트 peer 디렉터리
PROFILE_DIR=../scenarios                 # repo 루트 peer 디렉터리
```

LLM 서버는 별도로 띄워야 함. 예: `llama-server -m <model.gguf> -c 8192 --port 8000`.

## 실행

```bash
# backend/ 에서 (cwd 가 backend 여야 dotenv·상대경로가 맞음)
../.venv/bin/python run_api.py
```

dotenv 가 자동으로 `backend/.env` 를 로드하고 uvicorn 이 `HOST:PORT` 에 바인딩.

### 라우트 (Basic Auth 필요)

| Method | Path | 용도 |
|---|---|---|
| GET  | `/health` | 헬스체크 (인증 불필요) |
| GET  | `/profiles` | 시나리오 + 종족 카드 목록 |
| GET  | `/session/current` | 마지막 game_id 의 FrontState (없으면 404) |
| POST | `/session/init` | 새 게임 (profile + player) |
| GET  | `/session/{id}/state` | FrontState 조회 |
| POST | `/session/{id}/turn` | 한 턴 (SSE) |
| POST | `/session/{id}/roll` | pending_check 굴림 (SSE) |
| POST | `/session/{id}/intro` | GM 인트로 생성 (SSE, init 직후 1회) |
| POST | `/debug/complete` | LLM 디버그용 단발 호출 |

SSE 이벤트: `judge / pending_check / narrative_delta / log_entry / state / done / error`. 자세한 모양은 `../docs/02-runtime.md` §2.4.

## 테스트

```bash
# repo 루트에서 (pyproject 의 testpaths=backend/tests 가 잡아줌)
.venv/bin/python -m pytest -q                   # unit (live 스킵)
RUN_LIVE=1 .venv/bin/python -m pytest -q        # LLM 살아 있어야 함
```

`pytest-asyncio` 자동 모드. `live` 마커가 붙은 테스트는 `RUN_LIVE=1` 일 때만 실행 (`BASE_URL` 도달 가능해야 함).

## 디렉터리

```
backend/
  run_api.py                       # 진입점
  .env                             # 필수, gitignored
  src/                             # 코드 (계층은 docs/05-codemap.md 참고)
  tests/                           # pytest
  scripts/                         # 일회용 도구 (judge_stress 등)
../scenarios/<profile>/            # 시나리오 시드 (world.md, start.json, races/, locations/, characters/, items/, quests/, chapters/, player_template.json). repo 루트 peer
../saves/                          # 런타임 저장소 (gitignored)
  .current                           # 마지막 game_id 한 줄
  games/<game_id>/
    meta.json                        # 싱글톤 필드 (player_id, world_time, pending_check, ...)
    characters/<id>.json             # 엔티티별 한 파일
    items/<id>.json
    locations/<id>.json
    races/<id>.json                  # ...
    log.jsonl                        # append-only 로그
    history.jsonl                    # append-only 턴 요약
    dialogue.jsonl                   # append-only 대사
```

원자적 쓰기 (`.tmp` → `os.replace`) + `asyncio.Lock` 으로 동시 쓰기 차단.
