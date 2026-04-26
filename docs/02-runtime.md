# 런타임 메커닉 (§1-§7)

> 한 턴이 어떻게 흐르고, 엔진과 에이전트가 그 사이 무엇을 주고받는지. 인덱스·Phase 범위는 [01-overview.md](./01-overview.md). 다른 그룹은 [03-features.md](./03-features.md) (§1-§2 전투·확장), [04-boundary.md](./04-boundary.md) (프론트 경계), [05-codemap.md](./05-codemap.md) (백엔드 코드 지도).

위에서 아래로 읽으면 다음 순서:

1. **§1 에이전트** — 누가 결정하나 (DC판정 LLM, 내러티브 LLM)
2. **§2 파이프라인** — 한 턴이 어떻게 진행되나
3. **§3 컨텍스트 레이어** — 에이전트에 무엇을 보여주나
4. **§4 온톨로지** — 그 컨텍스트가 어떤 그래프로 조립되나
5. **§5 DC 시스템** — 판정 수치 계산
6. **§6 상태 업데이트** — 결정이 어떻게 게임 상태에 박히나
7. **§7 메모리 시스템** — 무엇이 다음 턴까지 남나

---

## 1. 에이전트

LLM 을 두 개로 쪼갠다.

- **DC판정** — "어떤 종류의 행동인가, 얼마나 어려운가" 만 분류한다. 짧은 JSON 출력.
- **내러티브** — "그래서 어떻게 됐는지" 를 서술한다. 긴 한국어 출력.

왜 둘로 나누나: 한 LLM 에게 분류 + 서술을 같이 시키면 둘 다 어설프게 한다. 출력 형식·프롬프트 길이·실패 모드가 정반대라 같은 모델 한 호출로 합치기 어렵다. 자세한 이유는 [01-overview.md](./01-overview.md) §1.

### 1.1 DC판정 에이전트

**역할**: 플레이어 입력을 해석하여 판정 여부, 난이도 등급, 관련 스탯, 대상을 결정.

**입력**:
- `player_input`: 플레이어 원문 텍스트
- `surroundings`: 현재 장소 + 주변 엔티티 상태 태그 (§3.4.1)

**출력**:
```json
{
  "action": "pass" | "roll" | "combat" | "rest" | "clarify" | "reject",
  "tier": "매우 쉬움" | "쉬움" | "보통" | "어려움" | "매우 어려움" | "전설" | "신화",
  "stat": "STR" | "DEX" | "CON" | "INT" | "WIS" | "CHA",
  "targets": ["<entity_id>", "<entity_id>"],
  "question": "되물을 내용 (clarify 일 때만)"
}
```

`action` 만 항상 존재. `tier`/`stat`/`targets` 는 `roll | combat` 일 때만, `question` 은 `clarify` 일 때만 채워진다 (pass/reject 는 모두 부재).

`targets` 는 판정 대상 ID 배열. 단일 대상이면 길이 1, 복수 대상(예: 두 경비병 동시 설득)이면 엔진이 actor 의 affinity 가 가장 낮은 대상을 기준으로 `social_bonus` 를 계산한다.

**action 유형**:

| action | 의미 | 다음 단계 |
|---|---|---|
| `pass` | 판정 불필요한 인-캐릭터 행동 (이동, 인사, 정가 구매 등) | target_view 없이 바로 내러티브 |
| `roll` | 주사위 필요 | 엔진이 DC 계산 → `pending_check` 저장 → 프론트 주사위 버튼 → `/roll` |
| `combat` | 일반 전투 행동 | [P2] 엔진이 `combat_state` 부팅·이니셔티브 굴림 → SSE `combat_start` → NPC 차례 자동 진행 → 다음 player 차례에서 멈춤. 라운드 본문은 LLM 안 부르고 엔진이 결정론으로 진행 (한국어 묘사 LLM 화는 후속) |
| `rest` | 잠·야영 (긴 휴식) | [P3] 엔진이 location.sleep_risk 굴림 → 풀회복 (HP/MP max + world_time +sleep_hours) 또는 sleep_encounters 풀에서 적 뽑아 surprise=enemy 로 combat 부팅 ([03-features.md](./03-features.md) §2.4) |
| `clarify` | 해석 불가 / 복합 행동 | 플레이어에게 되물음, 파이프라인 재시작 |
| `reject` | 인-캐릭터 입력이 아님 — 시스템 공격(프롬프트 인젝션, 메타 질문), OOC 잡담, 무의미 입력 | 인-게임 표현으로 흡수 (아래 reject 처리 참고) |

**reject 처리**: 내러티브 에이전트에 surroundings + reject 가이드만 전달 → narrator 가 인-게임 표현("알 수 없는 힘에 막힌다" 등)으로 흡수. `state_changes=[]`·`memorable=false` 강제. turn_log·recent_dialogue 에는 일반 턴처럼 append — "흔적 안 남김" 은 게임 상태/NPC 기억 한정이고, narrator 컨텍스트는 OOC 시도까지 자연스럽게 이어쓰려면 보존이 필요.

**규칙**:
- 매 턴 호출 (전투/비전투 무관)
- 명시적 대상 없으면 현재 location 이 기본값
- `stat` 은 행동의 성격으로 결정 (DC판정은 플레이어 수치를 안 봄)
- **히스토리·세션·월드 레이어를 받지 않는다**. 오직 현재 장면(`surroundings`) 만으로 판정. 장기 맥락·과거 턴 요약·엔티티 메모리는 내러티브 전용 (§3, [01-overview.md](./01-overview.md) §3.12).

### 1.2 내러티브 에이전트

**역할**: 이야기 서술 + 턴 요약 + 메모리 판정.

**입력**:
- `player_input`: 플레이어 원문
- `judge_result`: DC판정 에이전트 출력
- `grade`: 주사위 결과 등급 (roll/combat 일 때만, §5.3)
- `world_layer`: 세계관 (§3.1)
- `session_layer`: 챕터/퀘스트 진행 상태 (§3.2). `chapter.{title, summary, quests[]}` + `quests[].{title, summary, giver, goals, conditions}` + `world_time`. progress 숫자는 안 보냄. [P3 에서 Campaign 추가]
- `history_layer`: 최근 N턴 대화 + 이전 턴 요약 (§3.3)
- `target_view`: 대상 엔티티 기준 그래프 1-2홉 (§3.4.2). pass·reject 면 surroundings 만 (target_view 없음). reject 일 땐 추가로 reject 가이드(인-게임 방식으로 막으라는 지시)가 system 프롬프트에 합쳐짐.

