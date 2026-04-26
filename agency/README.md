# Agency — LLM 사무실

게임 운영을 돕는 LLM 직원들이 팀 단위로 일하는 곳. 각 팀은 자기 디렉터리 안에 agent prompt, harness, 실행 결과를 들고 있다.

```
agency/
  run_qa.py     # QA 팀 CLI 엔트리
  run_story.py  # Story 팀 CLI 엔트리
  qa/           # 게임을 플레이해보고 회귀를 잡는 검수팀
  story/        # 시나리오 시드 (race / character / ...) 를 새로 짓는 작가팀
```

## QA — AI 플레이어 기반 게임 테스트

게임 QA 를 고용해서 플레이시키는 식으로 동작. 매 턴마다 LLM 이 다음 입력을 생성, 백엔드 API 를 두드리고 SSE 응답을 transcript 로 모은 뒤, 별도의 reviewer LLM 이 transcript 를 분석해 verdict 를 낸다.

### 구조

```
agency/run_qa.py        # CLI 엔트리
agency/qa/
  agents/
    diplomat.md         # 사교가 — NPC 친밀도·대화 중심
    explorer.md         # 탐험가 — 이동·관찰·인벤토리 중심
    provocateur.md      # 도발자 — 엣지 케이스·judge 분기 트리거
    reviewer.md         # 분석가 — transcript 읽고 verdict JSON 생성
  harness/
    agent.py            # PlayerAgent — system prompt + 매 턴 LLM 호출
    state_view.py       # front_state → player-LLM 입력 텍스트
    transcript.py       # SSE → markdown / jsonl
    review.py           # reviewer 호출 + Verdict 검증
    runner.py           # 단일 agent 의 한 세션 실행

# 실행 결과는 repo 루트의 reports/qa/<timestamp>/ 에 떨어짐 (gitignored)
```

### 동작 원리

- `httpx.AsyncClient(transport=ASGITransport(app))` 로 FastAPI app 을 in-process 호출. 포트·프로세스 없이 HTTP 표면 (auth/SSE/error) 그대로 통과.
- LLM 은 외부 서버 (`BASE_URL`, e.g. llama.cpp) 그대로 사용.
- 각 run 은 자체 `saves/` 디렉터리를 사용 (격리). production save 와 안 섞임.
- 한 세션 흐름: `POST /session/init` → `POST /session/{id}/intro` (선택) → `(state 조회 → agent 가 다음 입력 결정 → POST /turn → pending_check 면 자동 POST /roll)` 반복.

### 실행

```bash
# 모든 agent 한 번씩 (기본 15턴)
.venv/bin/python agency/run_qa.py

# 특정 agent
.venv/bin/python agency/run_qa.py --agent diplomat --turns 20

# 다른 프로필
.venv/bin/python agency/run_qa.py --agent all --profile other_world
```

`.env` 는 `backend/.env` 를 자동 로드. `BASE_URL` 만 살아 있으면 됨.

### 출력

```
reports/qa/<timestamp>/
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

repo 루트의 `scenarios/<name>/` 에 들어가는 시드 파일을 LLM 이 짓는 팀. 현재는 entity 한 종류씩 단발 추가 (race / location / item / character / quest / chapter). 시나리오 한 벌 (줄글 → 디렉터리 통째) 은 후속 단계.

### 구조

```
agency/run_story.py    # CLI (entity / scenario subcommand)
agency/story/
  agents/
    _base.md           # 모든 fragment 위에 얹는 공통 규칙 (한국어, JSON-only, id 패턴)
    _decompose.md      # 줄글 → Decomposition 분해 prompt
    race.md            # entity 별 도메인 규칙 (스키마·필수 필드·참조)
    location.md
    item.md
    character.md
    quest.md
    chapter.md
  harness/
    runner.py          # generic write_entity(kind, ...) — LLM + Pydantic + 자기교정 5회 + 의미 검증 + 디스크 쓰기
    scenario.py        # 줄글 한 편 → 시나리오 한 벌 빌드 파이프라인

