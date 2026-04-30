# 프론트 경계

> 백엔드가 프론트엔드에 무엇을 어떤 모양으로 보내는지. 인덱스는 [01-overview.md](./01-overview.md). 한 턴의 안쪽 흐름은 [02-runtime.md](./02-runtime.md), 전투·확장 기능은 [03-features.md](./03-features.md), 백엔드 코드 지도는 [05-codemap.md](./05-codemap.md).

## 1. 프론트로 보내는 필드

프론트엔드는 백엔드가 준 데이터를 **있는 그대로 화면에 그리기만** 한다. 날짜 한국어 변환 ("812년 4월 28일"), 여러 값을 한 줄로 합치기 ("이름 (종족 직업)"), 조건에 따라 라벨 바꾸기 같은 가공은 전부 백엔드에서 끝낸 뒤 보낸다.

### Hero — `characters[player_id]`

| 프론트 필드 | 백엔드 출처 | 변환 |
|---|---|---|
| `name`, `level` | 같은 이름의 필드 | 그대로 복사 |
| `raceJob: str` | `race_id` + `job` | `races[race_id].name` 과 `job` 을 합쳐 `"<종족> <직업>"` 한 문자열로. `job` 이 빈 문자열이면 종족 이름만 (trailing space 없음). race 가 사라졌으면 race_id 그대로 |
| `gender: str` | `Character.gender` (`male`/`female`/`none`) | `male` → `"남성"`, `female` → `"여성"`, `none` → `""`. 빈 문자열이면 프론트가 meta 라인에서 생략 |
| `hp/hpMax`, `mp/mpMax` | 같은 이름의 필드 | 그대로 복사. 값은 엔진이 계산으로 갱신 — narrator 가 `set` 으로 못 건드림 |
| `exp/expMax` | `xp_pool` + `xp_for_next_level(level)` | 레벨업 곡선은 [03-features.md](./03-features.md) §2.3 의 `base_xp × N` |
| `canLevelUp: bool` | `engines/growth.can_afford_level_up(player)` | xp_pool 이 다음 레벨 임계 도달 + 레벨이 cap 미만일 때 true. 프론트가 레벨업 버튼/힌트 노출 결정에 사용 |
| `stats: [{label, value}]` | `stats` (STR/DEX/CON/INT/WIS/CHA) | ASCII 키를 한국어 라벨로 변환해 고정 순서 배열로 — `[{label:"근력", value}, {label:"민첩", ...}, "건강", "지능", "지혜", "매력"]`. 장비·버프 미적용 기본값. 장비·버프를 더한 실효 수치는 백엔드 내부 계산용 |
| `equipment` (3슬롯: `weapon/armor/accessory`) | `equipment` 같은 키 | 슬롯에 든 item_id 로 `items[id].name` 을 찾아 `{name}` 만 노출. 빈 슬롯은 `null` (키 3개는 항상 존재) ([03-features.md](./03-features.md) §2.5) |
| `inventory: [{name, qty}]` | `inventory_ids: list[str]` | 같은 item_id 끼리 묶어 개수를 세고, `items[id].name` 으로 이름을 찾아 `[{name, qty}]` 모양으로. **장비 슬롯에 장착된 item_id 는 슬롯당 1 개씩 차감** (invariant 상 장착 아이템은 inventory_ids 에도 존재해 중복 노출 방지) ([03-features.md](./03-features.md) §2.5) |
| `status: list[str]` | `status: list[str]` | 정해진 목록 없는 자유 문자열 태그. narrator 가 `set` 으로 추가/제거 ([02-runtime.md](./02-runtime.md) §6.1) |
| `skills: list[str]` | `racial_skill_ids + learned_skill_ids` ([03-features.md](./03-features.md) §2.6) | 두 id 리스트를 이은 뒤 각 id 로 `state.skills[id].name` 을 찾아 한 줄로 |
| `companions: list[str]` | `companions: list[char_id]` ([03-features.md](./03-features.md) §2.9) | 각 char_id 의 캐릭터를 찾아 `"이름 (종족 직업)"` 으로 조립. `job` 이 빈 문자열이면 `"이름 (종족)"` — 괄호 안 공백·trailing space 없음 |

### Subject — `characters[active_subject_id]`

active_subject_id 는 죽은 NPC 도 가리킬 수 있다 — subject pin 이 사망 시점에 사라지지 않고 corpse-aware 로 살아남아, narrate 가 죽은 정체성을 anchor 로 잡고 회상·시체 묘사를 잇는다. corpse 일 때 `known` 한 줄 (`["죽음"]`) 만 채워지고 나머지 수치는 사망 직전 상태 그대로 노출.