**출력**: 토큰 단위로 흘려보낸다(스트리밍). 한국어 2인칭 본문 3-6문장을 먼저 보내고, 구분자(`---JSON---`) 뒤에 메타 JSON을 붙인다.

```
<서술 본문>
---JSON---
{
  "turn_summary": "경비병 설득 성공",
  "state_changes": [
    {"type": "affinity", "actor": "player_01", "target": "guard_01", "grade": "success", "intent": "friendly"}
  ],
  "memorable": true,
  "memory_targets": ["guard_01", "player_01"],
  "memory": "플레이어가 뇌물을 줘서 통과시켜줌",
  "importance": 3,
  "memory_links": {"guard_01": "player_01", "player_01": "guard_01"}
}
```

**필드**:
- `turn_summary`: turn_log 에 저장될 이 턴 한 줄 요약 (대상/결과 명시, ~60자). 챕터/퀘스트의 누적 진행 요약(§3.2 의 `summary`) 과 다름 — 이건 turn-level 한 줄.
- `state_changes`: 엔진에 전달할 상태 변경 목록 (§6)
- `memorable`: 이 턴이 NPC/장소/플레이어 중 누군가의 장기 기억(§7) 에 남을 만한지
- `memory_targets`: 기억을 저장할 엔티티 ID 목록 (복수 가능)
- `memory`: 저장할 기억 내용 (`memorable=true` 일 때 필수). `memory_targets` 가 비면 엔진이 `memorable=false` 로 강등하고 저장 안 함.
- `importance`: 기억 중요도 (1: 사소, 2: 보통, 3: 중요)
- `memory_links`: 각 entity 의 기억이 누구를 향한 것인지 매핑 (`{entity_id: target_id}`). `memory_targets` 의 entity 마다 한 줄. 여기 빠진 entity 의 기억은 `target_id=None` 으로 박혀 Subject.known 산출 ([04-boundary.md](./04-boundary.md) §1) 에서 자연스럽게 빠진다. 1명짜리 memory_targets (예: 플레이어 혼자 깨달음) 는 보통 비워둠. 자동 추론 안 함 — 1:1·다대다 모두 narrator 가 명시.

**서술 규율**:
- 수치/확률/DC 를 본문에 노출하지 않음 ("설득을 시도한다" ○, "DC 15 설득" ✗)
- HP·데미지·XP·골드는 엔진이 이미 적용. 본문에서 숫자로 다시 제시하지 않음.
- NPC 의 말투·대사는 `target_view` 의 `tone_hint`, `disposition` 을 따름.
- `state_changes` 타입은 `set | set_time | move | move_item | affinity` 5종만. 이 5종이 아니거나 형식이 어긋난 항목은 `apply_changes` 가 `rejected[]` 로 따로 빼두고 적용하지 않는다.

### 1.3 LLM 런타임

- 단일 모델, 단일 `BASE_URL` (llama.cpp OpenAI-compat 서버). judge·narrate 모두 같은 클라이언트.
- `src/llm/client.py` 가 `LLMClient` 노출.
- 시스템 프롬프트는 `src/llm/prompts/judge.md`, `src/llm/prompts/narrate.md` 에서 로드.

---

## 2. 파이프라인

위 두 에이전트가 한 턴 안에 어떻게 엮이는지.

### 2.1 1턴 흐름

```
플레이어 입력
  ↓
엔진: surroundings 조립
  ↓
DC판정 에이전트 호출
  │
  ├─ clarify → SSE log_entry(act, question) → done. 다음 /turn 에서 재시작 (narrator 호출 없음)
  │
  ├─ roll    → 엔진: target 검증 → DC·mod·required_roll 계산
  │             → pending_check 저장 → SSE pending_check → 스트림 종료
  │             (프론트 주사위 버튼 활성 → 플레이어 주사위 → /roll 진입)
  │             /roll: grade 판정 → target_view 조립 → 내러티브 호출 → 후처리 ↓
  │
  ├─ combat  → [P2] 엔진: combat_state 부팅 (이니셔티브 굴림 + enemy_ids 박기)
  │             → SSE combat_start → NPC 차례 자동 진행 (각 차례마다 SSE combat_turn)
  │             → 종료 조건이면 SSE combat_end → done
  │             → 살아있으면 player 차례 도달 시 done. 다음 /turn 에서 player 행동 처리.
  │             (라운드 본문은 LLM 안 부르고 결정론, narrator 호출 없음)
  │
  ├─ pass    → target_view 없이 내러티브 호출 (surroundings 만) → 후처리 ↓
  │
  └─ reject  → target_view 없이 내러티브 호출 (surroundings + reject 가이드) → 후처리 ↓

reject 전용 추가 단계 (후처리 직전):
  엔진이 narrator 출력의 state_changes 를 비우고 memorable=false 로 강제

후처리 (narrator 가 돈 분기 공통):
  엔진: state_changes 검증 → 유효 변경 적용, 무효는 rejected[] 로깅
  엔진: turn_summary 를 turn_log 에 저장, (player_input, narrative) 를 recent_dialogue 에 append
  엔진: memorable 이면 memory 를 memory_targets[].memories[] 에 저장
  ↓
  SSE state (전체 슬롯) → save_game → SSE done
```

### 2.2 두 단계 턴 (pending_check)

`roll` 분기는 **한 턴을 두 HTTP 호출로 쪼갠다** (`/turn` → `/roll`).

왜 쪼개나: 플레이어가 "주사위 굴리기" 버튼을 누르는 시점이 LLM 응답 사이에 끼어 있다. 한 호출로 끝내려면 서버가 사용자 입력을 기다리며 스트림을 열어둬야 해서 구조가 복잡해진다. 그냥 두 호출로 끊는 게 단순하다. 자세한 이유는 [01-overview.md](./01-overview.md) §3.10.