# 매 호출의 prompt·응답 로그는 repo 루트의 reports/story/<ts>/<kind>_writer/ 에 떨어짐 (gitignored)
```

### 동작 원리

- backend 의 `LLMClient` 와 `domain/entities.py` 의 Pydantic 모델을 그대로 import.
- `SPECS` 에 entity 종류별 (model · sub_dir · fragment · 참조 종류 · 의미 검증 함수) 매핑.
- 호출당 한 사이클: `_base.md` + `<kind>.md` + scenario 의 `world.md` + 그 종류의 기존 instances + 참조 종류의 기존 instances 를 system 컨텍스트로 묶어 LLM 호출 → JSON 추출 → `<Model>.model_validate_json` + id 패턴 검증 + entity 별 참조 무결성 검증 (예: `character.race_id` 가 시나리오 `races/` 에 실재) → 실패 시 응답+에러를 messages 에 append → 최대 5회 자기교정 (judge runner 와 같은 패턴).
- 검증 통과 시 `scenarios/<scenario>/<sub_dir>/<id>.json` 에 `indent=2` 로 저장. 같은 파일이 이미 있으면 덮어쓰지 않고 에러.
- 모든 messages 는 `reports/story/<ts>/<kind>_writer/messages.jsonl` 에 보존 (디버깅용).

### 참조 무결성

각 entity 의 의미 검증이 챙기는 ID 참조:

| Kind | 검증되는 참조 |
|---|---|
| race | (없음) |
| location | `connections[*].target_id` → 시나리오의 다른 location id (자기 자신 금지) |
| item | (없음 — `required: Stats` 는 Pydantic 자동) |
| character | `race_id` → races, `location_id` → locations, `inventory_ids[*]` → items, `equipment.<slot>` → items |
| quest | `giver_id` → characters, `triggers[*].target_id` → type 따라 (character_death→characters, location_enter→locations, item_use→items), `prerequisite_ids[*]` → quests |
| chapter | `quest_ids[*]` → quests |

### 실행

두 트랙 — 자동화는 로컬 LLM, 한 번 똑똑하게 짓고 싶을 땐 Claude Code:

**(가) 로컬 LLM (`run_story.py`)**

```bash
.venv/bin/python agency/run_story.py race      --scenario default --hint "달밤에 활동하는 종족"
.venv/bin/python agency/run_story.py character --scenario default --hint "은퇴한 노검사"
.venv/bin/python agency/run_story.py item      --scenario default --hint "녹슨 단검"
.venv/bin/python agency/run_story.py location  --scenario default
.venv/bin/python agency/run_story.py quest     --scenario default
.venv/bin/python agency/run_story.py chapter   --scenario default
```

`backend/.env` 의 `BASE_URL` 만 살아 있으면 됨 (in-process consumer).

**(나) Claude Code 슬래시 커맨드 (`/story-write`)**

```
/story-write character default 은퇴한 노검사
/story-write quest default
/story-write race default 달밤에 활동하는 종족
```

`.claude/commands/story-write.md` 가 본문. Claude (대화 중인 모델) 가 `_base.md` + `<kind>.md` + `world.md` + 기존 instances 를 직접 Read 하고 entity JSON 한 개를 `scenarios/<scenario>/<sub_dir>/<id>.json` 에 Write 한다. 별도 LLM 서버 불필요, `reports/` 로그도 안 남김 (대화 transcript 가 곧 로그).

### 시나리오 한 벌 (`scenario` mode)

줄글 한 편 (`<prose-path>.md`) 을 받아 시나리오 디렉터리 한 벌을 통째로 짓는다. 단계 파이프라인:

1. **분해** — `_decompose.md` prompt 가 줄글을 받아 `Decomposition` (Pydantic) 한 개로 압축: `world_md` + 6 종류 entity 명단 (각 명단의 entry 가 `id` + `role` + 부가 hint) + `start_*` 셋 + profile 메타. 분해 자체도 자기교정 5회 + 일관성 검증 (id 패턴·중복·cross-ref).
2. **world.md** — 분해의 `world_md` 본문을 디스크에 markdown 으로 저장.
3. **race → location → item → character → quest → chapter** — 각 단계마다 분해 명단의 entry 마다 `write_entity` 를 호출. 단계 순서가 참조 의존성을 따라가서, 한 단계가 다음 단계의 컨텍스트가 됨.
4. **메타 3 파일** — `profile.json` / `start.json` / `player_template.json`. 분해 결과로 직접 dict → JSON dump.

**id 강제 메커니즘** — 분해 단계에서 미리 정한 id 를 entity 단계가 따라야 한다. `write_entity(force_id=...)` 가 `_check_id` 안에서 LLM 이 박은 id 와 비교하고, 다르면 자기교정 루프가 작동해 다음 시도에 교정. `_base.md` 에도 "user 메시지의 id 강제 지시는 한 글자도 바꾸지 말 것" 명시.

```bash
.venv/bin/python agency/run_story.py scenario \
  --name default_cli \
  --prose path/to/prose.md
```

Claude Code 트랙도 같은 단계를 본문으로 받음:

```
/story-scenario default_claude path/to/prose.md
```

`.claude/commands/story-scenario.md` 가 본문. Claude (대화 중인 모델) 가 분해 → 단계별 Read/Write 를 직접 진행. 같은 줄글에서 두 트랙의 결과 (`scenarios/default_cli/` vs `scenarios/default_claude/`) 를 비교 가능.

### 한계

- `racial_skills` 는 항상 빈 리스트 (skill 합성은 별도).
- chapter 는 현재 한 개 모드 (분해 명단의 모든 quest 가 첫 chapter 에 묶임).
- 게임 진행 중 런타임 entity 주입 (live save 에 새 NPC/item 등) 은 backend 쪽 일이라 미정.
