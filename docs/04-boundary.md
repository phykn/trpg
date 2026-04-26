# 외부 경계 (§1-§2)

> 백엔드가 바깥과 닿는 두 면을 모은 문서. §1 은 프론트엔드에 무엇을 어떤 모양으로 보내는지, §2 는 그 일을 하는 코드가 어디에 있는지.
> 인덱스는 [01-plan.md](./01-plan.md). 한 턴의 안쪽 흐름은 [02-runtime.md](./02-runtime.md), 전투·확장 기능은 [03-features.md](./03-features.md).

§1 은 "프론트가 받는 그림", §2 는 "백엔드 내부 구조". 두 절을 한 문서에 둔 이유: 프론트로 나가는 데이터는 전부 `mapping/to_front.py` 한 파일을 거치므로, 그 파일의 양쪽 (받는 쪽 — 프론트, 만드는 쪽 — 백엔드) 을 같이 두는 게 일관성이 좋다.

---

## 1. 프론트 경계

### 1.1 프론트로 보내는 필드

프론트엔드는 백엔드가 준 데이터를 **있는 그대로 화면에 그리기만** 한다. 날짜 한국어 변환 ("812년 4월 28일"), 여러 값을 한 줄로 합치기 ("이름 (종족 직업)"), 조건에 따라 라벨 바꾸기 같은 가공은 전부 백엔드에서 끝낸 뒤 보낸다.

#### Hero — `characters[player_id]`

| 프론트 필드 | 백엔드 출처 | 변환 |
|---|---|---|
| `name`, `race`, `job`, `level` | 같은 이름의 필드 | 그대로 복사 |
| `hp/hpMax`, `mp/mpMax` | 같은 이름의 필드 | 그대로 복사. 값은 엔진이 계산으로 갱신 — narrator 가 `set` 으로 못 건드림 |
| `exp/expMax` | `xp_pool` + 레벨 곡선 [P3] | xp/level 시스템 자체가 P3 일정 ([03-features.md](./03-features.md) §2.3). P1 동안은 자리표시 0/0 만 노출 |
| `stats` | `stats` | 장비·버프 미적용 기본값. 장비·버프를 더한 실효 수치는 백엔드 내부 계산용 |
| `equipment` (8슬롯: `head/top/bottom/feet/leftHand/rightHand/acc1/acc2`) | `equipment` 같은 키 | 슬롯에 든 item_id 로 `items[id].name` 을 찾아 `{name}` 만 노출. 빈 슬롯은 `null` (키 8개는 항상 존재) ([03-features.md](./03-features.md) §2.5) |
| `inventory: [{name, qty}]` | `inventory_ids: list[str]` | 같은 item_id 끼리 묶어 개수를 세고, `items[id].name` 으로 이름을 찾아 `[{name, qty}]` 모양으로 ([03-features.md](./03-features.md) §2.5) |
| `status: list[str]` | `status: list[str]` | 정해진 목록 없는 자유 문자열 태그. narrator 가 `set` 으로 추가/제거 ([02-runtime.md](./02-runtime.md) §6.1) |
| `skills: list[str]` | `racial_skills + learned_skills` ([03-features.md](./03-features.md) §2.6) | 두 리스트를 합친 뒤 각 스킬에서 `name` 만 추출 |
| `companions: list[str]` | `companions: list[char_id]` ([03-features.md](./03-features.md) §2.9) | 각 char_id 의 캐릭터를 찾아 `"이름 (종족 직업)"` 으로 조립. `job` 이 빈 문자열이면 `"이름 (종족)"` — 괄호 안 공백·trailing space 없음 |

#### Subject — `characters[active_subject_id]`

| 프론트 필드 | 백엔드 출처 | 변환 |
|---|---|---|
| `name`, `race`, `job`, `level` | 같은 이름의 필드 | 그대로 |
| `hp/hpMax` | 같은 이름의 필드 | 그대로 |
| `stats` | `stats` | 그대로 |
| `inventory: [{name, qty}]` | `inventory_ids` | Hero 와 동일 |
| `role: str` | `role: str` (프로필 config 에 박힌 값) | 자유 문자열. 그대로 |
| `trust: int` | `relations.get(player_id, 0)` | -100..+100, 기본 0 (중립). 방향은 **subject → player** (subject 가 player 를 어떻게 느끼는가) |
| `known: list[str]` | `appearance` (한 줄) + player 의 `memories` 중 `target_id == subject_id` 인 항목들 | 첫 줄 = subject 의 외모 한 줄 (subject.appearance), 그 아래 = player 가 그 subject 에 대해 들고 있는 기억 한 줄씩 ([02-runtime.md](./02-runtime.md) §7). 메모리 항목이 0개면 외모 한 줄만 나감. |