| 프론트 필드 | 백엔드 출처 | 변환 |
|---|---|---|
| `name`, `level` | 같은 이름의 필드 | 그대로 |
| `raceJob: str` | `race_id` + `job` | Hero.raceJob 와 동일 규칙 |
| `gender: str` | `Character.gender` | Hero.gender 와 동일 규칙 |
| `hp/hpMax` | 같은 이름의 필드 | 그대로 |
| `stats: [{label, value}]` | `stats` | Hero 와 동일 |
| `equipment` (3슬롯: `weapon/armor/accessory`) | `equipment` 같은 키 | Hero 와 동일 |
| `inventory: [{name, qty}]` | `inventory_ids` | Hero 와 동일 |
| `skills: list[str]` | `racial_skill_ids + learned_skill_ids` | Hero 와 동일 |
| `role: str` | `role: str` (프로필 config 에 들어 있는 값) | 자유 문자열. 그대로 |
| `trust: int` | `relations.get(player_id, 0)` | -100..+100, 기본 0 (중립). 방향은 **subject → player** (subject 가 player 를 어떻게 느끼는가) |
| `known: list[str]` | `appearance` (한 줄) + player 의 `memories` 중 `target_id == subject_id` 인 항목들 | 살아 있을 때: 첫 줄 = subject 의 외모 한 줄 (subject.appearance), 그 아래 = player 가 그 subject 에 대해 들고 있는 기억 한 줄씩 ([02-runtime.md](./02-runtime.md) §7). 메모리 항목이 0개면 외모 한 줄만 나감. **죽어 있을 때**: `["죽음"]` 단일 항목 (외모·메모리 무시) — 시체 톤을 패널이 한 줄로 표시. |

### Quest — `quests[active_quest_id]`

| 프론트 필드 | 백엔드 출처 | 변환 |
|---|---|---|
| `title`, `summary` | 같은 이름의 필드 | 그대로 |
| `giver: str` | `giver_id` | id 로 캐릭터를 찾아 `name` 만 노출 |
| `difficulty: str` | `Quest.difficulty` (Tier — 7단계 한글 라벨, [02-runtime.md](./02-runtime.md) §4.3) | 라벨 문자열 그대로 (`"보통"`, `"어려움"`, `"전설"` 등). 패널이 tone-colored meta line 으로 표시. 옛 `{value, max, label}` 진행도 객체는 폐기 — 퀘스트 progress 는 패널의 `goals[]` 줄로 충분하고, difficulty 자체는 단순 라벨이라 더 잘게 쪼개지 않음. |
| `goals: list[str]` | `triggers: list[QuestTrigger]` ([03-features.md](./03-features.md) §2.8) | 모든 트리거의 `name` 만 추출. **필터 없음** (narrator 용 session_layer 의 pending-only `goals` 와는 다름, [02-runtime.md](./02-runtime.md) §3.2) |
| `conditions: list[str]` | `conditions: list[str]` | 자유 문자열 제약 그대로. Hero.status 와 달리 narrator 가 `set` 으로 못 건드림 ([02-runtime.md](./02-runtime.md) §6.1) |
| `rewards: {gold, exp}` | `rewards.gold`, `rewards.exp` | 그대로. `rewards.items` 는 [P3] 추가 |

### Place — `locations[characters[player_id].location_id]`

| 프론트 필드 | 백엔드 출처 | 변환 |
|---|---|---|
| `name`, `weather` | 같은 이름의 필드 | 그대로 |
| `description: str` | `Location.description` | 장소 설명 한 줄. 패널 본문 lead. |
| `features: list[str]` | `Location.tags` | 장소 태그 그대로 |
| `dayPhase: str` | `state.turn_count` 에서 백엔드가 파생 (`domain/clock.py:day_phase`) | "새벽/오전/오후/밤" 중 하나. 분/시 단위 시계는 없음 ([03-features.md](./03-features.md) §2.1) |
| `surroundings: PlaceSurrounding[]` | `Location.connections` 의 각 엣지 | `{name, blurb, difficulty}`. `name`/`blurb` 는 인접 location 의 `name`/`description`, `difficulty` 는 Connection 의 자물쇠/통과 난이도 라벨 (없으면 `null`). 패널이 actionable surrounding row 로 표시 — 클릭하면 이동 의도 발화. |
| `targets: PlaceTarget[]` | 같은 location 에 있는 player 외 캐릭터 | `{name, level, raceJob, gender, blurb, trust}`. `level/raceJob/gender` 규칙은 Hero 와 동일. `blurb` = 살아 있으면 `appearance` (없으면 `description`), 죽어 있으면 `"죽음"`. `trust` = `relations.get(player_id, 0)`. 시체도 포함 — 패널이 corpse 톤으로 흐림 처리. |

