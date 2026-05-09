# 코드 지도

> 백엔드 모듈 구조와 레이어 경계, 오류 계층. 인덱스는 [01-overview.md](./01-overview.md). 프론트 경계는 [04-boundary.md](./04-boundary.md), 한 턴의 안쪽 흐름은 [02-runtime.md](./02-runtime.md), 전투·확장 기능은 [03-features.md](./03-features.md).

## 1. 모듈 구조

```
scenarios/                       repo 루트 peer (server·agency/story 공유). 작성은 로컬 fs 에서, Supabase 배포 시 `server/scripts/upload_scenarios.py` 가 같은 트리를 Storage 버킷에 업로드 — 버킷 레이아웃은 1:1 미러
  default/
    profile.json                 시나리오 메타: id, name, description (GET /profiles 응답 베이스)
    world.md                     세계관·톤
    start.json                   시작 장소·활성 퀘스트
    player_template.json         플레이어 캐릭터 시드
    characters/*.json            NPC 시드
    locations/*.json             장소 시드
    quests/*.json                퀘스트 시드
    chapters/*.json              챕터 시드 (quest_ids 묶음 + 진행 status)
    items/*.json                 아이템 시드
    races/*.json                 종족 시드
    skills/*.json                기술 시드 (racial + 시드 정의 learned)
    # campaigns/*.json           [P3] init.py 가 디렉터리 없으면 빈 dict 로 흡수
server/
  run_api.py                     FastAPI 진입점 (build_app / create_app / main). `_load_env` 가 `.env.<APP_ENV>` (기본 `dev`) → `.env.llama_cpp` → `.env.google` 순서로 dotenv 로드
  .env.dev                       APP_ENV=dev 의 공통 config (HOST/PORT/BASIC_AUTH_*/CORS_ORIGINS/SUPABASE_*/LLM_ROUTE_*)
  .env.release                   APP_ENV=release 의 같은 슬롯 (gitignored, 템플릿 = `.env.release.example`)
  .env.llama_cpp / .env.google   provider 블록 — `LLM_<NAME>_BASE_URL` · `_API_KEYS` · `_THINK_*` 카테고리. 두 파일 모두 두 모드에서 layered 로 읽힘
  src/
    domain/                      Pure data shapes — no logic, no I/O
      entities.py                Character, Race, Location, Item (WeaponEffect/ArmorEffect/ConsumableEffect 분기), Quest/QuestTrigger/QuestRewards, Chapter/ChapterProgress, Campaign, Connection, Equipment, Stats, Disposition, Skill/SkillCandidate/ActiveBuff, CombatBehavior, DeathSaveState
      state.py                   GameState container (엔티티 dict + game_id/profile + player_id + active_subject_id/active_quest_id + turn_count + pending_check + combat_state + pending_skill_candidates + previous_phase_signal + turn_log + recent_dialogue + log_entries + next_log_id) + CombatState (turn_order, surprise, enemy_ids, damage_dealt, player_target_id/skill_id/skill_used/intent — 사이클 사이 player 의도 보존). `graph()` / `invalidate_graph()` 메서드와 `_graph_cache` PrivateAttr 가 lazy 그래프 캐시 — Pydantic dump 에 안 실림
      clock.py                   day_phase(turn_count) → 새벽/오전/오후/밤; next_dawn_turn(turn_count) → 다음 새벽 boundary 까지 점프 (수면 회복용)
      memory.py                  Memory, TurnLogEntry, DialoguePair, PendingCheck, LogEntry union (gm/player/act/roll)
      types.py                   StatKey, Tier, Grade, Intent, tier_to_int (Tier → 1..7), STAT_PAIRS
      errors.py                  DomainError + PendingCheckActive/Expected, JudgeMalformed, LLMUnavailable, PersistenceFailed, ProfileNotFound, RaceNotFound, ProfileMalformed, LevelUpInvalid, InventoryInvalid, SkillInvalid

    rules/                       Tunable knobs + pure dice/DC math
      config.py                  frozen RULES (DC tiers, social, memory, log, time, combat, death, recovery, growth, skill, carry, trade, flee). frozen Pydantic — 변경 시 에러
      dc.py                      compute_required_roll, pick_dc, tier_mid_dc, compute_grade, social_bonus
      permissions.py             `set` 권한 매트릭스 단일 출처 ([02-runtime.md](./02-runtime.md) §6.1). engines/apply 와 agents/narrate/runner 가 같은 frozenset 을 공유 — 옛 손-mirror 시절의 `gender`/`location_id` 누락을 일원화로 막음

    engines/                     Pure logic — no LLM, no disk I/O
      apply.py                   `state_changes` (set / move / move_item / affinity) 검증·적용 + rejected[] 기록 + character_death/location_enter quest 훅
      combat.py                  apply_attack_to_defender / 명중·데미지 (D&D 5e mod + crit) / 이니셔티브 / NPC AI (highest_threat 는 combat_state.damage_dealt 누적값) / flee / 사망·revive·death-save / character_death quest 훅 / combat_state 라이프사이클 / surprise / start_combat 양측 companions 자동 합류
      growth.py                  level_up, xp_for_next_level, recalc_max_hp_mp, grant_xp, award_kill_xp, assert_pair_trade_invariant — 페어 트레이드 (STR↔CHA·DEX↔WIS·CON↔INT)
      skill.py                   cast (level/MP/range 검증, target self/single/area, grade_multipliers), tick_active_buffs, build_skill_from_candidate, compute_cast_grade, existing_skill_ids — attack/debuff 만 d20 굴림
      quest.py                   check_quests (character_death/location_enter/item_use single-fire), fail_triggers, locked→active, gold/exp/items 보상, chapter.progress
      recovery.py                attempt_rest — 위험도 굴림으로 풀회복 vs 인카운터, turn_count 를 next_dawn_turn 으로 점프, summon 콜백으로 LLM 즉석 적 폴백
      invariants.py              check.stats / check.character / check.scenario / check.state / check.quest_graph / Scenario dataclass — 시드·런타임 검증. LLM self-correction feedback 으로 재활용 가능한 한 줄 메시지 형식
      inventory/                 P3 §2.5 / §2.7 — 모듈 분할
        carry.py                 carry_capacity (STR × weight_per_strength), check_can_carry
        equipment.py             equip / unequip / auto_equip_slot (3슬롯: weapon/armor/accessory)
        trade.py                 buy / sell / 흥정 가격 (affinity_price_per_point × cap)
        use.py                   use (ConsumableEffect heal/damage/mp_restore/buff + on_use trigger + quest 훅)

    agents/                      LLM-driven — prompt + schema + semantics + runner per agent
      _runner.py                 공유 5회 자기교정 루프 + AgentSemanticError + read_prompt 헬퍼
      dc_judge/                  DC 판정 + 액션 분류 (17종 union, [02-runtime.md](./02-runtime.md) §1.1). prompt.md / schema.py / semantics.py / runner.py
      narrate/                   일반 서사 스트리밍. parser.py 가 본문 조각 + 끝 JSON 분리
      combat_narrate/            한 방 시네마틱 전투 서술 ([03-features.md](./03-features.md) §1). schema.py / runner.py / prompt.md. CombatNarrateInput / CombatRoundEvent / CombatStateSnapshot 으로 등급·이벤트·HP 스냅샷을 받아 3–5 문장 시네마틱 스트리밍
      skill_recommend/           §2.3 4단계 — level_up 직후 기술 후보 3개. 수치는 engines/skill 이 템플릿으로 채움
      encounter_summon/          §2.4 폴백 — sleep_encounters 풀이 비었을 때 LLM 으로 적 한 마리. 페어 트레이드 invariant 는 schema validator 가 강제

    ontology/                    derived view (구조·의미·config 관계 그래프 — 관계 SSOT)
      graph.py                   GameGraph (노드: character/item/location/quest/skill/race/chapter; 엣지: located_at, located_in, equips[slot], carries, has_companion, connects_to[difficulty,key_item_id], unlocks, gives_quest, required_by, kill_target_of, reward_of, belongs_to_race, knows_skill[source], racial_skill_of, member_of_chapter). out·in 양방향 인덱스 (`get_edges` / `get_in_edges`), `Edge.attrs` 에 부가 정보
      queries.py                 named traversal 헬퍼 — 호출부가 엣지 라벨 대신 의도(`inhabitants_of`, `inventory_of`, `equipment_of`, `connections_of`, `race_of`, `location_of`, `quests_given_by`, `giver_of`, `kill_targets_of`, `quests_killing`, `trigger_targets_of`, `quests_requiring`, `reward_items_of`, `quests_rewarding`, `locations_unlocked_by`, `chapter_of_quest`, `quests_in_chapter`, `container_of`, `companions_of`, `known_skills_of`, `items_in`)로 읽음. `flow/`·`context/`·`mapping/` 의 호출부는 `graph.get_edges(...)` 직접 호출 대신 이 헬퍼를 거친다
      target_view.py             target 노드에서 2홉 훑기. NPC = gives_quest + (quest 의) kill_target_of/required_by/reward_of, 추가로 NPC 자신이 kill_target_of 인 quests_kill_target 별도 필드. Location = required_by + (quest 의) giver/kill_targets/triggers/rewards. Item = unlocks/reward_of/located_in 1홉 (모두 이름·title 로 resolve)
      player_view.py             player 정체성(race/appearance/description/gender) 페이로드 — narrate / combat_narrate 용

    context/                     Prompt input builders
      layers.py                  build_world_layer / build_session_layer / build_history_layer (narrate 용)
      surroundings.py            build_surroundings (judge 용) — location, entities, corpses, equipment, skills (racial+learned), inventory, growth, skill_candidates, merchants, recent_npc, in_combat. corpses 는 같은 location 시체 + history 에 등장한 off-screen 시체 둘 다 묶음 ([02-runtime.md](./02-runtime.md) §3.4.1)

    flow/                        한 턴의 orchestration. SSE 이벤트 발행
      dirty.py                   Dirty 컨테이너 (entities/log/history/dialogue) + push_log_entry / push_turn_log / push_dialogue / next_log_id / flush / finalize
      buff_tick.py               tick_turn_buffs — 턴 경계에서 active_buff duration -1 (시계 산수는 없고 buff tick 만). 옛 이름 advance_turn → tick_turn_buffs, 옛 위치 flow/clock.py
      format.py                  로그 줄 builders (format_use_log / format_combat_end_text) + front_grade. 시네마틱 후행 정산은 combat_auto.format_outcome_summary 가 자체 발행 ([03-features.md](./03-features.md) §1.2)
      error_phrases.py           humanize_engine_error — 영문 엔진 에러 (`InventoryInvalid` / `LevelUpInvalid` / `SkillInvalid` 등) 를 한국어 한 줄 GM phrase 로 번역. 단일 substring 테이블, 폴백 `"지금은 그 행동이 통하지 않는다"`
      actions.py                 apply_attack_action / apply_skill_action (combat_auto sim 용 silent 헬퍼 — 부수효과만 적용, SSE/log 없음) + emit_use / emit_equip / emit_unequip / emit_level_up / emit_learn_skill / emit_trade / emit_roll_pending. 엔진 검증 실패 (DomainError) 를 catch 해서 humanize_engine_error 로 한국어 한 줄 변환 후 GM log 로 흘림
      subject.py                 refresh_active_subject — combat / roll / trade / 최근 대화 NPC 로 active_subject_id 동기화. corpse-aware: 죽은 NPC 도 pin 으로 살아남아 narrate anchor 유지
      combat_auto.py             run_auto_combat — 자동 사이클 (terminal outcome 까지 결판, HARD_CAP=50 안전장치) 시뮬: PlayerAction 매 라운드 반복 + NPC pick_npc_target AI + flee/death-save 자동 처리. AutoCombatResult 에 events + turn_events + outcome (victory/defeat/fled/downed) + per-enemy hit + player damage. build_narrate_input / format_outcome_summary 로 cinematic input + numeric act_line 산출. cap 파라미터는 ambush (cap=1) 전용 ([03-features.md](./03-features.md) §1)
      combat_phase.py            run_combat_player_turn (in-combat /turn dispatch) + start_combat_and_drive_auto (rest ambush + /turn CombatAction 진입) + _drive_auto_combat (sim → cinematic stream → numeric → combat_end SSE). 자동 모드 전용 — manual round 분기는 없음
      rest.py                    run_rest — recovery 호출 + summon 콜백 wiring
      turn.py                    run_turn 입구 — combat 활성이면 combat_phase.run_combat_player_turn 로 라우팅, 아니면 15개 action 분기 (chain 은 sequential dispatch). CombatAction/SummonCombatAction 은 _enter_combat_and_finalize 로 자동 사이클 진입
      intro.py                   run_intro — 게임 시작 시 첫 GM narration. judge 안 부르고 narrate 만
      roll.py                    run_roll — stat 굴림 해소 후 SSE 발사. 전투 중이면 굴림 후 자동 사이클 cap=1 로 NPC 1 라운드 추가 진행
      judge.py                   run_judge wrapper — JudgeMalformed / JudgeSemanticError → location roll 폴백
      narrate.py                 run_narrate wrapper — context layers + ontology target_view 합성
      memory_writer.py           narrate output.memory + memory_links → 캐릭터 memory 누적
      encounter.py               summon_encounter — encounter_summon agent 호출 → Character 생성·등록
      skill_recommend.py         recommend_skill_candidates — skill_recommend agent 호출 → engines/skill 의 build_skill_from_candidate 로 수치 채움

    persistence/                 Storage I/O — repo Protocols + 어댑터
      repo.py                    SaveRepo / ScenarioRepo Protocol (모두 async). flow/, context/, api/, init.py 가 인스턴스를 thread
      factory.py                 build_save_repo / build_scenario_repo — `SUPABASE_URL` 등 env 를 읽어 Supabase 어댑터 쌍을 unconditionally 빌드
      supabase.py                SupabaseSaveRepo (PostgREST: games / entities / log·history·dialogue_entries upsert + tail SELECT) + SupabaseStorageScenarioRepo (Storage 버킷 — world.md / seed JSON / local_profile_path 임시 디렉터리 materialization, 프로세스-라이프 캐시)
      _supabase_http.py          `_PostgREST` / `_Storage` httpx 래퍼 — Supabase 어댑터 전용
      local_fs.py                LocalFsSaveRepo / LocalFsScenarioRepo — 테스트가 tmp_path 로 직접 생성. SaveRepo 는 store.py 에 위임, ScenarioRepo 는 시나리오 디렉터리 트리를 직접 읽음
      store.py                   atomic 파일 IO 헬퍼 (load_game / save_meta / save_entity / append_*_entries — `.tmp` + `os.replace` + asyncio.Lock). LocalFsSaveRepo 의 내부 통로
      init.py                    init_game(profile, player, save_repo, scenario_repo) → 초기 GameState. Supabase 모드는 `copy_seed_into_game` 으로 시드를 entities 에 bulk-INSERT 후 player 캐릭터 합성

    mapping/
      to_front.py                to_front_state — GameState → 프론트가 기대하는 flat dict 8 슬롯 (`hero / subject / quest / place / combat / log / pendingCheck / storyGraph`). 합성 문자열·corpse-aware subject·pending_check wire 가공 모두 여기서 끝. 라벨 빌더는 labels.py, story-graph 사영은 story_graph.py 로 분리
      labels.py                  to_front 의 라벨 헬퍼 모음 — stat_label / gender_label / race_job_label / giver_with_location_label / difficulty_badge / RISK_PAYLOAD / stats_payload
      story_graph.py             to_story_graph — GameState → 플레이어 시점 reachable map + 현장 NPC + companions + active subject 만 추린 `{nodes, edges, summary}`. `state.storyGraph` 슬롯에 실려 `/session/{id}/state` · SSE `state` 로 나감
      josa.py                    한국어 조사 선택 헬퍼 — i_ga / eun_neun / eul_reul / gwa_wa. 받침(jongseong) 유무로 이/가, 은/는, 을/를, 와/과 가름. flow/format·to_front 의 한 줄 GM phrase 조립에 쓰임

    llm/
      client.py                  OpenAI 호환 스트리밍 LLMClient

    api/                         HTTP edge — thin adapter
      auth.py                    Basic Auth dependency
      deps.py                    get_save_repo / get_scenario_repo / get_llm / get_state Depends 헬퍼 (4 종). game_id 검증·404 매핑은 `get_state` 에서 일괄 처리되어 `/state` `/turn` `/roll` `/intro` 모두 공유
      schema.py                  request/response Pydantic
      sse.py                     이벤트 → 텍스트 직렬화, StreamingResponse 헬퍼
      routes/
        __init__.py              router — health 만 public, 나머지는 Basic Auth 게이트
        health.py                /health
        profiles.py              /profiles + 시드 스캔
        session.py               /session/init /session/{id}/state /turn /roll /intro
        debug.py                 /debug/complete

  migrations/
    001_init.sql                 Supabase 스키마 (games / entities / log·history·dialogue_entries). Supabase SQL editor 또는 `psql` 로 한 번 적용
  scripts/
    upload_scenarios.py          로컬 `scenarios/<profile>/` 트리를 Supabase Storage 버킷으로 업로드 (.env.<APP_ENV> 와 같은 버킷)
```