#### Quest — `quests[active_quest_id]`

| 프론트 필드 | 백엔드 출처 | 변환 |
|---|---|---|
| `title`, `summary` | 같은 이름의 필드 | 그대로 |
| `giver: str` | `giver_id` | id 로 캐릭터를 찾아 `name` 만 노출 |
| `difficulty: {value, max, label}` | tier 정수 ([02-runtime.md](./02-runtime.md) §4.3) | 백엔드가 7단계로 만들어 보냄: `value=tier(1..7)`, `max=7`, `label=한글명` |
| `goals: list[str]` | `triggers: list[QuestTrigger]` ([03-features.md](./03-features.md) §2.8) | 모든 트리거의 `name` 만 추출. **필터 없음** (narrator 용 session_layer 의 pending-only `goals` 와는 다름, [02-runtime.md](./02-runtime.md) §3.2) |
| `conditions: list[str]` | `conditions: list[str]` | 자유 문자열 제약 그대로. Hero.status 와 달리 narrator 가 `set` 으로 못 건드림 ([02-runtime.md](./02-runtime.md) §6.1) |
| `rewards: {gold, exp}` | `rewards.gold`, `rewards.exp` | 그대로. `rewards.items` 는 [P3] 추가 |

#### Place — `locations[characters[player_id].location_id]`

| 프론트 필드 | 백엔드 출처 | 변환 |
|---|---|---|
| `name`, `weather`, `features` | 같은 이름의 필드 | 그대로 |
| `date: str` | `world_time` (ISO 8601 형식 문자열, 예: `"0812-04-28T..."`) | 한국어 표기로 ("812년 4월 28일") |
| `hour: int` | `world_time` 의 시 부분 | 0..23 정수만 추출 |
| `period: str` | `world_time` 으로 백엔드가 계산 | "새벽/오전/오후/저녁/밤" 중 하나 |
| `surroundings: list[str]` | 인접 location 들의 `name` (`connections` 으로 연결됨) | 인접 장소 이름만 |

#### LogEntry — SSE `log_entry` 이벤트 + `narrative_delta` 누적

프론트가 보는 4종 — `kind` 필드로 어떤 모양인지 구분되는 4 가지 중 하나. SSE `log_entry` 이벤트로 흘러오는 건 `player | act | roll` 3종이고, `gm` 은 `narrative_delta` (이야기 본문이 조각조각 흘러오는 이벤트) 를 클라이언트가 누적해서 만든다 ([02-runtime.md](./02-runtime.md) §2.4).

- `gm` — `narrative_delta` 를 모아 만든 이야기 본문 한 덩이 (SSE 이벤트로는 안 옴)
- `player` — 플레이어가 친 입력을 그대로 되돌려 보냄 (서버 발행)
- `act` — clarify 되묻기, 시스템 알림 등 (서버 발행)
- `roll` — 주사위 결과 (서버 발행). `result: 'success' | 'fail'` 는 5단계 grade 를 3:2 로 줄임 — `critical_success | success | partial_success` → `success`, 나머지 → `fail` ([02-runtime.md](./02-runtime.md) §5.3)

#### 내부 전용 (프론트로 안 나감)

`disposition`, `tone_hint`, `memories`, `location_id`, `relations`, `combat_behavior`, `triggers`, `inventory_ids`, `racial_skills`/`learned_skills`, `effective_*` 스탯, `ActiveBuff`, `xp_pool`, `death_saves` 등.

- `triggers` — QuestTrigger 의 `id`/`type`/`target_id` 는 내부 전용. 프론트엔 `name` 만 `goals[]` 로 나감.
- `racial_skills`/`learned_skills` — 두 리스트를 합쳐 `name` 만 빼서 Hero.skills 로 나감.

#### 위 매핑이 의존하는 신설 필드

§1.1 표가 동작하려면 다음 백엔드 필드가 정의돼 있어야 한다. 자세한 스키마는 각 절 참고:

- **Character.role: str** — 자유 문자열 ("몬스터", "마을 장로" 등). 프로필 config 에 박힌 값.
- **Character.appearance: str** — 시간이 지나도 변하지 않는 외모 한 줄 (자유 텍스트). `Subject.known` 의 첫 줄. 새 게임 시 사용자가 캐릭터 생성 화면에서 한 칸에 자유롭게 적은 값. NPC 는 시드 (`config/profiles/{id}/characters/*.json`) 에 박힘. 태그 리스트 아님.
- **Character.status: list[str]** — 자유 문자열 상태 태그. narrator 가 `set` 으로 추가·제거.
- **Character.relations: dict[str, int]** — affinity ([03-features.md](./03-features.md) §2.2). `Subject.trust` 가 여기서 옴.
- **Location.connections: list[str]** — 인접 장소의 ID 리스트. `Place.surroundings` 산출에 씀.
- **Quest.triggers: list[QuestTrigger]** — 자동 발동 트리거 ([03-features.md](./03-features.md) §2.8). 각 트리거는 `id`, `name`, `type`, `target_id` 를 가짐. `Quest.goals` 는 여기서 `name` 만 뽑은 것.
- **Quest.conditions: list[str]** — 자유 문자열 제약 ([03-features.md](./03-features.md) §2.8). 프론트로 그대로 나감.
- **Quest.rewards: {gold, exp, items?[P3]}** — gold/exp 만 P1 노출.
- **Place.period** — `world_time` 으로 백엔드가 계산 ([03-features.md](./03-features.md) §2.1).
- **Memory.target_id: str | None** — 메모리가 어느 엔티티에 관한 것인지 가리키는 ID. `Subject.known` 산출이 player 의 `memories` 중 `target_id == subject_id` 인 항목만 골라 쓴다. narrator 의 `memory_links` 출력으로 채워짐 ([02-runtime.md](./02-runtime.md) §1.2, §7.1, §7.2).
- **Race** — 종족 시드. 필드: `id: str`, `name: str`, `description: str`, `racial_skills: list[Skill]`. `GET /profiles` 응답의 race 카드에 `{id, name, description}` 만 노출 (skills 는 내부). 캐릭터 생성에서 사용자가 race 를 고르면 init 이 그 race 의 `racial_skills` 를 player 의 `racial_skills` 컬렉션에 그대로 부여 ([02-runtime.md](./02-runtime.md) §2.5). 시드는 `config/profiles/{id}/races/*.json`.

### 1.2 외부 API

| 메서드 | 경로 | 바디 | 응답 |
|---|---|---|---|
| GET  | `/profiles` | — | `[{id, name, description, races: [{id, name, description}]}]` |
| GET  | `/session/current` | — | `FrontState` (없으면 HTTP 404 — 프론트는 새게임 화면으로 분기) |
| POST | `/session/init` | `{profile: string, player: {name: string, race_id: string, appearance: string}}` | `{game_id, state: FrontState}` |
| GET  | `/session/{id}/state` | — | `FrontState` |
| POST | `/session/{id}/turn` | `{player_input: string}` | `text/event-stream` (SSE — 서버가 한 연결을 열어둔 채 이벤트를 계속 흘려주는 방식) |
| POST | `/session/{id}/roll` | — (서버가 d20 굴림) | `text/event-stream` |

`FrontState = {hero, subject, quest, place, log}`. SSE `state` 이벤트 ([02-runtime.md](./02-runtime.md) §2.4) 는 `{hero, subject, quest, place}` 4 슬롯만 — `log` 는 누적되는 흐름이라 `log_entry` 이벤트로 따로 흐름. **`FrontState.log` 영속본 cap 은 `rules.log.display_turns` (기본 20)** — `GET /session/{id}/state` 와 `GET /session/current` 모두 최근 20 턴치만 반환 ([02-runtime.md](./02-runtime.md) §6.2 디스플레이 로그 영속화).

세션 흐름 — 앱 시작 시 `GET /session/current` 시도 → 200 이면 진행 중 게임 복원, 404 면 `GET /profiles` 호출 → 프론트가 시나리오·종족 카드를 보여주고 사용자가 캐릭터 생성 → `POST /session/init` 호출 → 첫 턴. 게임 목록·이어하기 화면은 P1 에 없음 (한 명·한 게임 흐름).