### LogEntry — SSE `log_entry` 이벤트 + `narrative_delta` 누적

프론트가 보는 4종 — `kind` 필드로 어떤 모양인지 구분되는 4 가지 중 하나. SSE `log_entry` 이벤트로 흘러오는 건 `player | act | roll` 3종이고, `gm` 은 `narrative_delta` (이야기 본문이 조각조각 흘러오는 이벤트) 를 클라이언트가 누적해서 만든다 ([02-runtime.md](./02-runtime.md) §2.4).

- `gm` — `narrative_delta` 를 모아 만든 이야기 본문 한 덩이 (SSE 이벤트로는 안 옴)
- `player` — 플레이어가 친 입력을 그대로 되돌려 보냄 (서버 발행)
- `act` — 시스템 알림, 검증 실패 GM 메시지 등 (서버 발행)
- `roll` — 주사위 결과 (서버 발행). `{check, roll, margin, result}`. `roll` 은 d20 원본 값, `margin = total - required_roll` (음수면 미달, 양수면 초과). 옛 `dc`/`mod` 분리 노출은 폐기 — UI 가 한 숫자(`margin`) 로 성공·실패 거리를 보여주는 게 직관적이라 한 줄로 합침. `result: 'success' | 'partial' | 'fail'` 는 5단계 grade 를 3-state 로 묶음 — `critical_success | success` → `success`, `partial_success` → `partial`, `failure | critical_failure` → `fail` ([02-runtime.md](./02-runtime.md) §5.3, `flow/format.py:front_grade`)

### 내부 전용 (프론트로 안 나감)

`disposition`, `tone_hint`, `memories`, `location_id`, `relations`, `combat_behavior`, `triggers`, `inventory_ids`, `racial_skill_ids`/`learned_skill_ids`, `effective_*` 스탯, `ActiveBuff`, `xp_pool`, `death_saves` 등.

- `triggers` — QuestTrigger 의 `id`/`type`/`target_id` 는 내부 전용. 프론트엔 `name` 만 `goals[]` 로 나감.
- `racial_skill_ids`/`learned_skill_ids` — 두 id 리스트를 이어 `state.skills[id].name` 을 찾아 Hero.skills 로 나감.

### 위 매핑이 의존하는 신설 필드

§1 표가 동작하려면 다음 백엔드 필드가 정의돼 있어야 한다. 자세한 스키마는 각 절 참고:

- **Character.role: str** — 자유 문자열 ("몬스터", "마을 장로" 등). 프로필 config 에 들어 있는 값.
- **Character.gender: Literal["male","female","none"]** — 캐릭터 생성 시 플레이어가 고르고 (`PlayerInput.gender`), NPC 는 시드 (`scenarios/{id}/characters/*.json`) 에 들어 있다. 짐승·괴수는 `none` 기본값. 프론트로는 한국어 라벨 (`남성`/`여성`/빈값) 로 변환되어 Hero / Subject / Place.targets meta 라인에 노출.
- **Character.appearance: str** — 시간이 지나도 변하지 않는 외모 한 줄 (자유 텍스트). `Subject.known` 첫 줄·`Place.targets[].blurb` 출처. NPC 는 시드 (`scenarios/{id}/characters/*.json`) 에 들어 있고, 플레이어는 입력으로 받지 않으므로 빈 문자열 — `Subject` 패널은 player 가 active subject 일 일이 없어 무관. 태그 리스트 아님.
- **Character.status: list[str]** — 자유 문자열 상태 태그. narrator 가 `set` 으로 추가·제거.
- **Character.relations: dict[str, int]** — affinity ([03-features.md](./03-features.md) §2.2). `Subject.trust` 가 여기서 옴.
- **Location.connections: list[str]** — 인접 장소의 ID 리스트. `Place.surroundings` 산출에 씀.
- **Quest.triggers: list[QuestTrigger]** — 자동 발동 트리거 ([03-features.md](./03-features.md) §2.8). 각 트리거는 `id`, `name`, `type`, `target_id` 를 가짐. `Quest.goals` 는 여기서 `name` 만 뽑은 것.
- **Quest.conditions: list[str]** — 자유 문자열 제약 ([03-features.md](./03-features.md) §2.8). 프론트로 그대로 나감.
- **Quest.rewards: {gold, exp, items?[P3]}** — gold/exp 만 P1 노출.
- **Quest.difficulty: Tier** — 7단계 한글 라벨 ([02-runtime.md](./02-runtime.md) §4.3, [03-features.md](./03-features.md) §2.8). 라벨 그대로 프론트에 노출.
- **Place.dayPhase** — `state.turn_count` 에서 백엔드가 파생 ([03-features.md](./03-features.md) §2.1).
- **Place.targets/surroundings** — `to_front_state` 가 같은 location 의 alive·dead 캐릭터를 `targets[]`, 인접 location (`Connection`) 을 `surroundings[]` 로 사영. 시체는 `targets` 에 `blurb="죽음"` 으로 노출.
- **Memory.target_id: str | None** — 메모리가 어느 엔티티에 관한 것인지 가리키는 ID. `Subject.known` 산출이 player 의 `memories` 중 `target_id == subject_id` 인 항목만 골라 쓴다. narrator 의 `memory_links` 출력으로 채워짐 ([02-runtime.md](./02-runtime.md) §1.2, §7.1, §7.2).
- **Race** — 종족 시드. 필드: `id: str`, `name: str`, `description: str`, `racial_skill_ids: list[str]`. `GET /profiles` 응답의 race 카드에 `{id, name, description}` 만 노출 (skill_ids 는 내부). 캐릭터 생성에서 사용자가 race 를 고르면 init 이 그 race 의 `racial_skill_ids` 를 player 의 `racial_skill_ids` 에 그대로 부여 ([02-runtime.md](./02-runtime.md) §2.5). 시드는 `scenarios/{id}/races/*.json`.