- `/turn` 이 `{action: "roll"}` 로 끝나면 엔진은 `PendingCheck` 를 `GameState` 에 저장하고 스트림을 닫는다. 내러티브는 아직 돌지 않음.
- 프론트는 `pending_check` 이벤트로 받은 `{dc, stat, mod, required_roll, tier, target}` 을 UI 에 띄우고, 플레이어가 버튼을 누르면 **본문 없이** `/roll` 호출. 주사위 눈은 서버가 굴린다 (서버 권위 — 클라이언트가 dice 값을 보내지 않음).
- `/roll` 은 `PendingCheck` 를 읽어 d20 을 굴리고 `grade` 를 계산한 뒤 내러티브를 돌리고 `pending_check = None` 으로 지운다.
- `/turn` 을 `pending_check` 가 활성인 채로 호출하면 `error: PendingCheckActive`. `/roll` 을 `pending_check` 없이 호출하면 `error: PendingCheckExpected`. P1 은 재시도/취소 엔드포인트 없음.
- **프론트 입력 가드**: `pending_check` 활성 동안 텍스트 전송 버튼은 비활성화. 주사위 버튼만 활성. 백엔드 가드(`PendingCheckActive`)와 이중 방어.

```python
class PendingCheck:
    player_input: str
    action: Literal['roll']
    tier: Tier
    stat: StatKey
    target: str
    targets: list[str]    # judge 원본 배열. 단일 대상이어도 [id] 로 채움. 폴백(§2.3 step 3) 도 [location_id] 로 채워 None 경로 없음
    dc: int               # tier 범위에서 균등 샘플링 (§5.2)
    mod: int              # social_bonus
    required_roll: int    # sigmoid 결과 (1..20)
    created_at: str       # ISO 8601. 디버깅·로그용 (P1 에선 소비처 없음)
```

### 2.3 judge 출력 검증과 재시도

dc_judge runner 가 매 호출마다 두 단계 검증:

1. **JSON 파싱** — `JudgeOutput` 스키마 검증 (`backend/src/llm_client/agents/dc_judge/schema.py`).
2. **semantic 검증** — `targets[]` 의 모든 ID 가 `state.characters | locations | items` 에 실제로 존재하는지 (LLM 은 종종 없는 ID 를 지어내는 환각이 있음).

둘 중 어느 쪽이 실패해도 직전 응답 본문과 에러 메시지를 messages 에 append 해서 자기 교정 루프로 다시 호출 — 같은 실수를 반복하지 않게 LLM 컨텍스트에 실패 사유를 박아주는 것. 최대 5 회 재시도 (총 6 번 시도).

5 회 후에도 통과 못하면 마지막 에러 종류로 분기:
- 마지막이 JSON 파싱 실패 → `JudgeMalformed` 예외 raise ([04-boundary.md](./04-boundary.md) §3 → SSE `error: JudgeMalformed`).
- 마지막이 semantic 실패 → 폴백: 현재 플레이어가 있는 장소 하나로 (`targets=[location_id]`, `target=location_id`). 예외 안 던짐, 일반 진행 계속.

검증 통과 시 PendingCheck 채우는 규칙:
- `targets` 단일 대상이면 `PendingCheck.target` 에 그대로.
- 복수 대상이면 actor 가 가장 싫어하는(affinity 가 가장 낮은) 대상을 기준으로 한 명 골라 `PendingCheck.target` 에 — `social_bonus` 가 한 명 기준으로 계산되기 때문. 원본 배열은 `PendingCheck.targets` 에 함께 둔다.

### 2.4 SSE 이벤트

한 줄 JSON 형식: `data: {"type": "<event>", "data": {...}}\n\n`. 스트림은 반드시 `done` 또는 `error` 로 종료.

| type | data | 시점 |
|---|---|---|
| `judge` | `{action, tier?, stat?, targets?, question?}` — `tier` 는 한글 라벨 string (§5.2 의 7단계 중 하나). 디스플레이용 `{value, max, label}` 객체 형식은 `pending_check` 에서 재가공. `action=pass|rest|clarify|reject` 면 판정이 일어나지 않으므로 `tier`/`stat` 는 부재 | judge LLM 직후. §2.3 의 재호출이 일어나도 최종(검증 통과) 결과 1회만 발사 |
| `pending_check` | `{dc, stat, mod, required_roll, tier, target}` — `tier` 는 §5.2 의 `{value:1..7, max:7, label}` 형식 | action=roll 확정. 직후 스트림 종료 |
| `narrative_delta` | `{text}` | narrate LLM 청크마다 |
| `state` | `{hero, subject, quest, place}` | apply 후 전체 슬롯 통짜 송신. 한 턴에 1회, 파이프라인 말미 |
| `log_entry` | `LogEntry` (`player | act | roll | gm`) | 플레이어 입력, clarify 되물음, 주사위 결과, 그리고 P2 전투 라운드의 자체 발행 gm 텍스트. 평시 narrate 의 `gm` 은 `narrative_delta` 축적으로 만들어지므로 이벤트 없음 |
| `combat_start` | `{turn_order, round, surprise, enemy_ids}` — P2 | judge 가 `action="combat"` 반환해 엔진이 `combat_state` 를 띄운 직후 |
| `combat_turn` | `{actor, action: "attack"|"flee"|"pass"|"death_save", grade, damage?, target?, hand?}` — P2 | combat 라운드 안 한 actor 의 한 행동 직후. 다이스 굴림은 엔진이 결정 |
| `combat_end` | `{outcome: "victory"|"defeat"|"fled"}` — P2 | 종료 조건 충족 직후. 다음 SSE `done` 이 따라옴 |
| `done` | `{}` | 턴 종료 |
| `error` | `{message, code?}` | 복구 불가 오류 |

### 2.5 세션 생명주기

**프로필 목록** (`GET /profiles`): `PROFILE_DIR/` 아래 각 프로필 디렉터리를 스캔해 `[{id, name, description, races: [{id, name, description}]}]` 반환. 프론트 새게임 화면이 이 목록을 카드로 보여주고 사용자가 하나 골라서 시작.
- 프로필 메타(`id, name, description`)는 `scenarios/{id}/profile.json` 한 파일에 박힘. `id` 는 디렉터리 이름과 같아야 (스캐너가 디렉터리명으로 찾고 검증).
- race 목록은 `scenarios/{id}/races/*.json` 의 각 파일에서 `{id, name, description}` 만 추려서 응답에 포함 (`racial_skills` 는 내부 전용, 프론트로 안 나감).