**인증** — 위 6 개 endpoint 모두 HTTP Basic Auth 로 보호. `GET /profiles` 도 예외 아님 — 같은 LAN 안에서도 시나리오 메타 노출은 인증 뒤. `BASIC_AUTH_USER` / `BASIC_AUTH_PASS` env 누락 시 fail-fast ([01-plan.md](./01-plan.md) 환경 변수 부록).

P1 에서는 빠지는 엔드포인트 — 장비·소비·캐스트·휴식·레벨업·거래는 전부 [P3] ([03-features.md](./03-features.md) §2.3-§2.7, [01-plan.md](./01-plan.md) §3.9). 전투 진입은 P1 에서 SSE `error: CombatNotSupported` 로 거절.

### 1.3 에러 매핑

| 상황 | 응답 |
|---|---|
| `game_id` 없음 | HTTP 404 `{detail: "game not found"}` (FastAPI 기본 형식) |
| judge 가 `action="combat"` 반환 (P1 미구현) | SSE `error: CombatNotSupported` |
| `/turn` 진입 시 pending_check 가 이미 활성 | SSE `error: PendingCheckActive` |
| `/roll` 진입 시 pending_check 가 비어 있음 | SSE `error: PendingCheckExpected` |
| judge LLM 출력이 JSON 파싱 실패 | 5회까지 자기 교정 재시도 (직전 응답+에러를 messages 에 append) → 마지막에도 실패면 SSE `error: JudgeMalformed` ([02-runtime.md](./02-runtime.md) §2.3) |
| judge 의 target 검증 (semantic) 실패 | 5회까지 자기 교정 재시도 → 마지막에도 실패면 현재 location 으로 fallback (에러 아님). JSON 실패와 같은 retry 카운터 공유 |
| narrate JSON 파싱 실패 | 본문은 보존, `state_changes=[]`, `memorable=False` 로 강등 |
| narrate `state_change` 가 스키마 위반 | 그 항목만 버리고 `rejected[]` 에 기록, 나머지는 적용 |
| LLM 자체가 연결 안 됨 | SSE `error: LLMUnavailable` 후 종료 |
| 저장 실패 | SSE `error: PersistenceFailed`, in-memory 상태 롤백 |

---

## 2. 코드 지도

§1 의 매핑이 어느 코드 파일에 있는지, 그 주변 모듈이 어떻게 정리돼 있는지.

### 2.1 모듈 구조

