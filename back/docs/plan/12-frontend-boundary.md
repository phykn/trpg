# 12. 프론트 경계

> 상위: [plan.md](../plan.md)

## 12.1 노출 슬롯

| 프론트 타입 | 소스 | 노출 필드 |
|---|---|---|
| `Hero` | `characters[player_id]` | name, race, job, level, exp, expMax, hp, hpMax, mp, mpMax, stats, equipment, inventory, status, skills, companions |
| `Subject` | `characters[active_subject_id]` | name, role, race, job, trust, known, level, hp, hpMax, stats, inventory |
| `Quest` | `quests[active_quest_id]` | title, giver (이름), difficulty, goals, conditions, rewards, memo |
| `Place` | `locations[characters[player_id].location_id]` | name, date, hour, weather, features, surroundings |
| `LogEntry` | `turn_log` + 이벤트 부산물 | `gm / player / act / roll` 4종 union |

- `Subject.trust = characters[active_subject_id].relations.get(player_id, 50)` — **대상이 플레이어를 어떻게 느끼는가** (반대 방향 아님).
- `Subject.inventory` 는 내부 `inventory_ids` 를 Counter 로 집약해 `{name, qty}` 배열 (§11.4).
- `Place.date` 는 한국어 포맷 ("812년 4월 28일"), `hour` 는 0..23. `world_time` (ISO) 을 파싱.
- 내부 전용 필드(`disposition`, `tone_hint`, `memories`, `location_id`, `relations`, `combat_behavior` 등) 는 **절대 노출 금지**.

## 12.2 외부 API

| 메서드 | 경로 | 바디 | 응답 |
|---|---|---|---|
| POST | `/session/init` | `{profile: string}` | `{game_id, state: FrontState}` |
| GET  | `/session/{id}/state` | — | `FrontState` |
| POST | `/session/{id}/turn` | `{player_input: string}` | `text/event-stream` |
| POST | `/session/{id}/roll` | `{dice: int (1..20)}` | `text/event-stream` |

`FrontState = {hero, subject, quest, place, log}`.

## 12.3 에러 매핑

| 상황 | 응답 |
|---|---|
| `game_id` 없음 | HTTP 404 `{error: "game not found"}` |
| `/turn` 중 pending_check 활성 | SSE `error: PendingCheckActive` |
| `/roll` 중 pending_check 없음 | SSE `error: PendingCheckExpected` |
| `/roll` 의 dice 범위 밖 (1..20) | HTTP 422 (Pydantic) |
| judge JSON 파싱 실패 | 재시도 1회 → 실패 시 SSE `error: JudgeMalformed` |
| judge target 유효성 2회 연속 실패 | 현재 location 으로 폴백 (에러 아님) |
| narrate JSON 파싱 실패 | narrative 는 보존, `state_changes=[]`, `memorable=False` 로 degrade |
| narrate state_change 스키마 위반 | 해당 항목 drop + `rejected[]` 로깅, 나머지 적용 |
| LLM 연결 실패 | SSE `error: LLMUnavailable` 후 종료 |
| 저장 실패 | SSE `error: PersistenceFailed`, in-memory 상태 롤백 |