**init** (`POST /session/init {profile, player: {name, race_id, appearance}}`):
- 요청 검증: `profile` 이 `PROFILE_DIR` 에 있는 디렉터리인지, `race_id` 가 그 프로필의 race 목록에 있는지. 누락·미스매치는 422.
- 시드 로딩: `PROFILE_DIR/{profile}/` 의 `world.md`, `start.json`, `player_template.json`, `characters/`, `locations/`, `quests/`, `items/`, `races/` 를 읽어 초기 `GameState` 조립.
- 플레이어 캐릭터 합성: `player_template.json` 의 시작 위치·equipment·인벤토리 시드는 그대로 쓰되, `name`·`race_id`·`appearance` 는 요청값으로 덮어쓰기. 스탯 6 개 (`STR/DEX/CON/INT/WIS/CHA`) 모두 10 으로 강제 (player_template 의 stats 는 무시). max_HP / max_MP 는 [03-features.md](./03-features.md) §2.3 의 공식 (level 0, CON 10 → max_HP 20, INT 10 → max_MP 15). race 의 `racial_skills` 자동 부여.
- `game_id` 는 시작 시각으로 할당 (`game_YYMMDD_HHMMSS`), 최초 저장. `SAVES_DIR/.current` 한 줄 텍스트 파일에 game_id 기록. `FrontState` 와 함께 반환.

**현재 세션 복원** (`GET /session/current`): `SAVES_DIR/.current` 가 가리키는 game_id 의 `FrontState` 반환. `.current` 가 없거나 가리키는 파일이 없으면 HTTP 404 — 프론트는 이 응답으로 새게임 화면 분기. 게임 목록·이어하기 화면은 P1 에 없음 (한 명·한 게임 흐름).

**load** (`GET /session/{id}/state` 또는 `/turn` · `/roll` 진입): `SAVES_DIR/games/{id}.json` 을 읽어 Pydantic 으로 `GameState` 복원. 파일 없으면 HTTP 404.

**save**: `apply_changes` 이후 파이프라인 말미에서 호출. 안전 쓰기 — `.tmp` 파일에 먼저 다 쓴 뒤 `os.replace` 로 한꺼번에 본 파일을 갈아끼운다. 쓰는 도중 죽어도 반쪽짜리 파일이 남지 않음. 프로세스 안에서 `asyncio.Lock` 하나로 동시 저장 요청을 한 줄 세워 순서대로 처리. 저장이 실패하면 메모리에 들고 있던 게임 상태를 직전 값으로 되돌리고 SSE `error: PersistenceFailed` 를 보낸다.

**인스턴스 단위 파일**: 게임 하나 = 파일 하나 (`SAVES_DIR/games/{game_id}.json`). 파일 이동·복사만으로 세션 이전 가능. 이유와 한계는 [01-overview.md](./01-overview.md) §3.11.

---

## 3. 컨텍스트 레이어

내러티브 에이전트에 전달되는 컨텍스트는 4개 레이어. 위에서 아래로 갈수록 자주 바뀐다 — 맨 위 월드 레이어는 게임 한 판 내내 거의 그대로 두고, 맨 아래 장면 레이어는 매 턴 새로 조립한다. 안 바뀌는 건 시스템 프롬프트에 박아 캐싱하고, 자주 바뀌는 건 매번 다시 만든다.

### 3.1 월드 레이어 (거의 불변)

게임 세계관, 톤, 시대, 기본 규칙. 프로필별 `world.md` (`scenarios/{name}/world.md`). 시스템 프롬프트에 고정.

```markdown
# 세계관
중세 판타지, 어두운 톤. 812년 고블린 침공기.
인간과 고블린이 대립하는 세계.

# 톤
진지하고 긴박한 분위기. 유머는 절제.
```

### 3.2 세션 레이어 (퀘스트 완료 시 변경)

엔진이 매 턴 조립. 현재 챕터와 그 안의 활성 퀘스트에 대해 **narrator 가 진행을 이어가는 데 필요한 최소 정보**를 넘긴다 — 큰 그림 톤이 아니라 "지금까지 어디까지 왔고, 무엇이 남았고, 어떤 제약이 있는지".

```json
{
  "chapter": {
    "title": "고블린 침공",
    "summary": "마을 광장의 고블린 정찰병을 처치하고, 대장장이의 무기 제작을 돕는 중. 마을은 본격적인 침공에 대비하고 있다.",
    "quests": [
      {
        "title": "광장의 고블린 정찰병",
        "summary": "광장 입구에서 정찰병 한 명을 발견했지만 아직 접근하지 않음.",
        "giver": "마을 장로",
        "goals": ["정찰병 처치"],
        "conditions": []
      },
      {
        "title": "대장장이의 부탁",
        "summary": "대장장이 군나르가 철광석 5개를 요청. 첫 번째를 동굴에서 발견해 가져온 상태. 4개 남음.",
        "giver": "대장장이 군나르",
        "goals": ["대장장이에게 보고"],
        "conditions": ["기한 없음"]
      }
    ]
  },
  "world_time": "812-04-28T14:00:00"
}
```

필드 의미:

- **`summary`** — "지금까지 진행한 것의 한 줄 요약" (동적). 정적 의뢰 내용이 아니라 챕터/퀘스트가 *어디까지 왔는지* 의 서사적 상태. narrator 가 의미 있는 진행이 있을 때 `{type: "set", entity: "chapters|quests", id, field: "summary", value: "..."}` 로 갱신 (§6.1). 초기값은 시나리오 시드 (`scenarios/{name}/quests/*.json`, `chapters/*.json`) 에 박힘 — 보통 "[수락] 마을 장로가 광장의 정찰병 처치를 의뢰" 같은 한 줄.
- **`goals`** — 아직 충족 안 된 트리거 이름들 (`pending only`). 끝난 트리거는 빠짐. narrator 에게 "지금 남은 단계가 무엇인지" 직접 알림. 출처: `quest.triggers[i].name where !triggers_met[i]`.
- **`conditions`** — 자유 텍스트 제약 ("기한 없음", "민간인 피해 최소화"). narrator 가 매 턴 톤에 반영. quest 모델의 `conditions` 그대로.
- **`giver`** — 의뢰자 이름 (캐릭터 ID 가 아닌 표시명). narrator 의 회상 서술 ("장로의 의뢰가 떠올랐다") 에 사용. 출처: `characters[quest.giver_id].name`.
- **`title`** — 식별자.
- **`world_time`** — 현재 게임 내 시각. session_layer 가 narrator 에게 "지금 시각" 을 넘기는 유일한 경로. 형식 정의는 아래 구조 결정 항목.

