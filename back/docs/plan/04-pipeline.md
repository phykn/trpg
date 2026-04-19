# 4. 파이프라인

> 상위: [plan.md](../plan.md)

## 4.1 1턴 흐름

```
플레이어 입력
  ↓
엔진: surroundings 조립
  ↓
DC판정 에이전트 호출
  ├─ skip    → 내러티브 에이전트 (surroundings만)
  ├─ roll    → 엔진: target 검증 → DC·mod·required_roll 계산
  │             → pending_check 저장 → SSE pending_check 이벤트 → 스트림 종료
  │             (프론트 주사위 버튼 활성)
  │             → 플레이어 주사위 → /roll
  │             → grade 판정 → target_view 조립 → 내러티브 에이전트
  ├─ combat  → [P1] SSE error(CombatNotSupported) / [P2] 자동 주사위 → 내러티브
  └─ clarify → SSE log_entry(act, question) → done. 다음 /turn 에서 재시작
  ↓
내러티브 에이전트 호출 (스트리밍)
  ↓
엔진: state_changes 검증 → 유효 변경 적용, 무효는 rejected[] 로깅
엔진: summary 를 turn_log 에 저장, (player_input, narrative) 를 recent_dialogue 에 append
엔진: memorable 이면 memory 를 memory_targets[].memories[] 에 저장
  ↓
SSE state_patch (바뀐 슬롯만) → save_game → SSE done
```

## 4.2 두 단계 턴 (pending_check)

`roll` 분기는 **한 턴을 두 HTTP 호출로 쪼갠다**. 이유는 §14.10.

- `/turn` 이 `{action: "roll"}` 로 끝나면 엔진은 `PendingCheck` 를 `GameState` 에 저장하고 스트림을 닫는다. 내러티브는 아직 돌지 않음.
- 프론트는 `pending_check` 이벤트로 받은 `{dc, stat, mod, required_roll, tier, target}` 을 UI 에 띄우고, 플레이어가 주사위를 굴리면 `/roll` 호출.
- `/roll` 은 `PendingCheck` 를 읽어 `grade` 를 계산하고 내러티브를 돌린 뒤 `pending_check = None` 으로 지운다.
- `/turn` 을 `pending_check` 가 활성인 채로 호출하면 `error: PendingCheckActive`. `/roll` 을 `pending_check` 없이 호출하면 `error: PendingCheckExpected`. P1 은 재시도/취소 엔드포인트 없음.

```python
class PendingCheck:
    player_input: str
    action: Literal['roll']
    tier: Tier
    stat: StatKey
    target: str
    targets: list[str] | None
    dc: int               # 기본 DC ± random_buffer 적용 후
    mod: int              # social_bonus
    required_roll: int    # sigmoid 결과 (1..20)
    created_at: str       # ISO 8601
```

## 4.3 target 검증

DC판정이 반환한 `target` 을 `state.characters | locations | items` 키와 대조:
- 유효 → 진행
- 무효 → DC판정 재호출 (최대 1회). 두 번째도 실패하면 현재 location 으로 폴백.

## 4.4 SSE 이벤트

한 줄 JSON 형식: `data: {"type": "<event>", "data": {...}}\n\n`. 스트림은 반드시 `done` 또는 `error` 로 종료.

| type | data | 시점 |
|---|---|---|
| `judge` | `{action, tier?, stat?, target?, targets?, question?}` | judge LLM 직후 |
| `pending_check` | `{dc, stat, mod, required_roll, tier, target}` | action=roll 확정. 직후 스트림 종료 |
| `narrative_delta` | `{text}` | narrate LLM 청크마다 |
| `state_patch` | `{hero?, subject?, quest?, place?}` | apply 후 변경된 슬롯만 |
| `log_entry` | `LogEntry` (`player | act | roll`) | 플레이어 입력, clarify 되물음, 주사위 결과. `gm` 은 `narrative_delta` 축적으로 생성되므로 이벤트 없음 |
| `done` | `{}` | 턴 종료 |
| `error` | `{message, code?}` | 복구 불가 오류 |

## 4.5 세션 생명주기

**init** (`POST /session/init`): 요청의 `profile` 이름으로 `PROFILE_DIR/{profile}/` 로딩 → `state.init.init_game` 이 `world.md`, `start.json`, `player_template.json`, `characters/`, `locations/`, `quests/`, `items/` 를 읽어 초기 `GameState` 조립 → `uuid4` 로 `game_id` 할당 → 최초 저장 → `FrontState` 와 함께 반환.

**load**: `GET /session/{id}/state` 또는 `/turn` · `/roll` 진입 시 `DATA_DIR/games/{id}.json` 을 읽어 Pydantic 으로 `GameState` 복원. 파일 없으면 HTTP 404.

**save**: `apply_changes` 이후 파이프라인 말미에서 호출. 원자적 쓰기 (`.tmp` → `os.replace`) 로 부분 쓰기 방지. 프로세스 레벨 `asyncio.Lock` 하나로 동시 저장 직렬화. 저장 실패 시 in-memory 상태 롤백 후 SSE `error: PersistenceFailed`.

**인스턴스 단위 파일**: 게임 하나 = 파일 하나 (`DATA_DIR/games/{game_id}.json`). 파일 이동·복사만으로 세션 이전 가능. 이유와 한계는 §14.11.
