# CLAUDE.md

`agency/` 에서 일할 때 참고. 사용 가이드는 [README.md](./README.md).

## 위치

- `agency/qa/` — AI 플레이어 기반 게임 테스트 팀. 현재 입주 중인 유일한 팀.
- 다른 팀 (스토리 등) 은 같은 layout (`agents/` + `harness/` + `runs/` + `run_*.py`) 으로 옆에 추가될 예정.

`agency` 자체는 backend 의 in-process consumer 다. `backend/src/...` 와 `backend/run_api.py` 를 직접 import 하므로 백엔드 코드를 수정하는 PR 에서 import 경로·시그니처가 깨지지 않았는지 같이 확인.

## 실행 환경

- 파이썬 venv 는 repo 루트의 `.venv` 를 그대로 씀. agency 전용 venv 없음.
- `backend/.env` 를 `run_qa.py` 가 자동 로드. agency 디렉터리에 따로 `.env` 두지 않음.
- `BASE_URL` 만 있으면 동작. `BASIC_AUTH_USER` / `PASS` 는 in-process 호출이라 harness 가 임의 값 (`"qa"` / `"qa"`) 으로 덮어씀.

## 컨벤션

### Korean-only

agent prompt (`agents/*.md`), reviewer 출력, transcript, README — 모두 한국어. 백엔드와 같은 규칙.

### Harness 가 production save 를 건드리지 않게

각 run 은 `runs/<timestamp>/<agent>/saves/` 를 자체 `SAVES_DIR` 로 사용. 절대 `../saves/` (repo 루트) 를 가리키도록 바꾸지 말 것 — 진행 중인 게임이 덮어쓰일 수 있음.

### 새 agent 추가

1. `agency/qa/agents/<name>.md` — system prompt 한 장. 어떤 성향인지 / 무엇을 위주로 할지 명시.
2. `agency/qa/run_qa.py` 의 `AGENTS` 리스트에 이름 추가.

prompt 는 `PlayerAgent` 가 그대로 system 으로 넣고, user 메시지로 매 턴 `state_summary` + `last_gm` + `최근 흐름` 을 붙여 호출한다 (`harness/agent.py`).

### 새 팀 추가

`agency/<team>/` 아래에 `agents/` + `harness/` + `runs/` + `run_*.py` 동일 layout 으로 만든다. backend FastAPI app 을 in-process 로 부르는 패턴 (`build_app` + `httpx.ASGITransport`) 은 재사용. `runs/` 는 `.gitignore` 에 추가.

### Reviewer verdict 스키마는 깨면 안 됨

`harness/review.py` 의 `Verdict` Pydantic 모델은 외부 도구 (index.md 생성, 향후 dashboard) 가 의존. 필드 추가는 OK, 기존 필드 이름·타입 변경은 별도 마이그레이션 PR.

## 한계 / 주의

- LLM 호출량이 크다. 빠른 피드백용으로 짧게 돌리는 게 기본.
- 비결정적. 회귀를 정밀하게 잡으려면 시나리오 모드 (입력 시퀀스 명시) 필요 — 아직 미구현.
- `runs/` 에 누적된 결과는 git 에 안 들어감. 보관·비교가 필요하면 별도 폴더로 옮길 것.