구조 결정:

- **정적/동적 분리** — session_layer 는 *동적* (지금까지의 진행). *정적* 디테일 (rewards, difficulty, full triggers, fail_triggers, prerequisite 등) 은 플레이어가 퀘스트 NPC/장소에 닿는 턴에 `target_view` 의 그래프 탐색으로 들어온다 (§3.4.2). session=윤곽·동적, target_view=깊이·정적.
- **progress 숫자 안 보냄** — `{done, total}` 같은 숫자는 본문에 녹이기 어렵다 ("0/1" 을 어떻게 묘사하나). narrator 가 진행 상태를 알 필요는 `summary` + `goals` (pending only) 로 충족된다. progress 자체는 프론트 표시·엔진 트리거 평가에서만 사용.
- **`active_*` prefix 없음 / `status` 필드 노출 안 함** — 어차피 활성인 것만 들어가므로 잉여 (`status` 필드 자체는 모델에 있고 narrator 가 `set` 으로 갱신함; session_layer 노출에서만 생략).
- **`chapter.quests[]` 위계** — 퀘스트는 항상 챕터에 속하므로 묶음. P3 의 Campaign 도 동일 패턴 (`campaign.chapters[]`).
- **`world_time` 은 ISO 8601 (`T` 포함)** — 다른 문서의 시간 필드와 일관 ([03-features.md](./03-features.md) §2.1, [04-boundary.md](./04-boundary.md) §1).

모델 정의와 progress 계산은 [03-features.md](./03-features.md) §2.8.

### 3.3 히스토리 레이어 (매 턴 변경)

히스토리는 두 블록을 한 문자열로 이어붙여 전달한다: **이전 요약 (먼 과거, 한 줄)** → **최근 대화 (가까운 과거, 원문)**. **마지막 줄이 곧 직전 턴** — narrator 가 자연스럽게 "지금" 으로 이어쓸 수 있게 한다. 먼 과거는 한 줄로 압축해 컨텍스트를 아끼고, 가까운 과거는 원문 그대로 보여줘서 톤·말투를 잇게 한다.

**턴 로그 (`turn_log`, 이전 요약)**: 전체 턴의 한 줄 요약을 롤링 보관. 상한은 `rules.memory.turn_log_size` (기본 50), 초과 시 오래된 항목부터 drop. 최근 대화에 포함된 턴은 이 블록에서 제외 (중복 방지).

```json
// 저장: narrator 의 turn_summary + 엔진이 메타로 함께 박는 target (`pending_check.target`, 없으면 `judge_result.targets[0]`, 둘 다 없으면 생략) — 메모리 연관·필터링용 [P3]
{"turn": 17, "target": "goblin_scout", "turn_summary": "정찰병 처치 → 광장 고블린 1/1 완료"}

// 전달 (먼저 등장, 시간 오름차순)
=== 이전 요약 ===
[턴 17] — 정찰병 처치 → 광장 고블린 1/1 완료
[턴 18] — 덩치에 계속 공격, 돌파 실패
```

**최근 대화 (`recent_dialogue`)**: 최근 N턴의 `(player_input, narrative)` 원문 쌍. narrate 가 돈 모든 분기에서 append — `/turn` 의 pass·reject, `/roll` 의 narrate 완료. clarify 와 combat-P1-error 는 narrate 가 안 돌아 append 안 함. 상한은 `rules.memory.recent_dialogue_turns` (기본 10), 초과 시 오래된 항목부터 drop.

```
=== 최근 대화 ===
[턴 19]
  플레이어: 한 걸음 물러서며 사방을 살핀다.
  서술자: 어둠 속에서 무언가 움직이는 기척이...
[턴 20]
  플레이어: 숨을 고르며 눈을 뜨려 한다.
  서술자: 차가운 돌바닥이 뺨에 닿는다...
```

**엔티티 메모리**: target 의 `memories[]` 가 `target_view` 에 포함되어 전달 (§7).

### 3.4 장면 레이어 (매 행동 변경)

두 에이전트의 필요가 달라서 두 갈래로 조립된다:

- `surroundings` → DC판정에게: "지금 여기 뭐가 있나" (장소 + 주변 엔티티 상태 태그)
- `target_view` → 내러티브에게: "이 한 명/한 곳에 대해 알 수 있는 모든 것" (그래프 1~2홉 탐색)

#### 3.4.1 surroundings (판정 결정용)

**목적**: DC판정 에이전트에게 "지금 여기 뭐가 있고 어떤 상태인지" 전달.

**포함**:
- 현재 장소 이름 + 설명 + 상태 태그
- 장소에 놓인 아이템 (visible items)
- 주변 NPC: 이름 + 상태 태그 (예: "경계중(affinity -25)", "우호적(affinity 70)") — 어떤 affinity 값이 어떤 라벨이 되는지(매핑 규칙)는 §7.4
- 주변 오브젝트 + 상태 태그 (예: "문: 잠김", "상자: 함정")
- 인접 장소 이름

#### 3.4.2 target_view (내러티브용)

**목적**: 내러티브 에이전트에게 "이 대상의 관점에서 알 수 있는 정보" 전달.

**조립 방법**: target 하나에 대해서만 조립 (같은 장소의 다른 NPC 정보는 포함하지 않음). 그래프 탐색 규칙(시작 노드·홉 수·엣지 갈아타기)은 §4.2.

**분기 결정**: target ID 가 `state.characters | locations | items` 중 어느 컬렉션에 속하는지로 자동 판별 (§2.3 의 검증 결과 재사용).

**target 이 NPC 일 때**:
- 성격, 톤 힌트, 호감도
- 임무/역할 (왜 여기 있는지)
- 아는 정보 (hints)
- memories[]
- 연결된 퀘스트
- 보이는 장비 (visible_equipment)

**target 이 Location 일 때**:
- 설명, 태그
- hidden_items (발견된 것만), hidden_connections
- 연결된 퀘스트

**target 이 Item 일 때** (문·상자·함정 같은 인터랙션 객체 포함):
- 상태 (잠김, 함정 등)
- 연결된 아이템 (key_item_id)
- 뒤에 뭐가 있는지 (connection target)

