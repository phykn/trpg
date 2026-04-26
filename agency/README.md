# Agency — LLM 사무실

게임 운영을 돕는 LLM 직원들이 팀 단위로 일하는 곳. 각 팀은 자기 디렉터리 안에 agent prompt, harness, 실행 결과를 들고 있다.

```
agency/
  qa/       # 게임을 플레이해보고 회귀를 잡는 검수팀
  story/    # 시나리오 시드 (race / character / ... ) 를 새로 짓는 작가팀
```

## QA — AI 플레이어 기반 게임 테스트

게임 QA 를 고용해서 플레이시키는 식으로 동작. 매 턴마다 LLM 이 다음 입력을 생성, 백엔드 API 를 두드리고 SSE 응답을 transcript 로 모은 뒤, 별도의 reviewer LLM 이 transcript 를 분석해 verdict 를 낸다.

### 구조

```
agency/qa/
  agents/
    diplomat.md       # 사교가 — NPC 친밀도·대화 중심
    explorer.md       # 탐험가 — 이동·관찰·인벤토리 중심
    provocateur.md    # 도발자 — 엣지 케이스·judge 분기 트리거
    reviewer.md       # 분석가 — transcript 읽고 verdict JSON 생성
  harness/
    agent.py          # PlayerAgent — system prompt + 매 턴 LLM 호출
    transcript.py     # SSE / state → markdown / jsonl
    review.py         # reviewer 호출 + Verdict 검증
    runner.py         # 단일 agent 의 한 세션 실행
  runs/               # gitignored, 실행 결과
  run_qa.py           # CLI 엔트리
```

### 동작 원리

- `httpx.AsyncClient(transport=ASGITransport(app))` 로 FastAPI app 을 in-process 호출. 포트·프로세스 없이 HTTP 표면 (auth/SSE/error) 그대로 통과.
- LLM 은 외부 서버 (`BASE_URL`, e.g. llama.cpp) 그대로 사용.
- 각 run 은 자체 `saves/` 디렉터리를 사용 (격리). production save 와 안 섞임.
- 한 세션 흐름: `POST /session/init` → `POST /session/{id}/intro` (선택) → `(state 조회 → agent 가 다음 입력 결정 → POST /turn → pending_check 면 자동 POST /roll)` 반복.

### 실행

```bash
# 모든 agent 한 번씩 (기본 15턴)
.venv/bin/python agency/qa/run_qa.py

# 특정 agent
.venv/bin/python agency/qa/run_qa.py --agent diplomat --turns 20

# 다른 프로필
.venv/bin/python agency/qa/run_qa.py --agent all --profile other_world
```

`.env` 는 `backend/.env` 를 자동 로드. `BASE_URL` 만 살아 있으면 됨.

### 출력

```
agency/qa/runs/<timestamp>/
  index.md                      # agent 비교 요약표 + high/medium 이슈 추출
  diplomat/
    transcript.md               # 사람-읽기용 턴별 기록
    sse.jsonl                   # raw SSE 이벤트 (재현·디버깅용)
    final_state.json            # 끝난 시점의 GameState 전체
    verdict.json                # 구조화된 평가 (코드 고칠 때 활용)
    review.md                   # reviewer 의 사람-읽기용 코멘트
    saves/                      # run 격리용 임시 save (재실행 시 새 디렉터리)
  explorer/...
  provocateur/...
```

`verdict.json` 스키마:

```json
{
  "agent": "diplomat",
  "run_id": "...",
  "verdict": "pass" | "warn" | "fail",
  "wins": ["..."],
  "issues": [
    {
      "severity": "low" | "medium" | "high",
      "category": "narrative" | "state" | "judge" | "memory" | "input" | "schema" | "기타",
      "summary": "...",
      "evidence": ["턴 N: ..."]
    }
  ],
  "questions": ["..."]
}
```

### 코드 수정에 활용

새 변경 후 `run_qa.py` 한 번 돌려서 `index.md` 의 high/medium 이슈와 `verdict.json` 들을 확인. 회귀가 발견되면 evidence 에 적힌 턴 번호로 transcript 의 해당 부분을 보고 디버깅. 잘 동작하던 부분 (`wins`) 이 사라졌다면 회귀 신호.

### 한계

- 실시간 가이드 역할이지 단정적 검수는 아님. reviewer LLM 의 판단도 검토 대상.
- LLM 호출량이 많음 (turn 당 narrator 1 + player 1 + 마지막에 reviewer 1). 짧게 돌려서 빠르게 피드백 받는 식이 적합.
- 비결정적. 같은 프롬프트라도 매번 다른 transcript. 회귀를 정밀하게 잡으려면 시나리오 모드 (입력 시퀀스 명시) 가 필요 — 추후 추가 가능.

## Story — 시나리오 시드 작성

repo 루트의 `scenarios/<name>/` 에 들어가는 시드 파일 (race, character, location, ...) 을 LLM 이 짓는 팀. 첫 단계는 race 한 개부터.

### 구조

```
agency/story/
  agents/
    race_writer.md           # 새 종족 한 개 작성하는 작가
  harness/
    runner.py                # LLM 호출 + Pydantic 검증 + 자기교정 루프 (5회) + 디스크 쓰기
  runs/                      # gitignored — 매 호출의 prompt·응답 로그
  run_story.py               # CLI
```

### 동작 원리

- backend 의 `LLMClient` 와 `domain/entities.py` 의 `Race` Pydantic 모델을 그대로 import.
- 호출당 한 사이클: scenario 의 `world.md` + 기존 `races/*.json` 을 system 컨텍스트로 묶어 LLM 호출 → JSON 추출 → `Race.model_validate_json` + 추가 의미 검증 (`id` 가 ASCII snake_case 이고 기존과 안 겹침) → 실패 시 응답+에러를 messages 에 append → 최대 5회 재시도 (judge runner 와 같은 패턴).
- 검증 통과 시 `scenarios/<scenario>/races/<id>.json` 에 `indent=2` 로 저장. 같은 파일이 이미 있으면 덮어쓰지 않고 에러.
- 모든 messages 는 `agency/story/runs/<ts>/race_writer/messages.jsonl` 에 보존 (디버깅용).

### 실행

```bash
.venv/bin/python agency/story/run_story.py race --scenario default --hint "달밤에만 활동하는 종족"

# 힌트 없이 LLM 자체 판단
.venv/bin/python agency/story/run_story.py race --scenario default
```

`backend/.env` 의 `BASE_URL` 만 살아 있으면 됨 (in-process consumer).

### 한계

- 한 번에 entity 한 개. race 외 (character / location / quest / chapter / 시나리오 한 벌) 는 후속.
- `racial_skills` 는 항상 빈 리스트로 만든다 (기존 races 가 다 비어 있어서). skill 합성은 별도 단계.
- 시나리오 디렉터리 자체를 새로 만드는 모드 없음 (기존 `<scenario>/` 안에 추가만).