## 2. 외부 API

모든 게임 행동은 `POST /turn` 의 자연어 입력 한 통로에 모인다 — judge 가 입력을 보고 액션 종류 (장비·거래·레벨업·기술·아이템 사용 등) 를 분류한다. 옛 메타 액션 REST 엔드포인트 (`/level-up`, `/learn-skill`, `/equip`, `/unequip`, `/buy`, `/sell`, `/cast`, `/use`) 는 폐기. 결정 이유는 [01-overview.md](./01-overview.md) §3.16.

| 메서드 | 경로 | 바디 | 응답 |
|---|---|---|---|
| GET  | `/profiles` | — | `[{id, name, description, races: [{id, name, description}]}]` |
| POST | `/session/init` | `{profile: string, player: {name: string, race_id: string, gender: "male"\|"female"}}` | `{game_id, state: FrontState}` |
| GET  | `/session/{id}/state` | — | `{game_id, state: FrontState}` |
| POST | `/session/{id}/turn` | `{player_input: string}` | `text/event-stream` (SSE — 서버가 한 연결을 열어둔 채 이벤트를 계속 흘려주는 방식) |
| POST | `/session/{id}/roll` | — (서버가 d20 굴림) | `text/event-stream`. `pending_check.kind="stat"` 의 일반 굴림만 받음 — 전투/죽음 굴림은 자동 처리되어 dice 버튼이 뜨지 않음 ([02-runtime.md](./02-runtime.md) §2.2) |
| POST | `/session/{id}/intro` | — | `text/event-stream`. 게임 시작 직후 첫 GM narration 한 번. judge 안 부르고 `flow/intro.py` 가 narrate 만 호출 |

`FrontState = {hero, subject, quest, place, combat, log, pendingCheck}`. SSE `state` 이벤트 ([02-runtime.md](./02-runtime.md) §2.4) 는 같은 7 슬롯 묶음 — `log` 는 누적되는 흐름이라 `log_entry` 이벤트로도 따로 흐른다 (state 안에는 영속본 꼬리만). **`FrontState.log` 영속본 cap 은 `rules.log.display_turns` (기본 20)** — `GET /session/{id}/state` 는 최근 20 턴치만 반환 ([02-runtime.md](./02-runtime.md) §6.2 디스플레이 로그 영속화). `pendingCheck` 는 `state.pending_check` 가 활성일 때만 채워짐 — 앱이 굴림 도중에 닫혀도 다음 GET 으로 UI 가 복원된다.

`pendingCheck` 모양 — `{kind, dc, stat, stat_label, stat_value, mod, required_roll, tier:{value,max,label}, target, reason}`. `kind` 는 항상 `"stat"`, `stat_label` 은 stat 의 한국어 라벨, `stat_value` 는 그 스탯의 플레이어 점수, `reason` 은 judge `RollAction.reason` 의 자유 텍스트 — 프론트 RollPrompt 가 dice strip 위에 표시.