```
back/
  run_api.py                     FastAPI 진입점 (build_app, main)
  .env                           HOST, PORT, BASE_URL, BASIC_AUTH_USER, BASIC_AUTH_PASS, DATA_DIR, PROFILE_DIR
  config/
    profiles/
      default/
        profile.json             시나리오 메타: id, name, description (GET /profiles 응답 베이스)
        world.md                 세계관·톤
        start.json               시작 장소·활성 퀘스트·활성 subject·world_time
        player_template.json     플레이어 캐릭터 시드 (시작 위치·equipment·인벤토리만 사용. name·race_id·appearance·stats 는 init 요청값으로 덮어씀)
        characters/*.json        NPC 시드
        locations/*.json         장소 시드
        quests/*.json            퀘스트 시드
        items/*.json             아이템 시드
        races/*.json             종족 시드 (id, name, description, racial_skills) — 캐릭터 생성 화면의 종족 목록
  data/
    .current                     마지막 game_id 한 줄 (GET /session/current 가 읽음)
    games/{game_id}.json         GameState 한 덩이 (엔티티 + 로그 + 메모리 + pending)
  src/
    rules.py                     DC·시간·소셜·메모리·로그 수치 (P1 은 DC·소셜·메모리·로그만, 전투·거래·성장은 P2·P3). frozen Pydantic — 변경 시도하면 에러.
    api/
      routes.py                  /profiles, /session/current, /session/init, /session/{id}/state, /turn, /roll
      schema.py                  네트워크로 주고받는 Pydantic 모델 (ProfileListResponse, InitRequest/Response, TurnRequest, RollRequest)
      sse.py                     이벤트를 텍스트로 직렬화, StreamingResponse 헬퍼
    pipeline/
      judge.py                   DC 판정 에이전트 호출 + JSON 파싱 + target 검증
      narrate.py                 내러티브 에이전트 호출 + 응답 스트림 파싱 (본문 조각 + 끝에 붙는 JSON)
      apply.py                   `state_changes` 검증·적용 + `rejected[]` 기록
      context.py                 surroundings / target_view / history 모아 묶음
      dc.py                      sigmoid DC, tier → DC, social_bonus, grade 계산
      turn.py                    `run_turn` / `run_roll` 흐름 지휘 (SSE 이벤트 방출)
    state/
      store.py                   `load_game` / `save_game` (원자적 파일 I/O + 동시 쓰기 방지 Lock) + `.current` 읽기/쓰기
      init.py                    프로필 + 캐릭터 생성 요청 → 초기 GameState
      models.py                  GameState 컨테이너 (엔티티 dict + world_time + pending_check + turn_log + recent_dialogue + log_entries + active_subject_id + active_quest_id + player_id)
    ontology/
      graph.py                   구조 관계·의미 관계·config 관계 — 그래프 엣지 종류
      target_view.py             target 노드에서 1~2 단계 떨어진 이웃까지 훑기
    domain/
      entities.py                Character, Race, Location, Item, Quest, QuestTrigger, QuestRewards, Connection, Equipment, Stats
      memory.py                  Memory, TurnLogEntry, DialoguePair, PendingCheck, LogEntry (gm/player/act/roll union)
      types.py                   StatKey, Tier, Grade, Intent, Action enum
    llm_client/                  LLMClient (OpenAI 호환 스트리밍) + 에이전트 묶음
      __init__.py                LLMClient export
      client.py                  스트리밍 클라이언트 본체
      agents/                    에이전트별 디렉터리 — 호출 래퍼·프롬프트·스키마를 한 곳에
        dc_judge/                DC 판정 에이전트
          runner.py              호출 래퍼 (`pipeline/judge.py` 가 사용). 5회 자기 교정 retry, 마지막 에러 종류로 분기 ([02-runtime.md](./02-runtime.md) §2.3)
          schema.py              입출력 Pydantic
          semantics.py           target 검증 등 후처리
          prompt.md              시스템 프롬프트
        # narrate/ 등 다른 에이전트도 같은 레이아웃
    mapping/
      to_front.py                to_hero / to_subject / to_quest / to_place / to_log_entry / to_front_state / to_profile_list
    errors.py                    DomainError, CombatNotSupported, PendingCheckExpected, ...
```

### 2.2 레이어 경계

- `domain/` + `ontology/` = 게임이 다루는 모든 데이터 모양 (스키마) 의 정의.
- `pipeline/` = 한 턴의 로직. 순수 파이썬이라 FastAPI 없이도 돌아간다 — 단위 테스트에서 TestClient 안 띄워도 직접 호출 가능해야 함.
- `api/` = HTTP 입출구의 얇은 어댑터. URL 라우팅, 요청 모양 검증, SSE 응답 포장만 담당.
- `mapping/to_front.py` = 프론트로 데이터를 내보내는 단 하나의 파일 ([01-plan.md](./01-plan.md) §3.13).
- `state/store.py` = 디스크 I/O 의 유일한 통로. 파이프라인은 이 모듈을 거쳐야 저장 상태에 닿음.

### 2.3 오류 계층

`src/errors.py` 의 예외 계층. 파이프라인은 `DomainError` 하위 클래스만 던지고, API 레이어가 그걸 HTTP/SSE 응답으로 매핑한다 (§1.3 표).

- `DomainError` — 모든 도메인 에러의 기반 클래스.
  - `CombatNotSupported` — judge 가 `action="combat"` 을 반환했을 때 P1 이 던짐 ([03-features.md](./03-features.md) §1 의 미구현 구간).
  - `PendingCheckActive` — `/turn` 진입 시 `pending_check` 가 이미 설정돼 있을 때.
  - `PendingCheckExpected` — `/roll` 진입 시 `pending_check` 가 비어 있을 때.
  - `JudgeMalformed` — judge LLM 출력이 2번 연속 JSON 파싱 실패.
  - `LLMUnavailable` — judge / narrate 어느 단계에서든 LLM 연결 실패.
  - `PersistenceFailed` — 저장 I/O 실패 (원자 교체 직전 또는 도중 오류).

Pydantic 422 (요청 모양 검증), HTTP 404 (`game_id` 없음) 은 FastAPI 기본 처리로 가고 `DomainError` 가 아니다.
