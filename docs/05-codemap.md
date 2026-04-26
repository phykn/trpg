# 코드 지도

> 백엔드 모듈 구조와 레이어 경계, 오류 계층. 인덱스는 [01-overview.md](./01-overview.md). 프론트 경계는 [04-boundary.md](./04-boundary.md), 한 턴의 안쪽 흐름은 [02-runtime.md](./02-runtime.md), 전투·확장 기능은 [03-features.md](./03-features.md).

[04-boundary.md](./04-boundary.md) §1 의 매핑이 어느 코드 파일에 있는지, 그 주변 모듈이 어떻게 정리돼 있는지.

## 1. 모듈 구조

```
backend/
  run_api.py                     FastAPI 진입점 (build_app, main)
  .env                           HOST, PORT, BASE_URL, BASIC_AUTH_USER, BASIC_AUTH_PASS, SAVES_DIR, PROFILE_DIR
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
    rules.py                     DC·시간·소셜·메모리·로그·전투·사망·회복 수치 (P3 회복: encounter_chance / sleep_hours, 거래·성장은 P3 후속). frozen Pydantic — 변경 시도하면 에러.
    api/
      routes.py                  /profiles, /session/current, /session/init, /session/{id}/state, /turn, /roll, /level-up
      schema.py                  네트워크로 주고받는 Pydantic 모델 (ProfileListResponse, InitRequest/Response, TurnRequest, RollRequest)
      sse.py                     이벤트를 텍스트로 직렬화, StreamingResponse 헬퍼
    pipeline/
      judge.py                   DC 판정 에이전트 호출 + JSON 파싱 + target 검증
      narrate.py                 내러티브 에이전트 호출 + 응답 스트림 파싱 (본문 조각 + 끝에 붙는 JSON)
      apply.py                   `state_changes` 검증·적용 + `rejected[]` 기록
      context.py                 surroundings / target_view / history 모아 묶음
      dc.py                      sigmoid DC, tier → DC, social_bonus, grade 계산
      combat.py                  P2 전투 엔진 (LLM 미사용). 명중·데미지 (시그모이드 + dual-wield + crit) / 이니셔티브 / NPC AI / flee / 사망·revive·death-save / combat_state 라이프사이클 / surprise 첫 라운드 skip
      recovery.py                P3 §2.4 회복 (rest). 위험도 굴림으로 풀회복 vs 인카운터 분기, sleep_hours 만큼 world_time 점프, sleep_encounters 풀에서 enemy 선택
      growth.py                  P3 §2.3 성장 (level_up). xp_for_next_level 곡선, 페어 트레이드 (STR↔CHA·DEX↔WIS·CON↔INT), recalc_max_hp_mp, grant_xp, assert_pair_trade_invariant
      turn.py                    `run_turn` / `run_roll` 흐름 지휘 (SSE 이벤트 방출). combat_state 살아있으면 combat 분기로 라우팅
    state/
      store.py                   `load_game` / `save_game` (원자적 파일 I/O + 동시 쓰기 방지 Lock) + `.current` 읽기/쓰기
      init.py                    프로필 + 캐릭터 생성 요청 → 초기 GameState
      models.py                  GameState 컨테이너 (엔티티 dict + world_time + pending_check + combat_state + turn_log + recent_dialogue + log_entries + active_subject_id + active_quest_id + player_id)
    ontology/
      graph.py                   구조 관계·의미 관계·config 관계 — 그래프 엣지 종류
      target_view.py             target 노드에서 1~2 단계 떨어진 이웃까지 훑기
    domain/
      entities.py                Character, Race, Location, Item, Quest, QuestTrigger, QuestRewards, Connection, Equipment, Stats
      memory.py                  Memory, TurnLogEntry, DialoguePair, PendingCheck, LogEntry (gm/player/act/roll union)
      types.py                   StatKey, Tier, Grade, Intent, Action enum (pass / roll / combat / rest / clarify / reject)
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
    errors.py                    DomainError + PendingCheckActive/Expected, JudgeMalformed, LLMUnavailable, PersistenceFailed, ProfileNotFound, RaceNotFound, LevelUpInvalid
```

## 2. 레이어 경계

- `domain/` + `ontology/` = 게임이 다루는 모든 데이터 모양 (스키마) 의 정의.
- `pipeline/` = 한 턴의 로직. 순수 파이썬이라 FastAPI 없이도 돌아간다 — 단위 테스트에서 TestClient 안 띄워도 직접 호출 가능해야 함.
- `api/` = HTTP 입출구의 얇은 어댑터. URL 라우팅, 요청 모양 검증, SSE 응답 포장만 담당.
- `mapping/to_front.py` = 프론트로 데이터를 내보내는 단 하나의 파일 ([01-overview.md](./01-overview.md) §3.13).
- `state/store.py` = 디스크 I/O 의 유일한 통로. 파이프라인은 이 모듈을 거쳐야 저장 상태에 닿음.

## 3. 오류 계층

`src/errors.py` 의 예외 계층. 파이프라인은 `DomainError` 하위 클래스만 던지고, API 레이어가 그걸 HTTP/SSE 응답으로 매핑한다 ([04-boundary.md](./04-boundary.md) §3 표).

- `DomainError` — 모든 도메인 에러의 기반 클래스.
  - `PendingCheckActive` — `/turn` 진입 시 `pending_check` 가 이미 설정돼 있을 때.
  - `PendingCheckExpected` — `/roll` 진입 시 `pending_check` 가 비어 있을 때.
  - `JudgeMalformed` — judge LLM 출력이 2번 연속 JSON 파싱 실패.
  - `LLMUnavailable` — judge / narrate 어느 단계에서든 LLM 연결 실패.
  - `PersistenceFailed` — 저장 I/O 실패 (원자 교체 직전 또는 도중 오류).
  - `LevelUpInvalid` — `/level-up` 요청이 페어 트레이드 / 캡 / 잔여 xp 검증 실패. API 가 422 로 매핑.

Pydantic 422 (요청 모양 검증), HTTP 404 (`game_id` 없음) 은 FastAPI 기본 처리로 가고 `DomainError` 가 아니다.
