# 13. 코드 지도

> 상위: [plan.md](../plan.md)

## 13.1 모듈 구조

```
back/
  run_api.py                     FastAPI 엔트리 (build_app, main)
  .env                           HOST, PORT, BASE_URL, DATA_DIR, PROFILE_DIR, DEFAULT_PROFILE
  config/
    rules.py                     DC·시간·소셜 수치 (P1 은 DC·소셜·메모리만, 전투·거래·성장은 P2·P3)
    profiles/
      default/
        world.md                 세계관·톤
        start.json               시작 장소·활성 퀘스트·활성 subject·world_time
        player_template.json     Player Character 시드
        characters/*.json        NPC 시드
        locations/*.json         장소 시드
        quests/*.json            퀘스트 시드
        items/*.json             아이템 시드
  data/
    games/{game_id}.json         GameState 덩이 (엔티티 + 로그 + 메모리 + pending)
  src/
    api/
      routes.py                  /session/init, /session/{id}/state, /turn, /roll
      schema.py                  Pydantic wire (InitRequest/Response, TurnRequest, RollRequest)
      sse.py                     이벤트 직렬화, StreamingResponse 헬퍼
    pipeline/
      judge.py                   DC 판정 에이전트 호출 + JSON 파싱 + target 검증
      narrate.py                 내러티브 에이전트 호출 + stream parsing (delta + trailing JSON)
      apply.py                   state_changes 검증·적용 + rejected[] 로깅
      context.py                 surroundings / target_view / history 조립
      dc.py                      sigmoid DC, tier → DC, social_bonus, grade
      turn.py                    run_turn / run_roll 오케스트레이터 (SSE 이벤트 방출)
    state/
      store.py                   load_game / save_game (atomic file I/O + Lock)
      init.py                    프로필 → 초기 GameState
      models.py                  GameState 컨테이너
    ontology/
      graph.py                   구조적·의미적·config 엣지
      target_view.py             target 기준 1-2홉 탐색
    domain/
      entities.py                Character, Location, Item, Quest, Connection, Equipment, Stats
      memory.py                  Memory, TurnLogEntry, DialoguePair, PendingCheck
      types.py                   StatKey, Tier, Grade, Intent, Action enum
    llm/
      client.py                  LLMClient (OpenAI-compat 스트리밍)
      prompts/
        judge.md                 DC 판정 시스템 프롬프트
        narrate.md               내러티브 시스템 프롬프트
        __init__.py              load_prompt(name)
    mapping/
      to_front.py                to_hero / to_subject / to_quest / to_place / to_log_entry / to_front_state
    errors.py                    DomainError, CombatNotSupported, PendingCheckExpected, ...
```

## 13.2 레이어 경계

- `domain/` + `ontology/` = 내부 풀 스키마. 레거시 계산 필드 포함.
- `pipeline/` = 턴 로직. 순수 파이썬, FastAPI 의존 없음 (테스트에서 TestClient 없이도 돌릴 수 있어야).
- `api/` = 얇은 어댑터. 라우팅·요청 검증·SSE 인코딩만.
- `mapping/to_front.py` = 유일한 프론트 노출 지점 (§14.13).
- `state/store.py` = 파일 I/O 경계. 파이프라인은 스토어를 통해서만 저장 상태에 접근.

## 13.3 오류 계층

`src/errors.py` 의 예외 계층. 파이프라인은 `DomainError` 만 던지며, API 레이어가 HTTP/SSE 로 매핑 (§12.3).

- `DomainError` — 기반 클래스.
  - `CombatNotSupported` — `action="combat"` 에 대해 P1 이 반환 (§10 미구현 구간).
  - `PendingCheckActive` — `/turn` 진입 시 `pending_check` 가 이미 설정되어 있음.
  - `PendingCheckExpected` — `/roll` 진입 시 `pending_check` 가 비어 있음.
  - `JudgeMalformed` — judge LLM 출력이 2회 연속 JSON 파싱 실패.
  - `LLMUnavailable` — judge/narrate 어느 단계든 LLM 연결 실패.
  - `PersistenceFailed` — 저장 I/O 실패 (원자 교체 이전/중 오류).

Pydantic 422 (요청 검증), HTTP 404 (game_id 없음) 은 FastAPI 기본 처리로 가며 `DomainError` 가 아니다.