모든 게임 행동은 `/turn` 의 자연어 한 통로에 모이고 judge 가 분류한다 ([01-overview.md](./01-overview.md) §3.16). `storyGraph` 슬롯은 `state` 응답 안에 read-only 시점 노출만 — 별도 라우트는 없음.

## 2. 레이어 경계

레이어 의존 방향: **위 → 아래만**, 역방향 금지.

1. **domain / rules** — 데이터 모양 + 튜닝 노브. 아무것도 임포트 안 함 (rules 는 domain 만).
2. **engines** — 순수 로직. domain/rules 만 임포트. LLM·I/O 모름.
3. **agents** — LLM 호출 래퍼. domain/rules/llm 만 임포트.
4. **ontology** — domain 위에 얹는 derived view.
5. **context** — agents 입력 builder. domain/rules/engines 임포트.
6. **persistence** — 저장소 I/O 단일 통로 (`SaveRepo` / `ScenarioRepo` Protocol + Supabase·LocalFs 어댑터). domain 만 임포트.
7. **mapping** — `to_front_state` 단일 파일. domain/engines 임포트, 한국어 표시 데이터는 여기서 끝.
8. **flow** — 한 턴 orchestration. engines/agents/context/persistence 모두 묶음.
9. **api** — HTTP 어댑터. flow + mapping + persistence + schema. business logic 없음.

