# CLAUDE.md

`backend/` 에서 Claude Code 가 일할 때 참고. 사용자용 셋업·라우트 표는 [README.md](./README.md), 설계 노트는 `../docs/01-overview.md`, 한 턴 내부 흐름은 `../docs/02-runtime.md`, 모듈 지도·오류 계층은 `../docs/05-codemap.md`.

## Layout

`backend/` 가 FastAPI 백엔드. venv·pyproject·requirements 는 repo 루트. pytest 는 루트에서, `run_api.py` 는 `backend/` cwd 에서 실행 (src 임포트 + dotenv 가 cwd 기준).

- `src/` — 애플리케이션 코드 (Architecture 참고).
- `tests/` — pytest (`asyncio_mode=auto`, `live` 마커는 LLM 도달 가능할 때만).
- `config/profiles/<profile>/` — 게임 시드 (`world.md`, `start.json`, `player_template.json`, `races/`, `locations/`, `items/`, `characters/`, `quests/`, `chapters/`).
- `../saves/` — 런타임 저장소 (repo 루트, `backend/` 의 peer). gitignored. 게임당 layout: `games/<game_id>/{meta.json, characters/<id>.json, items/<id>.json, ..., log.jsonl, history.jsonl, dialogue.jsonl}`.
- `run_api.py` — 진입점. env 읽고 FastAPI app 만들어 uvicorn 으로 띄움.
- `.env` — 필수 (fallback 없음, 누락 시 KeyError).

## Commands

```bash
# 루트에서
.venv/bin/python -m pytest -q                          # unit (live 스킵). pyproject 의 testpaths=backend/tests
RUN_LIVE=1 .venv/bin/python -m pytest -q               # LLM 살아 있을 때

# backend/ 에서
../.venv/bin/python run_api.py                         # 서버 띄우기 (cwd=backend, dotenv 가 backend/.env 읽음)
```

## Stack constraints

- **Python 3.12+**. Pydantic v2, FastAPI, async/await throughout. uvicorn dev server.
- **OpenAI 호환 LLM** at `BASE_URL` (현재 llama.cpp). `LLMClient.chat_stream` 이 스트리밍 primitive. agent 들이 자기 schema + retry 로 감쌈.
- **Pydantic 모델이 곧 schema**. 모든 상태 파일은 `GameState.model_validate_json(...)`. 수동 JSON munging 금지.
- **단일 프로세스** save lock (`state/store.py` 의 `asyncio.Lock`). 수평 확장은 P1 범위 밖.

## Architecture (layered)

상위는 하위에 의존, 역방향 금지. edge → core 순:

1. `api/` — FastAPI 표면. `routes.py` 가 protected router 정의 (`auth.py` 의 basic auth). `sse.py` 가 `AsyncIterator[dict]` → `text/event-stream` 변환. `schema.py` 가 request/response 모델. **business logic 없음**, glue 만.
2. `pipeline/` — 한 턴의 오케스트레이션. `turn.py` 가 `run_turn` / `run_roll` / `run_intro` (각각 `AsyncIterator[dict]` of SSE 이벤트) 노출. `judge.py`, `narrate.py`, `apply.py`, `memory_writer.py`, `dc.py`, `context.py` 가 `turn.py` 가 부르는 building block.
3. `llm_client/` — LLM transport (`client.py`) + agent 별 디렉터리 (`agents/dc_judge/`, `agents/narrate/`). 각 agent 디렉터리는 `prompt.md` (system), `schema.py` (입출력), `runner.py` (재시도-자기교정 호출 루프), `__init__.py` (public exports).
4. `ontology/` — `GameState` 위에 얹는 derived view. `graph.py` 가 entity relation 으로 typed edge graph 빌드 (located_at, equips, carries, connects_to, unlocks, gives_quest, kill_target_of, reward_of). `target_view.py` 가 narrate / judge prompt 용으로 한 entity 요약.
5. `mapping/to_front.py` — `GameState` → 프론트가 기대하는 flat dict 로 사영 (`hero`, `subject`, `quest`, `place`, `log`). **모든 한국어 날짜·기간·합성 문자열은 여기서 생성**, 프론트에서 안 만든다.
6. `state/` — `models.py` 가 `GameState` (단일 root container). `init.py` 가 profile seed + player 입력으로 새 `GameState` 빌드. `store.py` 가 atomic IO (`.tmp` + `os.replace`) + `.current` lifecycle.
7. `domain/` — 순수 데이터 모양. `entities.py` (Character, Item, Location, Race, Quest, Chapter, Campaign), `memory.py` (Memory, PendingCheck, LogEntry union, TurnLogEntry, DialoguePair), `types.py` (StatKey, Tier, Grade, Intent, Action literal).
8. `rules.py` — 단일 frozen `RULES` 인스턴스 (DC 티어, affinity delta, memory cap, log size, turn 당 시간, 전투·사망, 회복 (sleep_hours/encounter_chance)). 튜닝 노브는 여기, pipeline 코드에 흩뿌리지 말 것.
9. `errors.py` — `DomainError` + 서브클래스 (PendingCheckActive, PendingCheckExpected, JudgeMalformed, LLMUnavailable, PersistenceFailed, ProfileNotFound, RaceNotFound). 발견한 layer 가 raise, 응답을 만드는 boundary 가 catch.

## Conventions

### Korean-only

