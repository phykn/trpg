# 코드 지도

> 백엔드 모듈 구조와 레이어 경계, 오류 계층. 인덱스는 [01-overview.md](./01-overview.md). 프론트 경계는 [04-boundary.md](./04-boundary.md), 한 턴의 안쪽 흐름은 [02-runtime.md](./02-runtime.md), 전투·확장 기능은 [03-features.md](./03-features.md).

## 1. 모듈 구조

```
scenarios/                       repo 루트 peer (backend·agency/story 공유). PROFILE_DIR 가 가리킴
  default_cli/
    profile.json                 시나리오 메타: id, name, description (GET /profiles 응답 베이스)
    world.md                     세계관·톤
    start.json                   시작 장소·활성 퀘스트·world_time
    player_template.json         플레이어 캐릭터 시드
    characters/*.json            NPC 시드
    locations/*.json             장소 시드
    quests/*.json                퀘스트 시드
    items/*.json                 아이템 시드
    races/*.json                 종족 시드
backend/
  run_api.py                     FastAPI 진입점 (build_app, main)
  .env                           HOST, PORT, BASE_URL, BASIC_AUTH_USER, BASIC_AUTH_PASS, SAVES_DIR, PROFILE_DIR
  src/
    domain/                      Pure data shapes — no logic, no I/O
      entities.py                Character, Race, Location, Item, Quest, QuestTrigger, QuestRewards, Connection, Equipment, Stats, Skill, ActiveBuff, CombatBehavior, CombatState, DeathSaveState
      state.py                   GameState container (엔티티 dict + world_time + pending_check + combat_state + turn_log + recent_dialogue + log_entries + pending_skill_candidates + player_id)
      memory.py                  Memory, TurnLogEntry, DialoguePair, PendingCheck, LogEntry union (gm/player/act/roll)
      types.py                   StatKey, Tier, Grade, Intent
      errors.py                  DomainError + PendingCheckActive/Expected, JudgeMalformed, LLMUnavailable, PersistenceFailed, ProfileNotFound, RaceNotFound, ProfileMalformed, LevelUpInvalid, InventoryInvalid, SkillInvalid

    rules/                       Tunable knobs + pure dice/DC math
      config.py                  frozen RULES (DC tiers, social, memory, log, time, combat, death, recovery, growth, skill, carry, trade, flee). frozen Pydantic — 변경 시 에러
      dc.py                      sigmoid_required_roll, tier_to_int, pick_dc, compute_grade, social_bonus

    engines/                     Pure logic — no LLM, no disk I/O
      apply.py                   `state_changes` (set / set_time / move / move_item / affinity) 검증·적용 + rejected[] 기록 + character_death/location_enter quest 훅
      combat.py                  명중·데미지 (sigmoid + dual-wield + crit) / 이니셔티브 / NPC AI (highest_threat 는 combat_state.damage_dealt 누적값) / flee / 사망·revive·death-save / character_death quest 훅 / combat_state 라이프사이클 / surprise / start_combat 양측 companions 자동 합류
      growth.py                  level_up, xp_for_next_level, recalc_max_hp_mp, grant_xp, assert_pair_trade_invariant — 페어 트레이드 (STR↔CHA·DEX↔WIS·CON↔INT)
      skill.py                   cast (level/MP/range 검증, target self/single/area, grade_multipliers), tick_active_buffs, build_skill_from_candidate, compute_cast_grade — attack/debuff 만 d20 굴림
      quest.py                   check_quests (character_death/location_enter/item_use single-fire), fail_triggers, locked→active, gold/exp/items 보상, chapter.progress
      recovery.py                attempt_rest — 위험도 굴림으로 풀회복 vs 인카운터, sleep_hours world_time 점프, summon 콜백으로 LLM 즉석 적 폴백
      inventory/                 P3 §2.5 / §2.7 — 모듈 분할
        carry.py                 carry_capacity (STR × weight_per_strength), check_can_carry
        equipment.py             equip / unequip / equip_auto (slot 자동 결정) / two_handed 처리
        trade.py                 buy / sell / 흥정 가격 (affinity_price_per_point × cap)
        use.py                   use (ConsumableEffect heal/damage/mp_restore/buff + on_use trigger), use_with_quest_hook

    agents/                      LLM-driven — prompt + schema + semantics + runner per agent
      _runner.py                 공유 5회 자기교정 루프 + AgentSemanticError + read_prompt 헬퍼
      dc_judge/                  DC 판정 (action 14종 분기). prompt.md / schema.py / semantics.py / runner.py
      narrate/                   서사 스트리밍. parser.py 가 본문 조각 + 끝 JSON 분리
      skill_recommend/           §2.3 4단계 — level_up 직후 스킬 후보 3개. 수치는 engines/skill 이 템플릿으로 채움
      encounter_summon/          §2.4 폴백 — sleep_encounters 풀이 비었을 때 LLM 으로 적 한 마리. 페어 트레이드 invariant 는 schema validator 가 강제

    ontology/                    derived view (구조·의미·config 관계 그래프)
      graph.py                   located_at / equips / carries / connects_to / unlocks / gives_quest / kill_target_of / reward_of
      target_view.py             target 노드에서 1~2 단계 이웃 훑기

    context/                     Prompt input builders
      layers.py                  build_world_layer / build_session_layer / build_history_layer (narrate 용)
      surroundings.py            build_surroundings (judge 용) — location, entities, equipment, skills (racial+learned), inventory, growth, skill_candidates, merchants, in_combat

    flow/                        한 턴의 orchestration. SSE 이벤트 발행
      dirty.py                   Dirty 컨테이너 (entities/log/history/dialogue) + push_log_entry / push_turn_log / push_dialogue / advance_time / next_log_id / flush / finalize
      format.py                  로그 줄 builders (format_attack_log / format_skill_log / format_use_log / format_combat_end_text / format_roll_announce) + GRADE_LABEL / front_grade / label_for_target / choose_bonus_target
      actions.py                 emit_attack / emit_skill_cast / emit_use / emit_equip / emit_unequip / emit_level_up / emit_learn_skill / emit_trade / emit_roll_pending
      combat_phase.py            run_combat_npc_phase / start_combat_and_run_npc_phase / run_combat_player_turn (death-save / combat / flee / pass / use / equip 분기)
      rest.py                    run_rest — recovery 호출 + summon 콜백 wiring
      turn.py                    run_turn 입구 — combat 활성이면 combat_phase 로 라우팅, 아니면 14개 action 분기
      intro.py                   run_intro — 게임 시작 시 첫 GM narration
      roll.py                    run_roll — pending_check 해소 후 narrate, 전투 중이면 NPC phase 재개
      judge.py                   run_judge wrapper — JudgeMalformed / JudgeSemanticError → location roll 폴백
      narrate.py                 run_narrate wrapper — context layers + ontology target_view 합성
      memory_writer.py           narrate output.memory + memory_links → 캐릭터 memory 누적
      encounter.py               summon_encounter — encounter_summon agent 호출 → Character 생성·등록
      skill_recommend.py         recommend_skill_candidates — skill_recommend agent 호출 → engines/skill 의 build_skill_from_candidate 로 수치 채움

    persistence/                 Disk I/O
      store.py                   load_game / save_meta / save_entity / append_*_entries (atomic .tmp + os.replace + asyncio.Lock) + .current 읽기/쓰기
      init.py                    프로필 + 캐릭터 생성 요청 → 초기 GameState

    mapping/
      to_front.py                to_front_state — GameState → 프론트가 기대하는 flat dict (한국어 날짜·합성 문자열 여기서 끝)

    llm/
      client.py                  OpenAI 호환 스트리밍 LLMClient

    api/                         HTTP edge — thin adapter
      app.py                     (없음 — run_api.py 의 build_app 가 동등 역할)
      auth.py                    Basic Auth dependency
      deps.py                    get_state / get_llm / get_saves_dir / get_profile_dir Depends 헬퍼
      schema.py                  request/response Pydantic
      sse.py                     이벤트 → 텍스트 직렬화, StreamingResponse 헬퍼
      routes/
        __init__.py              router — health 만 public, 나머지는 Basic Auth 게이트
        health.py                /health
        profiles.py              /profiles + 시드 스캔
        session.py               /session/current /session/init /session/{id}/state /turn /roll /intro
        growth.py                /level-up /learn-skill
        inventory.py             /equip /unequip /buy /sell /cast /use
        debug.py                 /debug/complete

  data/ (= ../saves/)            게임당 디렉터리 (`games/<game_id>/...`) + `.current`
```