**pass 일 때**: target_view 를 조립하지 않음. 내러티브는 surroundings 만으로 서술.

**reject 일 때**: target_view 없음, surroundings 만 + reject 가이드. narrator 는 플레이어 입력을 인-게임 표현(예: "알 수 없는 힘에 막힌다", "현기증이 일어 그 생각을 잊는다")으로 흡수. `state_changes` 비우기·`memorable=false` 강제는 §1.1 참조.

---

## 4. 온톨로지 (그래프)

§3 의 `target_view` 가 어디서 오는지 — 엔티티들은 그래프로 연결돼 있고, 그래프 1-2홉 탐색이 NPC 의 "지식 범위" 를 만든다.

### 4.1 구조

엔티티(캐릭터·아이템·장소) 사이의 연결을 그래프로 본다. 점 하나(노드)가 엔티티 하나, 두 점을 잇는 선(엣지)이 그 사이의 관계.

**구조적 엣지**:
- `location_id`: NPC → 장소
- `equipment`: NPC → 아이템
- `inventory_ids`: NPC → 아이템
- `connections`: 장소 → 장소

**의미적 엣지** (init 시 자동 추론):
- 퀘스트 `triggers[].target_id` → `required_by` 엣지
- 퀘스트 `giver_id` → `gives_quest` 엣지
- 퀘스트 `triggers[].type == character_death` → `kill_target_of` 엣지
- 퀘스트 `rewards.items` → `reward_of` 엣지

**config 정의 관계** (서사적):
- NPC 의 `hints`: 아는 정보/퀘스트 연결
- Item 의 `key_item_id`: 열쇠 → 문 연결
- Item 의 `unlocks`: 아이템 → 오브젝트 연결

**런타임 컨텐츠** (엣지 아님 — 엔티티 안에 쌓이는 항목 집합):
- `memories[]`: 엔티티별 기억 (§7)

### 4.2 target_view 조립

target 노드에서 시작해 1~2 단계(홉) 떨어진 이웃까지 훑어 모은다. 단계마다 **다른 종류의 엣지를 갈아타도 된다** — NPC 가 아는 정보의 범위를 자연스럽게 넓히기 위해서.

예: `guard_01 →(gives_quest)→ quest_01 →(required_by)→ plaza_01` — 경비병이 주는 퀘스트, 그 퀘스트가 가리키는 장소까지 두 홉으로 도달.

구현은 `src/ontology/graph.py` 가 매 호출마다 `GameState` 에서 임시 그래프를 구성. 성능 최적화(인덱싱·캐시)는 P1 이슈 아님.

### 4.3 장소 확장

```python
Location(
    hidden_items=[...],         # 수색 성공 시 발견
    hidden_connections=[...],   # 수색 성공 시 통로 발견
    difficulty="보통",           # 수색 난이도 tier
)

Connection(
    target_id="cellar",
    difficulty="어려움",         # 자물쇠 난이도 tier
    key_item_id="iron_key",     # 이 열쇠 보유 시 자동 해제
    # travel_min: int | None    # per-edge 이동 분 ([03-features.md](./03-features.md) §2.1) [P3]
)
```

엔티티 종류가 tier 의 용도를 결정 (장소 → 수색, 통로 → 자물쇠, 아이템 → 잠금/해독 등). `Tier` enum 자체의 정의·매핑은 §5.2 참조.

---

## 5. DC 시스템

`{action: "roll"}` 분기에서 엔진이 굴리기 전에 계산하는 수치.

### 5.1 시그모이드 DC

```
required_roll = round(20 / (1 + e^(-k(DC - player_stat))))   # [1, 20] clamp
```

왜 시그모이드(S자 곡선)인가: 단순히 `DC - stat` 으로 빼면 어려운 행동은 0%, 쉬운 행동은 100% 가 되어 굴릴 의미가 없다. S자 곡선에 통과시키면 양 끝이 부드럽게 깎여 — 쉬운 행동도 약간은 실패하고, 어려운 행동도 약간은 성공한다 (k=0.5 일 때 곡선이 1·20 에 닿지 않고 한두 칸 안쪽에서 꺾인다). `k` 는 곡선의 가파름.

- d20 기반. 플레이어가 `required_roll` 이상을 굴리면 성공.
- `DC` 와 `player_stat` 은 모두 정수 스탯값. `k` (기본 0.5) 는 점당 가파름 — `rules.difficulty_class.sigmoid` config.

### 5.2 Tier 라벨 / Tier → DC 매핑

판정 난이도는 **7단계 한글 라벨**로 통일 — judge 출력(§1.1), SSE `judge`/`pending_check` 이벤트(§2.4), 장소·통로·아이템 난이도(§4.3), 아래 DC 매핑이 모두 같은 enum 을 공유하는 전역 정의.

```python
Tier = Literal["매우 쉬움", "쉬움", "보통", "어려움", "매우 어려움", "전설", "신화"]
```

백엔드는 라벨을 정수 tier (1..7) 와 1:1 매핑하고, 프론트 노출 시 `{value: int(1..7), max: 7, label: str}` 형식으로 보냄 ([04-boundary.md](./04-boundary.md) §1).


| tier | label | DC 범위 |
|---|---|---|
| 1 | 매우 쉬움 | 2–3 |
| 2 | 쉬움 | 4–6 |
| 3 | 보통 | 7–10 |
| 4 | 어려움 | 11–13 |
| 5 | 매우 어려움 | 14–16 |
| 6 | 전설 | 17–18 |
| 7 | 신화 | 19 |

- "보통" 이 가장 넓고 양 끝(매우 쉬움/신화) 으로 갈수록 범위가 좁아진다. LLM 이 같은 "보통" 을 골라도 실제 DC 는 7~10 사이 어디든 떨어져 결과가 다양해진다.
- tier 별 DC 범위 안에서 한 값을 무작위로 뽑아 DC 를 확정한 뒤, 시그모이드를 거쳐 최종 `required_roll` 을 만든다.
- DC 양 끝값(1, 20) 은 무작위 추첨에서 뺀다. 두 끝을 빼는 이유는 다르다 — DC 1 은 시그모이드를 거쳐도 `required_roll` 이 거의 모든 stat 에서 1 로 떨어져 사실상 자동 통과가 되고, DC 20 은 `required_roll` 이 20 부근에 몰려 자연 20 (`critical_hit_threshold`, §5.3) 과 구분이 사라진다. 치명타 판정은 d20 원본 주사위로만 한다는 약속(§5.3) 을 지키려면 끝값 두 칸은 비워둬야 한다.

