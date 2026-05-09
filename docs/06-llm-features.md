# LLM 기능 5종

LLM이 담당하는 호출은 총 5종. 각각 `src/llm/calls/<name>/` 디렉터리 하나로 떨어져 있고, `LLM_ROUTE_<AGENT>` env 키로 모델/프로바이더가 라우팅된다. 모델별 thinking 모드는 provider 블록(`LLM_<NAME>_THINK_*`)에서 결정.

## 1. classify (judge)

플레이어 자연어 입력을 엔진이 처리할 수 있는 동사(Verb)로 분류.

- **입력**: `player_input`, `surroundings`(현재 위치/등장 NPC/소지품 등 그래프 뷰), `history`, `recent_dialogue`
- **출력**: `JudgeOutput` — `verb` + 옵션 modifier(예: `target_id`, `stat`, `tier`)
- **트리거**: 모든 턴의 첫 단계 (`game/flow/turn.py`)
- **이유**: pronoun 해석("그것을 든다"), 기습 판정 등 맥락 의존 분류라 build-up beat를 함께 본다

## 2. narrate

판정/엔진 결과를 받아 Korean 묘사를 streaming으로 뱉고, 끝나면 후속 추출(state_changes / memory / suggestions)을 한 번 더.

- **두 단계로 나뉘어 있음**:
  - `narrate_body` — body 텍스트 streaming. 클라가 실시간으로 받음.
  - `narrate_extract` — body 끝난 뒤 구조화 데이터 추출.
- **입력**: `world`, `player_view`, `target_view`, `surroundings`, `judge_result`, `grade`, `act_log_lines`, `recent_engine_events`
- **출력**: `NarrateOutput` — `turn_summary`, `state_changes[]`, `memorable`, `memory{}`, `memory_links{}`, `importance`, `suggestions[]`
- **트리거**: 일반 턴 마무리 (`turn.py`), 굴림 결과 (`roll.py`), 인트로 (`intro.py`), 레벨업 (`level_up.py`)
- **재시도 특이사항**: body는 이미 송신된 토큰을 회수할 수 없어, body delta가 한 줄이라도 나간 뒤 실패하면 그대로 raise. extract는 표준 self-correction 3회.
- **책임 경계**: 묘사 전용. 상태 변경 발사는 flow가 담당.

## 3. combat_narrate

자동 전투 sim이 한 판 끝까지 돌린 뒤 누적된 round trace를 받아 5~10문장짜리 시네마틱 한 덩어리로 묘사.

- **입력**: `outcome`(victory/defeat/downed/fled), `events[]`(라운드별 actor/action/grade/killed), `enemies_start/end`, `surprise` 등
- **출력**: streaming Korean 본문 한 덩어리
- **숫자 차단**: HP/damage 같은 수치는 schema에서 아예 빠져 있음. 프롬프트 룰만으로는 부족하다고 판단해 데이터 레이어에서 막음.
- **트리거**: 전투 phase (`combat_phase.py`)

## 4. summon

수면 인카운터에서 시드 풀이 비었을 때 즉석에서 적 한 명을 합성.

- **입력**: `world`, `location`, `player_level`, `available_races`, `requested_role`(옵션 — 플레이어가 특정 역할을 언급한 경우)
- **출력**: `EncounterSummonOutput` — 이름/외모/race_id/스탯/공격 우선순위
- **invariant**: 스탯은 pair-trade(`STR+CHA=20, DEX+WIS=20, CON+INT=20`)를 schema-level에서 강제
- **트리거**: `game/flow/rest.py`의 sleep_encounter에서 시드 풀이 빈 경우 (`game/flow/encounter.py:summon_encounter`)
- **실패 시**: 시드 풀이 비었고 summon도 실패 → 인카운터 없이 진행 (`SUMMON_FAILED_TEXT`)

## 5. recommend

레벨업 직전 플레이어에게 보여줄 기술 후보 1~3개를 생성.

- **입력**: `character`(현 플레이어 상태), `existing_skills`, `recent_turns`, `recent_inputs`
- **출력**: `SkillRecommendOutput` — `candidates: list[SkillCandidate]` (1~3개)
- **트리거**: `GET /session/{game_id}/level_up_preview` (`api/routes/session.py`)
- **실패 처리**: validation/transport 실패 시 빈 리스트 반환 → 클라가 "기술 선택 없음"으로 처리. 0<n<3이면 `recommend:short`로 진단만 남기고 넘김.

---

## 공통 인프라

- 모든 호출은 `src/llm/calls/_runner.py`의 self-correction 루프(retries=3) 위에서 실행. ValidationError나 semantic-check 실패 시 직전 응답 + 에러를 메시지 스트림에 덧붙여 다음 시도가 스스로 고치게 함.
- 프롬프트는 `src/locale/prompts/<agent>/prompt.<locale>.md`에 분리. `_kernel.<locale>.md`이 공통 룰(출력 언어, 어투, ID 위생, 세계관 어휘)을 잡고, agent 프롬프트와 `---`로 합쳐짐.
- 5xx/네트워크 에러는 같은 attempt 카운터를 공유. 예산 소진 시 `LLMUnavailable`로 매핑.
- 라우트 fallback(`LLM_ROUTE_<AGENT>_FALLBACK`)은 `RateLimitError`(쿼터) 시 1회 스위치하고 그 이후 retry 동안 유지.
