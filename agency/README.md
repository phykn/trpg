# Agency — LLM 사무실

게임 운영을 돕는 LLM 직원들이 팀 단위로 일하는 곳. 각 팀은 자기 디렉터리 안에 agent prompt, harness, 실행 결과를 들고 있고 백엔드 API 를 두드려 일한다. 현재는 **QA 팀** 만 입주해 있고, 앞으로 **스토리 팀** 이 합류할 예정.

```
agency/
  qa/       # 게임을 플레이해보고 회귀를 잡는 검수팀
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