### 5.3 판정 결과 (grade)

단일 d20 결과는 다음 5등급으로 분류. 등급이 내러티브 톤을 결정.

| grade | 조건 | 의미 |
|---|---|---|
| critical_success | `dice >= critical_hit_threshold` (기본 20) | 원본 주사위 기준. 추가 보너스 (치명타, 비밀 노출). |
| critical_failure | `dice <= critical_miss_threshold` (기본 1) | 원본 주사위 기준. 장비 파손/부상. |
| success | `total > required_roll` | 깔끔한 성공. |
| partial_success | `total == required_roll` | 대가를 치르는 성공 (소음, 가까스로 성공). |
| failure | `total < required_roll` | 단순 실패. |

`total = dice + mod`. **표 순서 = 우선순위** (위에서부터 첫 일치): critical 두 행이 dice 만 보고 가장 먼저 잡힌다. `dice == 20` 이고 `total > required_roll` 이면 critical_success, `dice == 1` 이고 `total > required_roll` 이면 critical_failure (큰 mod 가 success 처럼 보이게 하는 걸 의도적으로 막음). **치명타는 원본 주사위로만 판정**: `mod` 가 critical 을 만들거나 지울 수 없음. 프론트 `RollResult` ('success' | 'fail') 는 `grade in (critical_success, success, partial_success)` 로 매핑.

### 5.4 소셜 보정 (social_bonus)

비전투 roll 에는 actor 가 대상을 어떻게 느끼는지(affinity) 에 따라 주사위 결과에 보너스/페널티를 얹는다. 친한 NPC 는 같은 말을 해도 잘 통하고, 사이가 틀어진 NPC 는 안 통한다는 감각을 수치화한 것.

```python
target_id = pending_check.target            # §2.3 이 고른 한 명. 폴백 시 location_id (§2.3 step 3)
aff = state.characters[actor].relations.get(target_id, 0)
mod = 0
if aff >=  social.friendly_threshold:  mod =  social.roll_bonus  # 친밀: +bonus
if aff <= -social.friendly_threshold:  mod = -social.roll_bonus  # 적대: -bonus
# 그 사이(중립)는 mod = 0
# 이 mod 가 PendingCheck.mod 에 박히고, /roll 에서 total = dice + mod 로 합산 (§5.3)
# Location 폴백 시 relations 에 location_id 가 없어 .get 이 0 으로 떨어진다 — 의도된 0(중립) 보정. 대상이 모호한 판정에는 affinity 보너스를 주지 않겠다는 결정.
```

위 코드의 `friendly_threshold` · `roll_bonus` 는 `rules.social` config. 같은 `rules.social` 그룹의 `affinity_success/failure/critical` 은 별개 키 — affinity delta 산출용으로 §6.1 에서 사용.

---

## 6. 상태 업데이트

내러티브 에이전트가 출력에 실어 보내는 `state_changes` 가 어떻게 게임 상태로 박히고, 무엇이 프론트로 흘러가는지.

### 6.1 state_changes 형식

내러티브 에이전트가 발행할 수 있는 타입은 **5종** (`Literal["set","set_time","move","move_item","affinity"]`):

```json
[
  {"type": "set",       "entity": "characters", "id": "guard_01", "field": "disposition.aggressive", "value": 80},
  {"type": "set_time",  "value":  "812-04-29T06:00:00"},
  {"type": "move",      "target": "player_01",  "destination": "plaza_01"},
  {"type": "move_item", "item":   "iron_key",   "from": "chest_01", "to": "player_01"},
  {"type": "affinity",  "actor":  "player_01",  "target": "guard_01", "grade": "success", "intent": "friendly"}
]
```

- `set` 권한 매트릭스 — entity 별로 narrator 가 만질 수 있는 field 가 다르다:
  - `characters` — 스칼라 + 점 표기 (`disposition.{lawful, aggressive, moral}`, `tone_hint`, `status` 등). list/엔진 전용/`world_time` 은 아래 묶음으로 제외.
  - `items`, `locations` — 스칼라만 (`weather`, `status` 등).
  - `chapters`, `quests` — `summary` 와 `status` 만 ([03-features.md](./03-features.md) §2.8).
- narrator 는 단순 스칼라 필드만 `set` 으로 바꿀 수 있다. 다음 세 묶음은 손댈 수 없다:
  - **list 필드** — character 의 `relations`, `inventory_ids`, `memories`, `racial_skills`, `learned_skills`, `companions`. 추가/제거의 부수효과가 커서 (예: `inventory_ids` 변경은 소지품 수를 흔든다) narrator 가 직접 만지면 일관성이 깨진다. 구조 변경은 백엔드 로직 [P3] 가 한다. quest 의 `triggers`/`conditions` 같은 list 도 같은 이유로 막히지만 — quest 는 위 매트릭스가 이미 `summary`/`status` 만 허용해 자동으로 제외된다.
  - **엔진 전용 필드** — `HP/MP/exp/gold/alive/death_saves/revive_coins` 등. 전투·레벨업·죽음 처리는 엔진이 독점하고, narrator 는 결과를 받아서 묘사만 한다 (수치를 결정할 권한이 없다). 전투 진입/이탈 자체는 `state.combat_state` 의 turn_order 등재 여부로 표현 — 캐릭터에 별도 `in_combat` 플래그는 두지 않는다.
  - **`world_time`** — 일반 `set` 으로 못 만진다. 시간 점프가 필요할 때만 전용 `set_time` type 을 발행 ([03-features.md](./03-features.md) §2.1).
- `set_time` 은 `world_time` 만 갱신하는 전용 type. 분 단위 가산은 엔진이 자동 처리하고, narrator 는 장면 전환·휴식·시간 비약 같은 절대 시각 점프에만 발행한다. 현재 `world_time` 보다 과거 ISO 는 `rejected[]` 로 reject (시간 역행 금지).
- `affinity` 는 `grade × intent` (× `target.disposition` [P3]) 로 `rules.social` 기반 delta 를 엔진이 산출. narrator 는 숫자를 정하지 않는다 ([03-features.md](./03-features.md) §2.2). 복수 대상 시나리오(예: 두 경비병 동시 설득)에서는 entry 를 대상별로 하나씩 발행 — `target` 단일 필드라 한 entry = 한 대상.
- `move` / `move_item` / `affinity` 적용 시 엔진이 자동으로 **퀘스트 트리거** 실행 (`location_enter`, `item_use`, `character_death`) [P3].

