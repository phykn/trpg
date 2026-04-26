# CLAUDE.md

`agency/` 에서 일할 때 참고. 사용 가이드는 [README.md](./README.md).

## 위치

- `agency/qa/` — AI 플레이어 기반 게임 테스트 팀.
- `agency/story/` — 시나리오 시드 작성 팀. 출력은 repo 루트의 `scenarios/<name>/`.
- 새 팀은 같은 layout (`agents/` + `harness/` + `runs/` + `run_*.py`) 으로 옆에 추가.

`agency` 자체는 backend 의 in-process consumer 다. `backend/src/...` 와 `backend/run_api.py` 를 직접 import 하므로 백엔드 코드를 수정하는 PR 에서 import 경로·시그니처가 깨지지 않았는지 같이 확인.

## 실행 환경

- 파이썬 venv 는 repo 루트의 `.venv` 를 그대로 씀. agency 전용 venv 없음.
- `backend/.env` 를 `run_qa.py` 가 자동 로드. agency 디렉터리에 따로 `.env` 두지 않음.
- `BASE_URL` 만 있으면 동작. `BASIC_AUTH_USER` / `PASS` 는 in-process 호출이라 harness 가 임의 값 (`"qa"` / `"qa"`) 으로 덮어씀.

## 컨벤션

### Korean-only

agent prompt (`agents/*.md`), reviewer 출력, transcript, README — 모두 한국어. 백엔드와 같은 규칙.

### Harness 가 production save 를 건드리지 않게

QA 의 각 run 은 `runs/<timestamp>/<agent>/saves/` 를 자체 `SAVES_DIR` 로 사용. 절대 `../saves/` (repo 루트) 를 가리키도록 바꾸지 말 것 — 진행 중인 게임이 덮어쓰일 수 있음.

### Story 팀은 production 시나리오를 직접 쓴다

QA 와 달리 story 팀은 `scenarios/<scenario>/` (PROFILE_DIR 가 가리키는 곳) 에 결과 파일을 바로 떨군다 — 다음 새 게임이 그 시드를 그대로 쓰는 게 목적이므로. 단 같은 `id.json` 이 이미 있으면 덮어쓰지 않고 에러로 멈춘다 (`harness/runner.py` 의 `write_race_to_disk`). LLM 주고받음 로그는 `agency/story/runs/<ts>/<agent>/` 에 따로 보존.

### Story 팀은 두 트랙을 가짐

같은 prompt 규칙을 두 진입점이 공유:

- `agency/story/run_story.py <kind> --scenario <s>` — 로컬 LLM (BASE_URL) 호출. 자동화·반복용. `harness/runner.py` 의 generic `write_entity` 가 자기교정 5회 + 참조 무결성 검증.
- `/story-write <kind> <s> [hint]` — `.claude/commands/story-write.md`. Claude Code 가 `_base.md` + `<kind>.md` + 시나리오 컨텍스트를 직접 Read 하고 결과 파일 Write. 한 번 더 똑똑하게 짓고 싶을 때.

`<kind>` ∈ `{race, location, item, character, quest, chapter}`.

### Fragment 추가법

새 entity 종류 (현재 6 외에) 를 늘리려면:

1. `agency/story/agents/<kind>.md` — 스키마·필수 필드·참조 규칙. 다른 fragment 와 비슷한 길이 (1-2 화면).
2. `agency/story/harness/runner.py` 의 `SPECS` 에 한 줄 (model · sub_dir · fragment · ref_kinds · check_refs).
3. 참조 검증 함수가 새로 필요하면 `_check_<kind>_refs` 작성. 단순 id 충돌·패턴은 generic 이 챙김.
4. `_base.md` 는 entity 무관 공통 규칙 (한국어 강제, JSON-only, id 패턴, id 강제 hint 따르기) — 여기 손 댈 필요 없음.

CLI subparser 와 슬래시 커맨드는 `SPECS` 만 갱신하면 자동으로 새 kind 노출.

규칙이 어긋나면 두 트랙 모두 같이 갱신. 한쪽만 고치면 같은 시나리오에 톤 다른 entity 가 들어가게 됨.

### Scenario mode 의 id 강제

`run_story.py scenario --name <new>` (또는 `/story-scenario`) 는 분해 단계에서 미리 정한 id 들을 entity 단계가 정확히 따라야 한다. `write_entity(force_id=X)` 가 `_check_id` 안에서 LLM 응답의 id 와 비교, 다르면 `EntityWriterError` 를 자기교정 루프에 던져 다음 시도에 교정시킴. 분해와 entity 단계가 id 가 갈리면 cross-reference (start_location_id / quest target_id / chapter quest_ids) 가 다 깨지기 때문. 단순 entity (`/story-write race ...`) 는 force_id 없이 LLM 자유 — 그럴 땐 id 충돌만 검증.

### Scenario sources 위치

줄글 입력은 `agency/story/sources/<name>.md` 에 보관. story 팀이 실험할 줄글이 누적되는 곳. 시나리오 디렉터리 이름과 같은 이름 (`default.md` → `scenarios/default_cli/`, `default_claude/`) 으로 가는 게 비교에 편함.

### 새 agent 추가

1. `agency/qa/agents/<name>.md` — system prompt 한 장. 어떤 성향인지 / 무엇을 위주로 할지 명시.
2. `agency/qa/run_qa.py` 의 `AGENTS` 리스트에 이름 추가.

prompt 는 `PlayerAgent` 가 그대로 system 으로 넣고, user 메시지로 매 턴 `state_summary` + `last_gm` + `최근 흐름` 을 붙여 호출한다 (`harness/agent.py`).

### 새 팀 추가

`agency/<team>/` 아래에 `agents/` + `harness/` + `runs/` + `run_*.py` 동일 layout 으로 만든다. backend FastAPI app 이 필요하면 in-process 호출 패턴 (`build_app` + `httpx.ASGITransport`) 재사용 (QA 식). 시드만 만든다면 `LLMClient` + Pydantic 모델 검증만으로 충분 (story 식). `runs/` 는 `agency/.gitignore` 에 추가.

### Reviewer verdict 스키마는 깨면 안 됨

`harness/review.py` 의 `Verdict` Pydantic 모델은 외부 도구 (index.md 생성, 향후 dashboard) 가 의존. 필드 추가는 OK, 기존 필드 이름·타입 변경은 별도 마이그레이션 PR.

## 한계 / 주의

- LLM 호출량이 크다. 빠른 피드백용으로 짧게 돌리는 게 기본.
- 비결정적. 회귀를 정밀하게 잡으려면 시나리오 모드 (입력 시퀀스 명시) 필요 — 아직 미구현.
- `runs/` 에 누적된 결과는 git 에 안 들어감. 보관·비교가 필요하면 별도 폴더로 옮길 것.