사용자에게 도달하는 모든 텍스트 (prompt, log, NPC 대사, 장소 이름, 클라이언트로 가는 에러 메시지) 는 한국어. localization layer 없음. 옛 `LocalizedText{ko,en}` 폐기.

### Stats / tiers / grades

- Stats key 는 ASCII 약어만: `STR/DEX/CON/INT/WIS/CHA`. judge `stat` enum 도 같은 키.
- Tier 는 7단계 한국어 라벨: `매우 쉬움 / 쉬움 / 보통 / 어려움 / 매우 어려움 / 전설 / 신화`. 영어 alias 없음.
- Grade 는 내부 5단계 (`critical_success / success / partial_success / failure / critical_failure`). 프론트로 나가는 `RollLogEntry.result` 는 `success | partial | fail` 로 collapse.

### Affinity

`-100..+100` (옛 0..100 폐기). `social.friendly_threshold = 50` 이면 `+social.roll_bonus = 2` 모디파이어 발동. 굴림 후 delta = `affinity_<grade>` 를 `intent` 로 mirror (hostile 은 부호 반전, deceptive 는 success 0 / failure ×2).

### Environment

`.env` 필수. 누락 시 startup 에서 `KeyError`. silent default 없음. Required: `HOST PORT BASE_URL BASIC_AUTH_USER BASIC_AUTH_PASS SAVES_DIR PROFILE_DIR`.

### Persistence

- Per-game 디렉터리: `../saves/games/<game_id>/`. Layout:
  - `meta.json` — 싱글톤 필드 (game_id, profile, player_id, world_time, turn_count, pending_check, active_*_id, next_log_id). 매 턴 끝마다 다시 쓰기 (commit point).
  - `<kind>/<id>.json` for each `kind` in `characters / items / locations / races / quests / chapters / campaigns`. 이 턴에 변경된 entity 만 다시 쓰기.
  - `log.jsonl`, `history.jsonl`, `dialogue.jsonl` — append-only one-line-per-entry. 디스크는 cap 없음. in-memory cap (`RULES.log.display_turns` / `memory.turn_log_size` / `memory.recent_dialogue_turns`) 은 tail load / prompt 공급 시에만 적용.
- `init_game` 이 `config/profiles/<profile>/` 의 seed entity 디렉터리를 game dir 로 verbatim 복사한 뒤 새 player character + meta 작성.
- Dirty tracking: `pipeline.turn._Dirty` 가 `(kind, id)` 쌍 (apply_changes / write_memories 에서) + 새 log/history/dialogue entry 누적. `_finalize` 가 flush — entity + jsonl append 먼저, meta 마지막.
- `saves/.current` 가 최신 `game_id` 한 줄. `GET /session/current` 가 읽음.
- Log entry 는 monotonic id (`GameState.next_log_id`). 프론트는 `log_entry` SSE 와 `state.log` 둘 다 도착했을 때 id 로 dedupe.
- per-entity `memories` cap 은 `RULES.memory.cap`, entity 모델 안에서 write 시점에 적용 (cap 이 entity 파일과 함께 이동).
- 단일 프로세스 save lock (`state/store.py` 의 `asyncio.Lock`) 이 프로세스 안 파일 쓰기 직렬화. 수평 확장은 P1 범위 밖. flush 도중 크래시 시 entity / jsonl 쓰기는 commit, `meta.json` 만 stale — 다음 턴에서 복구됨.

### Memory writes (post-turn)

- per-entity 시점: `NarrateOutput.memory: dict[entity_id, "그 시점 한 줄"]`. **player memory 는 1인칭 ("내가 …")**, NPC memory 는 그 NPC POV. 같은 문자열을 양쪽에 적지 말 것.
- LLM 은 `player_input` 에 충실해야 함 (escalation / 과장 금지).
- `memorable=true` 는 scene-shifting 사건 (결정, 약속, 위협, 거래, 첫인상). 잡담은 `false`.
- `memory_links: {entity_id: target_id}` 가 어느 Subject 패널에서 그 기억이 노출될지 결정. 빠진 항목은 `target_id=None`.

### Agent retry policy

각 agent (judge, narrate) 가 자기교정 루프 (`retries=5`). `ValidationError` / 의미 검증 실패 시 직전 응답 + 에러를 message stream 에 append → 다음 시도가 스스로 교정. 5회 후 마지막 에러 종류로 raise. pipeline 이 도메인 에러로 매핑.

### state_changes

5종만 (`set / set_time / move / move_item / affinity`). 각각 `pipeline/apply.py` 안에 자체 permission matrix. 금지된 `set` 필드는 per-change silently reject, 나머지 batch 는 그대로 적용. 시간은 역행 금지.

### SSE event shape

`{"type": "...", "data": {...}}` per event. 종류: `judge / pending_check / narrative_delta / log_entry / state / done / error`. `done` 은 **자동 append 안 함**. `roll` 분기의 `run_turn` 은 `pending_check` 후 종료, 클라이언트는 stream-close 를 신호로 본다.

### Tests

- Unit 은 LLM 없이 동작. live 는 `RUN_LIVE=1` 일 때만.
- live 는 `BASE_URL` (env, 기본 `http://localhost:8000/v1`) 도달 가능해야 함.
- `tests/conftest.py` 가 `fresh_state` (빈 `GameState`) 제공.