**형식 검사와 `rejected[]`**: `apply_changes` 는 narrator 가 보낸 변경 목록을 Pydantic 의 5종 union 스키마로 한 항목씩 검사한다. 형식이 어긋난 항목 — 잘못된 필드 이름, 모르는 type, narrator 가 못 만지는 엔진 전용 필드를 `set` 한 경우 등 — 은 그 항목만 `rejected[]` 에 따로 담고, 나머지 유효한 변경은 그대로 적용한다. 반환: `{applied, rejected, world_time, created_ids?, quest_updates?, chapter_updates?}`. 파이프라인은 `rejected[]` 를 로그에 남기기만 하고 narrator 를 다시 부르지 않는다 [P3 에서 재호출 루프 검토].

**내부 전용 타입** (엔진/CLI 만 사용, narrator 는 발행 금지):
- `{"type": "death", "target": "<id>"}` — 캐릭터 사망 처리 + 시체/드랍/퀘스트 연쇄. [P2]
- `{"type": "create", "entity": "items|characters|locations|races|quests", "data": {...}}` — 런타임 엔티티 생성, ID 자동 부여. [P3]

경계를 둔 이유: 내러티브 에이전트가 직접 엔티티를 생성/살해하지 못하게 해 상태의 결정권을 엔진에 묶어 둠.

### 6.2 프론트 반영

`apply_changes` 후 엔진은 `mapping/to_front.py` 로 **4 슬롯 전체** (Hero / Subject / Quest / Place) 를 다시 JSON 으로 만들어 `state` 이벤트로 보낸다. 바뀐 부분만 보내는 게 아니라 한 턴에 한 번 통째로 — 프론트는 받은 값으로 그대로 덮어쓴다. 파이프라인 말미에서 단 한 번 발사. Log 는 별도 `log_entry` 이벤트로 쌓인다. [04-boundary.md](./04-boundary.md) §1.

**디스플레이 로그 영속화**: SSE `log_entry` 와 누적된 `narrative_delta` (gm 본문 한 덩이) 는 매 턴 끝에 `GameState.log_entries: list[LogEntry]` 에도 append 된다. 상한 `rules.log.display_turns` (기본 20), 초과 시 가장 오래된 항목부터 evict. `GET /session/{id}/state` (§2.5) 와 `GET /session/current` 가 응답할 때 이 영속본을 `FrontState.log` 로 그대로 반환 — reload 시 최근 20 턴치 채팅이 화면에 복원된다. LLM 컨텍스트용 `recent_dialogue` 와 turn 단위 요약 `turn_log` (둘 다 §3.3) 와는 별개 cap.

---

## 7. 메모리 시스템

§6 의 `state_changes` 가 즉각적인 변경을 다루는 데 비해, 메모리는 다음 턴 이후 narrator 가 인용할 수 있는 **장기 기억**. NPC·장소·플레이어 모두 가진다.

### 7.1 구조

모든 엔티티(NPC, 장소, 플레이어) 공통:

```python
class Memory:
    content: str            # "플레이어가 뇌물을 줘서 통과시켜줌"
    importance: int         # 1: 사소, 2: 보통, 3: 중요
    turn: int               # 기록된 턴 번호
    target_id: str | None   # 이 기억이 향한 entity (NPC/장소/아이템) ID. narrator 의 memory_links (§1.2) 로 채움. None 이면 Subject.known 산출 ([04-boundary.md](./04-boundary.md) §1) 에서 빠짐.
```

### 7.2 저장

내러티브 에이전트가 `memorable=true` 로 판정하면, 엔진이 `memory_targets` 의 각 엔티티 `memories[]` 에 저장. 각 entity 의 `Memory.target_id` 는 narrator 가 함께 출력한 `memory_links` (§1.2) 의 매핑값으로 채운다 — `memory_links[entity_id]` 가 누락이면 `target_id=None`. narrator 는 `memories[]` 필드를 `set` 으로 건드릴 수 없고 (§6), 오직 이 경로로만 추가.

### 7.3 용량 관리

- 엔티티당 최대 N 개 (`rules.memory.cap`, 기본 20).
- cap 도달 시: importance 낮은 것부터 제거. 같은 importance 면 오래된 것 (turn 작은 것) 부터 제거.
- 모순되는 메모리는 둘 다 저장. 내러티브 에이전트가 시간순으로 해석 ("예전엔 믿었는데 배신당했다").

### 7.4 활용

- `target_view` 에 target 의 `memories[]` 가 포함 → narrator 는 NPC 기억을 보고 서술에 반영한다 ("아까는 통했지만 이번엔 너를 다시 본다").
- 스탯 악용(같은 행동을 반복해 쉬운 성공만 뽑아내는 것) 은 다음 돌아가는 경로로 막힌다:
  1. 같은 시도가 반복되면 narrator 가 그 분위기를 메모리에 적고 (`"또 설득하려 한다"`), 동시에 `affinity` state_change 로 호감도를 깎는다.
  2. 깎인 affinity 는 다음 턴 `surroundings` 의 상태 태그에 노출된다 (예: `경계중(affinity -25)`). 라벨 매핑은 §5.4 의 `rules.social.friendly_threshold` 를 재사용: `affinity >= friendly_threshold` 면 `우호적`, `affinity <= -friendly_threshold` 면 `경계중`, 그 사이는 `중립` — 같은 임계값으로 social_bonus mod 와 surroundings 태그가 동시에 갈린다.
  3. DC판정은 이 태그를 보고 자연스럽게 tier 를 올린다.
  - 즉 DC판정은 memory 를 직접 읽지 않는다. `memory → narrator → affinity → 태그 → DC판정` 의 우회 경로로만 영향이 흐른다. 이렇게 둔 이유: DC판정에게 메모리까지 직접 보여주면 컨텍스트가 부풀고, 판정이 "이 NPC 의 과거" 같은 서사적 정보에 흔들린다 (§1.1 의 "DC판정은 장기 맥락을 받지 않는다" 원칙).