`combat` 슬롯 — 평시엔 `null`. 자동 사이클은 결판까지 직진해 사이클 끝에 곧장 `null` 로 비워지므로, 평시 GET 응답에서 활성으로 보일 일은 ambush (수면 중 기습) 직후 한 번 정도. ambush 는 surprise round 1번만 돌고 멈춰 player 입력을 기다린다.

세션 흐름 — 앱 시작 시 클라이언트 `localStorage` 에 보관된 game_id 가 있으면 `GET /session/{id}/state` 로 복원 시도 → 200 이면 진행 중 게임 복원, 404·미보관이면 `GET /profiles` 호출 → 프론트가 시나리오·종족 카드를 보여주고 사용자가 캐릭터 생성 → `POST /session/init` 호출 (응답의 game_id 를 localStorage 에 저장) → `POST /session/{id}/intro` 로 시작 GM narration → 이후 `/turn` 으로 진행. 서버는 "최근 게임" 포인터를 들고 있지 않아 한 서버에 여러 사용자가 붙어도 서로의 마지막 게임이 안 섞인다. 게임 목록·이어하기 화면은 P1 에 없음 (사용자 한 명당 한 게임 흐름).

**인증** — `/health` 를 제외한 모든 endpoint 가 HTTP Basic Auth 로 보호. `GET /profiles` 도 예외 아님 — 같은 LAN 안에서도 시나리오 메타 노출은 인증 뒤. `BASIC_AUTH_USER` / `BASIC_AUTH_PASS` env 누락 시 fail-fast ([01-overview.md](./01-overview.md) 환경 변수 부록).

**액션 처리 위치** — judge 가 분류한 액션은 `flow/turn.py` 의 액션 분기에서 그 자리에서 엔진을 호출. 옛 명시적 endpoint 가 던지던 422 (`LevelUpInvalid` / `InventoryInvalid` / `SkillInvalid`) 는 이제 HTTP 응답이 아니라 인-게임 로그로 흡수된다 — 검증 실패 시 `format.py` 가 영문 에러 메시지를 한국어 한 줄로 변환해 GM `log_entry` 로 흘림 ("그 검은 손에 들 수 없는 무게다" 같은 식).

전투는 [03-features.md](./03-features.md) §1 의 한 방 시네마틱. 휴식은 P3 §2.4. 레벨업은 P3 §2.3. 장비·거래는 P3 §2.5. 기술 cast 는 P3 §2.6. 아이템 사용은 P3 §2.7. 모두 자연어 입력 → judge 분류 경로.

## 3. 에러 매핑

| 상황 | 응답 |
|---|---|
| `game_id` 없음 | HTTP 404 `{detail: "game not found"}` (FastAPI 기본 형식) |
| `/session/init` 의 `profile` / `race_id` 검증 실패 | HTTP 422 (`ProfileNotFound` / `RaceNotFound` / `ProfileMalformed`) |
| judge 가 `action="combat"` / `summon_combat` 반환 | 엔진이 `combat_state` 띄우고 자동 사이클 (라운드 N개) 실행 → SSE `combat_start` + `combat_turn`* + `narrative_delta`* + `combat_end` (terminal 시) ([03-features.md](./03-features.md) §1) |
| `/turn` 진입 시 pending_check 가 이미 활성 | SSE `error: PendingCheckActive` |
| `/roll` 진입 시 pending_check 가 비어 있음 | SSE `error: PendingCheckExpected` |
| judge LLM 출력이 JSON 파싱 실패 | 5회까지 자기 교정 재시도 (직전 응답+에러를 messages 에 append) → 마지막에도 실패면 SSE `error: JudgeMalformed` ([02-runtime.md](./02-runtime.md) §2.3) |
| judge 의 target 검증 (semantic) 실패 | 5회까지 자기 교정 재시도 → 마지막에도 실패면 현재 location 으로 fallback (에러 아님). JSON 실패와 같은 retry 카운터 공유 |
| 액션 검증 실패 (`LevelUpInvalid` / `InventoryInvalid` / `SkillInvalid`) | HTTP 응답 아님 — `flow/actions.py` 가 catch 해서 `format.py` 가 한국어 한 줄로 변환 후 GM `log_entry` 로 발행. 턴 자체는 정상 종료 |
| narrate JSON 파싱 실패 | 본문은 보존, `state_changes=[]`, `memorable=False` 로 강등 |
| narrate `state_change` 가 스키마 위반 | 그 항목만 버리고 `rejected[]` 에 기록, 나머지는 적용 |
| LLM 자체가 연결 안 됨 | SSE `error: LLMUnavailable` 후 종료 |
| 저장 실패 | SSE `error: PersistenceFailed` (메모리 롤백 없음 — 다음 GET 이 디스크에서 다시 로드하면 복구) |