## 3. 오류 계층

`domain/errors.py`. flow/engines 는 `DomainError` 하위만 던지고, 두 갈래로 처리된다:

- **세션 lifecycle 오류** — HTTP/SSE 응답으로 직접 매핑 ([04-boundary.md](./04-boundary.md) §3 표).
- **액션 검증 오류** — `flow/actions.py` 가 catch 해서 `format.py` 가 한국어 한 줄로 변환 후 GM `log_entry` 로 흘림. 턴은 정상 종료, HTTP 응답 영향 없음.

`DomainError` — 기반 클래스. 하위:

세션 lifecycle (HTTP/SSE 매핑):
- `PendingCheckActive` — `/turn` 진입 시 `pending_check` 이미 설정. SSE error.
- `PendingCheckExpected` — `/roll` 진입 시 `pending_check` 비어 있음. SSE error.
- `JudgeMalformed` — judge LLM 출력 5회 연속 JSON 파싱 실패. SSE error.
- `LLMUnavailable` — LLM 연결 실패. SSE error.
- `PersistenceFailed` — 저장 I/O 실패. SSE error.
- `ProfileNotFound` — `/session/init` 의 `profile` 디렉터리 없음. HTTP 422.
- `RaceNotFound` — `/session/init` 의 `race_id` 가 그 프로필 race 목록에 없음. HTTP 422.
- `ProfileMalformed` — 프로필 시드(`start.json` 등)가 자기 안에 없는 id를 가리킴. HTTP 422.

액션 검증 (인-게임 GM log 로 흡수, HTTP 응답 영향 없음):
- `LevelUpInvalid` — `level_up` 페어 트레이드 / 캡 / 잔여 xp 검증 실패. `engines/growth.py` 가 발행, `flow/actions.py:emit_level_up` 이 catch.
- `InventoryInvalid` — `equip` / `unequip` / `buy` / `sell` 슬롯·요구치·무게·affinity·잔여 금화 검증 실패. `engines/inventory/` 가 발행, `flow/actions.py:emit_equip` / `emit_unequip` / `emit_trade` 등이 catch.
- `SkillInvalid` — 기술 `cast` 레벨·MP·사정거리·소유 검증 실패. `engines/skill.py` 가 발행, 자동 사이클 안의 `flow/combat_auto.py:_resolve_player_turn` 이 catch 해서 평타 폴백으로 흡수 (out-of-combat cast 통로는 폐기 — 모든 cast 는 combat 분기를 통과한다).

Pydantic 422 (요청 모양 검증), HTTP 404 (`game_id` 없음) 은 FastAPI 기본 처리로 가고 `DomainError` 가 아니다.