## 2. 레이어 경계

레이어 의존 방향: **위 → 아래만**, 역방향 금지.

1. **domain / rules** — 데이터 모양 + 튜닝 노브. 아무것도 임포트 안 함 (rules 는 domain 만).
2. **engines** — 순수 로직. domain/rules 만 임포트. LLM·I/O 모름.
3. **agents** — LLM 호출 래퍼. domain/rules/llm 만 임포트.
4. **ontology** — domain 위에 얹는 derived view.
5. **context** — agents 입력 builder. domain/rules/engines 임포트.
6. **persistence** — 디스크 I/O 단일 통로. domain 만 임포트.
7. **mapping** — `to_front_state` 단일 파일. domain/engines 임포트, 한국어 표시 데이터는 여기서 끝.
8. **flow** — 한 턴 orchestration. engines/agents/context/persistence 모두 묶음.
9. **api** — HTTP 어댑터. flow + mapping + persistence + schema. business logic 없음.

## 3. 오류 계층

`domain/errors.py`. flow/engines 는 `DomainError` 하위만 던지고, api 가 HTTP/SSE 응답으로 매핑한다 ([04-boundary.md](./04-boundary.md) §3 표).

- `DomainError` — 기반 클래스.
  - `PendingCheckActive` — `/turn` 진입 시 `pending_check` 이미 설정.
  - `PendingCheckExpected` — `/roll` 진입 시 `pending_check` 비어 있음.
  - `JudgeMalformed` — judge LLM 출력 5회 연속 JSON 파싱 실패.
  - `LLMUnavailable` — LLM 연결 실패.
  - `PersistenceFailed` — 저장 I/O 실패.
  - `ProfileNotFound` — `/session/init` 의 `profile` 디렉터리 없음. 422.
  - `RaceNotFound` — `/session/init` 의 `race_id` 가 그 프로필 race 목록에 없음. 422.
  - `ProfileMalformed` — 프로필 시드(`start.json` 등)가 자기 안에 없는 id를 가리킴. 422.
  - `LevelUpInvalid` — `/level-up` 페어 트레이드 / 캡 / 잔여 xp 검증 실패. 422.
  - `InventoryInvalid` — `/equip` `/unequip` `/buy` `/sell` 슬롯·요구치·무게·affinity·잔여 골드 검증 실패. 422.
  - `SkillInvalid` — `/cast` 레벨·MP·사정거리·소유 검증 실패. 422.

Pydantic 422 (요청 모양 검증), HTTP 404 (`game_id` 없음) 은 FastAPI 기본 처리로 가고 `DomainError` 가 아니다.
