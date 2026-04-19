# LLM TTRPG 엔진 설계 (back)

> 북극성 설계 노트. 전체 시스템의 모양과 이유. 체크리스트가 아니라 참조용.
> Phase 마커: **[P1]** 현재 구현 중 · **[P2]** 전투 · **[P3]** 확장.
> Phase 마커 없는 절은 전 구간 공통 원칙.
> 구현 단위 플랜은 `back/docs/superpowers/plans/` 아래.

---

## 1. 설계 철학

### 역할 분리

| 역할 | 담당 |
|---|---|
| 이야기 서술 | LLM (내러티브 에이전트) |
| 난이도 등급 판정 | LLM (DC판정 에이전트) |
| DC 수치 계산 | 엔진 |
| 컨텍스트 조립 | 엔진 (그래프 탐색) |
| 상태 업데이트 | 엔진 |
| 전투 처리 [P2] | 엔진 |
| NPC AI [P2] | 엔진 (확률 규칙) |
| 호감도 | 엔진 (§6.4, §11.1) |
| 성장·거래·장비·스킬·시간 [P3] | 엔진 (§11) |

LLM 은 "무엇을 할까 / 어떻게 말할까" 만 결정. 수치·상태·규칙은 모두 엔진.

---

## 2. 에이전트

### 2.1 DC판정 에이전트

**역할**: 플레이어 입력을 해석하여 판정 여부, 난이도 등급, 관련 스탯, 대상을 결정.

**입력**:
- `player_input`: 플레이어 원문 텍스트
- `surroundings`: 현재 장소 + 주변 엔티티 상태 태그 (§4.1)

**출력**:
```json
{
  "action": "skip" | "roll" | "combat" | "clarify",
  "tier": "easy" | "moderate" | "hard" | "very_hard",
  "stat": "STR" | "DEX" | "CON" | "INT" | "WIS" | "CHA",
  "target": "<entity_id>",
  "targets": ["<entity_id>", "<entity_id>"],
  "question": "되물을 내용 (clarify일 때만)"
}
```

`target` 은 단일 대상, `targets` 는 동시 판정할 복수 대상 (예: 두 경비병 동시 설득). 둘 다 있으면 `targets` 가 우선하며, 엔진은 `targets` 중 actor 의 affinity 가 가장 낮은 대상을 기준으로 `social_bonus` 를 계산한다.

**action 유형**:

| action | 의미 | 다음 단계 |
|---|---|---|
| `skip` | 판정 불필요 (이동, 인사 등) | target_view 없이 바로 내러티브 |
| `roll` | 주사위 필요 | 엔진이 DC 계산 → `pending_check` 저장 → 프론트 주사위 버튼 → `/roll` |
| `combat` | 일반 전투 행동 | [P1 에러 반환] / [P2] 엔진이 자동 주사위 → 내러티브 |
| `clarify` | 해석 불가 / 복합 행동 | 플레이어에게 되물음, 파이프라인 재시작 |

**규칙**:
- 매 턴 호출 (전투/비전투 무관)
- 명시적 대상 없으면 현재 location 이 기본값
- `stat` 은 행동의 성격으로 판단 (플레이어 수치를 볼 필요 없음)
- **히스토리·세션·월드 레이어를 받지 않는다**. 오직 현재 장면(`surroundings`) 만으로 판정. 장기 맥락·과거 턴 요약·엔티티 메모리는 내러티브 전용 (§5, §12.12).

### 2.2 내러티브 에이전트

**역할**: 이야기 서술 + 턴 요약 + 메모리 판정.

**입력**:
- `player_input`: 플레이어 원문
- `judge_result`: DC판정 에이전트 출력
- `grade`: 주사위 결과 등급 (roll/combat 일 때만, §6.3)
- `world_layer`: 세계관 (§5.1)
- `session_layer`: 챕터/퀘스트 요약 (§5.2) [P3 에서 세밀화, P1 은 active_quest 제목만]
- `history_layer`: 최근 N턴 대화 + 이전 턴 요약 (§5.3)
- `target_view`: 대상 엔티티 기준 그래프 1-2홉 (§4.2). skip 이면 surroundings 만.

**출력**: 스트리밍. 본문(한국어 2인칭 3-6문장) + delimiter 뒤 JSON.

```
<서술 본문>
---JSON---
{
  "summary": "경비병 설득 성공",
  "state_changes": [
    {"type": "affinity", "actor": "player_01", "target": "guard_01", "grade": "success", "intent": "friendly"}
  ],
  "memorable": true,
  "memory_targets": ["guard_01"],
  "memory": "플레이어가 뇌물을 줘서 통과시켜줌",
  "importance": 3
}
```

**필드**:
- `summary`: 히스토리 로그에 저장될 한 줄 요약 (대상/결과 명시, ~60자)
- `state_changes`: 엔진에 전달할 상태 변경 목록 (§10)
- `memorable`: 이 턴이 기억할 만한지
- `memory_targets`: 기억을 저장할 엔티티 ID 목록 (복수 가능)
- `memory`: 저장할 기억 내용 (`memorable=true` 일 때 필수)
- `importance`: 기억 중요도 (1: 사소, 2: 보통, 3: 중요)

**서술 규율**:
- 수치/확률/DC 를 본문에 노출하지 않음 ("설득을 시도한다" ○, "DC 15 설득" ✗)
- HP·데미지·XP·골드는 엔진이 이미 적용. 본문에서 숫자로 다시 제시하지 않음.
- NPC 목소리는 `target_view.tone_hint`, `disposition` 을 따름.
- `state_changes` 타입은 `set | move | move_item | affinity` 4종만. 위반 항목은 `apply_changes` 가 `rejected[]` 로 돌려보내고 원본 변경은 적용되지 않음.

### 2.3 LLM 런타임

- 단일 모델, 단일 `BASE_URL` (llama.cpp OpenAI-compat 서버). judge·narrate 모두 같은 클라이언트.
- `src/llm/client.py` 가 `LLMClient` 노출 (기존 `src/llm_client/` 에서 `src/llm/` 로 이전).
- 시스템 프롬프트는 `src/llm/prompts/judge.md`, `src/llm/prompts/narrate.md` 에서 로드.

---

## 3. 파이프라인

### 3.1 1턴 흐름

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

### 3.2 두 단계 턴 (pending_check)

`roll` 분기는 **한 턴을 두 HTTP 호출로 쪼갠다**. 이유는 §12.10.

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

### 3.3 target 검증

DC판정이 반환한 `target` 을 `state.characters | locations | items` 키와 대조:
- 유효 → 진행
- 무효 → DC판정 재호출 (최대 1회). 두 번째도 실패하면 현재 location 으로 폴백.

### 3.4 SSE 이벤트

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

---

## 4. 컨텍스트 (alpha)

### 4.1 surroundings (판정 결정용, 구 alpha_1)

**목적**: DC판정 에이전트에게 "지금 여기 뭐가 있고 어떤 상태인지" 전달.

**포함**:
- 현재 장소 이름 + 설명 + 상태 태그
- 장소에 놓인 아이템 (visible items)
- 주변 NPC: 이름 + 상태 태그 (예: "경계중(affinity 25)", "우호적(affinity 70)")
- 주변 오브젝트 + 상태 태그 (예: "문: 잠김", "상자: 함정")
- 인접 장소 이름

### 4.2 target_view (내러티브용, 구 alpha_2)

**목적**: 내러티브 에이전트에게 "이 대상의 관점에서 알 수 있는 정보" 전달.

**조립 방법**: target 엔티티에서 그래프 1-2홉 탐색. target 하나에 대해서만 조립 (같은 장소의 다른 NPC 정보는 포함하지 않음).

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

**target 이 오브젝트일 때**:
- 상태 (잠김, 함정 등)
- 연결된 아이템 (key_item_id)
- 뒤에 뭐가 있는지 (connection target)

**skip 일 때**: target_view 를 조립하지 않음. 내러티브는 surroundings 만으로 서술.

---

## 5. 컨텍스트 레이어

내러티브 에이전트에 전달되는 컨텍스트는 4개 레이어. 위에서 아래로 변경 빈도 증가.

### 5.1 월드 레이어 (거의 불변)

게임 세계관, 톤, 시대, 기본 규칙. 프로필별 `world.md` (`config/profiles/{name}/world.md`). 시스템 프롬프트에 고정.

```markdown
# 세계관
중세 판타지, 어두운 톤. 812년 고블린 침공기.
인간과 고블린이 대립하는 세계.

# 톤
진지하고 긴박한 분위기. 유머는 절제.
```

### 5.2 세션 레이어 (퀘스트 완료 시 변경)

엔진이 매 턴 조립. 현재 챕터 진행도와 활성 퀘스트 요약. [P1 은 `active_quest` 제목만 / P3 에서 Campaign·Chapter·Quest 3-tier 전체].

```json
{
  "active_chapter": {"name": "고블린 침공", "progress": "2/4 퀘스트 완료"},
  "active_quests": [
    {"name": "광장의 고블린 정찰병", "progress": "0/1", "status": "active"},
    {"name": "대장장이의 부탁", "progress": "1/2", "status": "active"}
  ],
  "world_time": "812-04-28 14:00"
}
```

### 5.3 히스토리 레이어 (매 턴 변경)

두 블록을 이어붙여 한 문자열로 전달: **최근 대화** 먼저, 그다음 **이전 요약**.

**최근 대화 (`recent_dialogue`)**: 최근 N턴의 `(player_input, narrative)` 원문 쌍. `/turn` (skip) 또는 `/roll` (narrate 완료 시점) 에서 append. 상한은 `rules.memory.recent_dialogue_turns` (기본 5), 초과 시 오래된 항목부터 drop.

```
=== 최근 대화 ===
[턴 20]
  플레이어: 숨을 고르며 눈을 뜨려 한다.
  서술자: 차가운 돌바닥이 뺨에 닿는다...
```

목적: 내러티브 에이전트가 자기가 직전에 쓴 문장과 플레이어의 원문을 그대로 보고 톤·성격을 이어쓸 수 있도록.

**턴 로그 (`turn_log`, 이전 요약)**: 전체 턴의 한 줄 요약을 롤링 50개까지 보관. 최근 대화에 포함된 턴은 이 블록에서 제외 (중복 방지).

```json
// 저장
{"turn": 17, "target": "goblin_scout", "summary": "정찰병 처치 → 광장 고블린 1/1 완료"}

// 전달 (위 '최근 대화' 이후에 이어붙음)
=== 이전 요약 ===
[턴 17] — 정찰병 처치 → 광장 고블린 1/1 완료
[턴 18] — 덩치에 계속 공격, 돌파 실패
```

**엔티티 메모리**: target 의 `memories[]` 가 `target_view` 에 포함되어 전달 (§9).

### 5.4 장면 레이어 (매 행동 변경)

`surroundings` 와 `target_view`. §4 참조.

---

## 6. DC 시스템

### 6.1 시그모이드 DC

```
required_roll = round(20 / (1 + e^(-k(DC - player_stat))))   # [1, 20] clamp
```

- d20 기반. 플레이어가 `required_roll` 이상을 굴리면 성공.
- `k` (기본 0.5), `random_buffer` (기본 2) 모두 `rules.difficulty_class.sigmoid` config.

### 6.2 등급 → DC 매핑

| 등급 | 기본 DC | 랜덤 범위 |
|---|---|---|
| easy | 5 | ±random_buffer |
| moderate | 10 | ±random_buffer |
| hard | 15 | ±random_buffer |
| very_hard | 20 | ±random_buffer |

- DC판정이 `skip` 이면 주사위 없이 자동 성공.
- 기본 DC 에 ±랜덤을 적용한 후 시그모이드로 최종 `required_roll` 산출.

### 6.3 판정 결과 (grade)

단일 d20 결과는 다음 5등급으로 분류. 등급이 내러티브 톤을 결정.

| grade | 조건 | 의미 |
|---|---|---|
| critical_success | `dice >= critical_hit_threshold` (기본 20) | 원본 주사위 기준. 추가 보너스 (치명타, 비밀 노출). |
| success | `total > required_roll` | 깔끔한 성공. |
| partial_success | `total == required_roll` | 대가를 치르는 성공 (소음, 가까스로 성공). |
| failure | `total < required_roll` | 단순 실패. |
| critical_failure | `dice <= critical_miss_threshold` (기본 1) | 원본 주사위 기준. 장비 파손/부상. |

`total = dice + mod`. **치명타는 원본 주사위로만 판정**: `mod` 가 `total` 을 움직여도 critical 을 만들거나 지울 수 없음. 프론트 `RollResult` ('success' | 'fail') 는 `grade in (critical_success, success, partial_success)` 로 매핑.

### 6.4 소셜 보정 (social_bonus)

비전투 roll 에는 actor 의 대상에 대한 affinity 가 d20 결과에 더해짐.

```python
aff = state.characters[actor].relations.get(target_id, 50)
if aff >= 50 + social.friendly_threshold:  total += +social.roll_bonus
if aff <= 50 - social.friendly_threshold:  total -= social.roll_bonus
```

모든 경계값 (`friendly_threshold`, `roll_bonus`, `affinity_success/failure/critical`) 은 `rules.social` config.

### 6.5 전투 DC [P2]

전투에서는 **10 + 대상 방어도 합산**이 DC:
```
enemy_defense = 10 + Σ(armor_effect.defense for slot in 방어 슬롯)
required_roll = round(20 / (1 + e^(-k(enemy_defense - player_stat))))
```

- 무기 range ≤ 1.5 → STR, 초과 → DEX 를 `player_stat` 으로 사용.
- 장비 없을 때는 `UNARMED_DAMAGE="1d4"`, `UNARMED_RANGE=1.5` 폴백.
- 방어도 합산 슬롯은 P2 에서 확정 (현재 프론트는 head/top/bottom/feet 체계, §11.4 참조).

---

## 7. 전투 [P2]

> P1 은 `{action: "combat"}` 을 `SSE error(CombatNotSupported)` 로 반환한다. 아래는 P2 예정 설계.

### 7.1 전투 상태

엔진이 `combat_state` 를 관리:

```json
{
  "turn_order": ["player_01", "goblin_01", "goblin_02"],
  "current_turn": 0,
  "round": 1,
  "surprise": "enemy"
}
```

- `turn_order`: `d20 + base_stat` (기본 DEX) 내림차순.
- `current_turn`: 현재 행동할 엔티티 인덱스.
- `round`: 라운드 번호.
- `surprise`: 기습당한 쪽. 해당 쪽은 1라운드 행동 불가. null 이면 기습 없음.

### 7.2 플레이어 턴

매 턴 DC판정 에이전트 호출:
- "고블린을 공격" → `{action: "combat"}` → 엔진 자동 주사위
- "샹들리에 떨어뜨리기" → `{action: "roll", tier, stat}` → 플레이어 주사위 (비전투 플로우 재사용)

플레이어는 매 턴 행동을 **선택**함. 자동인 건 주사위만.

### 7.3 NPC AI

확률 기반 규칙 엔진 (LLM 미사용). 각 NPC 는 `combat_behavior` 필드로 동작을 지정.

**공격 대상 선택**:
- `nearest_weight`: 가장 가까운 적 선택 가중치 (기본 70)
- `random_weight`: 랜덤 다른 적 선택 가중치 (기본 30)
- `attack_priority`: nearest / lowest_hp / highest_threat / healer_first / random
- 적 판정은 **affinity < 50** 기준. 같은 location 안, 살아있는 엔티티만.

**도주**:
- `flee_hp_percent` 미만일 때 `flee_prob = (임계값 - 현재HP%) * 2` 확률로 도주 시도.
- 도주 주사위: `d20 + dex_mod vs flee.base_dc` (기본 12). 성공 시 전투에서 제거.

`combat_behavior=None` 이면 단순 랜덤 공격. 가중치·임계값 모두 config.

### 7.4 도주 (Flee)

`rules.combat.flee`: `dice="1d20"`, `base_dc=12`, `dex_modifier=True`. 플레이어도 `flee` 명령으로 동일 메커닉 사용.

**기회 공격**: `opportunity_attack=True` (기본)일 때, 도주 굴림 전에 같은 location 의 적대적 전투 참가자들이 각 1회 자동 공격. 기회 공격으로 HP 0 이 되면 도주 굴림 없이 실패.

### 7.5 전투 종료

- 적 전멸
- 도주 성공
- 플레이어 사망 → §7.6

전투 종료 시 엔진이 `combat_state` 삭제.

### 7.6 플레이어 사망 / Death Save

`rules.combat.death`:
- `instant_death: bool = False` — True 면 HP 0 즉시 사망 (NPC/몬스터는 기본 True, 플레이어는 `revive_coins` 우선).
- `revive_coins: int = 0` — 플레이어 전용 목숨 토큰. 0 초과면 HP 0 이 되어도 토큰 1개 소모하고 `max_hp * revive_ratio` (기본 0.5) 로 즉시 부활. 토큰 소진 후에만 dying/dead 전이.
- 토큰 없고 `instant_death=False` 면 HP ≤ 0 시 death save 진입. `death_saves={successes, failures}` 할당.
- 매 턴 `d20 ≥ save_dc` (기본 10). 성공 3회 → 안정화 (HP=1). 실패 3회 → 사망. 대미지 재피격 시 실패 카운트 +1. critical_failure 시 +2.

### 7.7 SSE 확장 [P2]

- `combat_start`: `{turn_order, round}`
- `combat_turn`: `{actor, action, grade, damage?}`
- `combat_end`: `{outcome: "victory" | "defeat" | "fled"}`

P1 이벤트 집합(§3.4) 을 덮어쓰지 않고 추가만.

---

## 8. 온톨로지 (그래프)

### 8.1 구조

노드 = 엔티티 (캐릭터, 아이템, 장소). 엣지 = 관계.

**구조적 엣지**:
- `location_id`: NPC → 장소
- `equipment`: NPC → 아이템
- `inventory_ids`: NPC → 아이템
- `connections`: 장소 → 장소

**의미적 엣지** (init 시 자동 추론):
- 퀘스트 condition 의 `target_id` → `required_by` 엣지
- 퀘스트 `giver_id` → `gives_quest` 엣지
- 퀘스트 condition `character_death` → `kill_target_of` 엣지
- 퀘스트 `rewards.items` → `reward_of` 엣지

**config 정의 관계** (서사적):
- NPC 의 `hints`: 아는 정보/퀘스트 연결
- Item 의 `key_item_id`: 열쇠 → 문 연결
- Item 의 `unlocks`: 아이템 → 오브젝트 연결

**런타임 관계**:
- `memories[]`: 엔티티별 기억 (§9)

### 8.2 target_view 조립

target 에서 그래프 1-2홉을 탐색하되, **이종 엣지 타입도 순회** 가능.

예: `guard_01 → gives_quest → quest_01 → condition → plaza_01` (퀘스트 관련 장소까지 도달).

구현은 `src/ontology/graph.py` 가 매 호출마다 `GameState` 에서 임시 그래프를 구성. 성능 최적화(인덱싱·캐시)는 P1 이슈 아님.

### 8.3 장소 확장

```python
Location(
    hidden_items=[...],         # 수색 성공 시 발견
    hidden_connections=[...],   # 수색 성공 시 통로 발견
    search_dc="moderate",       # 수색 난이도 등급
)

Connection(
    target_id="cellar",
    lock_dc=15,
    key_item_id="iron_key",   # 이 열쇠 보유 시 자동 해제
)
```

---

## 9. 메모리 시스템

### 9.1 구조

모든 엔티티(NPC, 장소, 플레이어) 공통:

```python
class Memory:
    content: str       # "플레이어가 뇌물을 줘서 통과시켜줌"
    importance: int    # 1: 사소, 2: 보통, 3: 중요
    turn: int          # 기록된 턴 번호
```

### 9.2 저장

내러티브 에이전트가 `memorable=true` 로 판정하면, 엔진이 `memory_targets` 의 각 엔티티 `memories[]` 에 저장. narrator 는 `memories[]` 필드를 `set` 으로 건드릴 수 없고 (§10), 오직 이 경로로만 추가.

### 9.3 용량 관리

- 엔티티당 최대 N 개 (`rules.memory.cap`, 기본 20).
- cap 도달 시: importance 낮은 것부터 제거. 같은 importance 면 오래된 것 (turn 작은 것) 부터 제거.
- 모순되는 메모리는 둘 다 저장. 내러티브 에이전트가 시간순으로 해석 ("예전엔 믿었는데 배신당했다").

### 9.4 활용

- `target_view` 에 target 의 `memories[]` 포함 → 내러티브가 NPC 기억을 반영.
- 스탯 어뷰즈 방지: "또 설득하려 한다" 가 쌓이면 NPC affinity/disposition 이 내려가고, 그 결과가 **다음 턴의 `surroundings` 상태 태그**에 드러난다 (예: `경계중(affinity 25)`). DC판정은 이 태그를 보고 자연스럽게 tier 를 올린다 — 메모리 자체를 직접 읽지 않는다.

---

## 10. 상태 업데이트

### 10.1 state_changes 형식

내러티브 에이전트가 배출할 수 있는 타입은 **4종** (`Literal["set","move","move_item","affinity"]`):

```json
[
  {"type": "set",       "entity": "characters", "id": "guard_01", "field": "disposition.aggressive", "value": 80},
  {"type": "move",      "target": "player_01",  "destination": "plaza_01"},
  {"type": "move_item", "item":   "iron_key",   "from": "chest_01", "to": "player_01"},
  {"type": "affinity",  "actor":  "player_01",  "target": "guard_01", "grade": "success", "intent": "friendly"}
]
```

- `set.entity` ∈ `characters | items | locations`. `set.field` 는 점 표기 경로 (`disposition.lawful`, `weather` 등).
- **list 필드 (`relations`, `inventory_ids`, `memories`, `goals`, `basic_skills`, `learned_skills`, `companions`) 는 `set` 으로 조작 불가**. 엔진 전용(HP/MP/exp/gold/alive/in_combat/death_saves 등) 도 금지.
- `affinity` 는 `grade × intent × target.disposition` 으로 `rules.social` 기반 delta 를 엔진이 산출. narrator 는 숫자를 정하지 않는다 (§11.1).
- `move` / `move_item` / `affinity` 적용 시 엔진이 자동으로 **퀘스트 트리거** 실행 (`location_enter`, `item_use`, `character_death`) [P3].

**검증과 `rejected[]`**: `apply_changes` 는 narrator 출력을 Pydantic union 으로 validate. 스키마 위반 (잘못된 필드명, 알 수 없는 타입, 엔진 전용 필드 set 등)은 해당 항목만 `rejected[]` 로 돌려보내고, 나머지 유효 변경은 적용. 반환: `{applied, rejected, world_time, created_ids?, quest_updates?, chapter_updates?}`. 오케스트레이터는 `rejected[]` 를 로깅만 하고 narrator 재호출은 하지 않는다 [P3 에서 재호출 루프 검토].

**내부 전용 타입** (엔진/CLI 만 사용, narrator 는 발행 금지):
- `{"type": "death", "target": "<id>"}` — 캐릭터 사망 처리 + 시체/드랍/퀘스트 연쇄. [P2]
- `{"type": "create", "entity": "items|characters|locations|races|quests", "data": {...}}` — 런타임 엔티티 생성, ID 자동 부여. [P3]

경계를 둔 이유: 내러티브 에이전트가 직접 엔티티를 생성/살해하지 못하게 해 상태의 결정권을 엔진에 묶어 둠.

### 10.2 프론트 반영

`apply_changes` 후 엔진은 변경된 슬롯만 `mapping/to_front.py` 로 재직렬화해 `state_patch` 이벤트 방출. 예를 들어 `characters[player_01].location_id` 변경 → `state_patch: {place: {...}}`. 슬롯 단위는 Hero / Subject / Quest / Place 4종 (Log 는 별도 `log_entry` 이벤트). §14.

---

## 11. 확장 시스템

Phase 별로 구현 범위가 다름. 수치는 모두 `config/rules.py` 에서 튜닝.

### 11.1 호감도 (Affinity) [P1 최소, P3 완성]

`compute_affinity_delta(grade, intent, social, disposition)` 가 grade·intent·disposition 을 조합해 Δaffinity 를 계산, `apply_affinity(actor, target_id, delta)` 가 [0, 100] clamp 하여 `relations` 를 갱신.

- grade → delta: success/partial_success 는 `social.affinity_success`, failure 는 `social.affinity_failure`, critical_success 는 `social.affinity_critical`, critical_failure 는 `-social.affinity_critical`.
- intent 보정 [P3 disposition 보정 포함]:
  - `hostile`: delta 부호 반전.
  - `deceptive`: 성공 시 0 (속임수는 호감도 안 오름), 실패 시 delta ×2.
- disposition 보정 [P3]:
  - lawful ≥ 70 + intent=deceptive + delta<0: ×1.5 (율법가가 거짓에 더 크게 실망)
  - aggressive ≥ 70 + intent=hostile + delta<0: ÷2 (공격적 성향은 도발을 덜 싫어함)
  - moral ≥ 70 + intent=friendly + delta>0: ×1.5

neutral 은 50. `get_affinity()` 는 relation 이 없으면 50 반환. P1 은 grade·intent 까지만. disposition 보정은 P3.

### 11.2 월드 시간 (World Time)

`state.world_time` (ISO 8601). [P1 은 턴당 +1분 고정 / P3 는 액션별 `advance_time(action_type, grade, state, rules)`].

P3 `rules.time.cost` (단위: 분):
- `combat_turn_min`: 전투 1턴 경과 시간
- `explore_action_min`: 탐험/조사 기본 소요
- `explore_critical_fail_min`: critical_failure 추가 지연
- `travel_per_connection_min`: 기본 이동 비용

`Connection.travel_min` 설정 시 per-edge override 가 기본값을 대체.

프론트 `Place.date` ("812년 4월 28일"), `Place.hour` (0..23) 은 `mapping/to_front.py` 가 `world_time` 을 파싱해 분리.

### 11.3 성장 (Growth) [P3]

`src/pipeline/growth/` 에 3종 루틴:

- **rest**: `rules.time.recovery` 에 따라 HP/MP 회복. `--minutes N` 또는 `--full`. world_time 동기 경과.
- **train**: `xp_pool` 을 소모해 스탯 +1. 비용 = `base_xp + xp_per_point * max(0, current-10)`. 상한 `max_stat` (기본 20). **시간 경과 없음** (즉시 반영; 훈련 장면 연출은 narrator).
- **learn**: 스킬을 `learned_skills[]` 에 추가. `skill.xp_cost` 소모. **시간 경과 없음**.

P1 에서는 자연어 "휴식한다" → `{action: "skip"}` + narrator `set` 으로만 간접 반영 (HP/MP 는 엔진 전용이라 실제 회복 없음). P3 에서 명시 엔드포인트로 노출.

### 11.4 장비 / 인벤토리 / 거래 [P3]

**장비 슬롯 (프론트 기준 8종)**: `head / top / bottom / feet / leftHand / rightHand / acc1 / acc2`. `Equipment` 타입이 단일 소스. 각 슬롯은 `EquipItem | null`.

- `equip` / `unequip` 엔드포인트. `Item.required` (Stats) 미충족 시 거부.
- `Item.effects` 가 `WeaponEffect` 면 무기, `ArmorEffect` 면 방어구. 무기는 `rightHand` 기준, 방어도는 `head / top / bottom / feet` 합산.
- `ActiveBuff(skill_id, stat, modifier, remaining_turns)` + 장비 수정자를 합산해 `get_effective_stat()` 이 실효 스탯 반환.

> 레거시는 `head/left_hand/right_hand/chest/legs/necklace/ring_1/ring_2` 8슬롯. 프론트 UI 는 `head/top/bottom/feet/leftHand/rightHand/acc1/acc2`. 외부 계약은 프론트 기준이며, 레거시 전투 공식(`head/chest/legs` 방어도 합산)을 새 슬롯으로 매핑하는 세부는 P2 전투 설계 때 확정.

**인벤토리**: `inventory_ids: list[str]`. `rules.carry.weight_per_strength` (기본 10.0) × STR 을 최대 무게로 사용. `check_can_carry()` 가 `buy` / `move_item` 에서 검증.

**거래**:
- `buy(actor, item, from=npc, ...)` — `rules.social.trade_threshold` (기본 0, neutral 이상이면 거래) 검사 → 골드/무게 검증 → affinity 할인 적용 후 이전.
- `sell(actor, item, to=npc)` — 가격 × `rules.trade.sell_ratio` (기본 0.5) × affinity 보너스.
- **흥정**: `rules.trade.affinity_price_per_point` (기본 0.01) × (affinity − 50) 이 할인/보너스 비율. affinity 70 → 20%, 100 → 50% (상한). 0 으로 끄면 고정 가격.

프론트 `Subject.inventory` 는 `InventoryItem{name, qty}` 배열. 내부 `inventory_ids` 를 Counter 로 집약해 qty 생성 (같은 `item_id` 개수).

### 11.5 스킬 시스템 [P3]

`Skill(id, name, description, type, target, power, mp_cost, range, required_stats, xp_cost, buff_stat, duration)`.

- `type`: attack / heal / buff / debuff.
- `target`: self / single / area.
- 캐릭터는 `basic_skills` (종족/직업 기본) / `racial_skills` / `learned_skills` 로 분리 저장. `all_skills()` 로 병합 조회.
- `cast` 파이프라인: MP 검증 → 사정거리 검증 → AoE 대상 자동 계산 → 데미지/회복/버프 적용 → 퀘스트 트리거.
- `ActiveBuff` 는 `duration` 턴 동안 유지. 턴 종료 시 `tick` 이 감소.

P1 프론트 `Hero.skills: string[]` 는 UI 태그만 노출. 효과 계산은 P3.

### 11.6 사용 / 소비 (Use) [P3]

`use --actor A --item I [--target T]`:
- `ConsumableEffect(heal, damage)` 에 따라 HP 변화.
- `Item.special` 의 `on_use` 트리거 실행 (예: 열쇠, 퀘스트 아이템).
- 아이템이 `consumable` 이면 인벤토리에서 제거.

### 11.7 진행 (Progression) [P3]

**구조**: `Campaign` → `Chapter` → `Quest` 3-tier.

- `Quest(giver_id, prerequisite_ids, conditions[], fail_conditions[], rewards, status, required)`.
- `QuestCondition(type, target_id)`. 타입: `location_enter`, `character_death`, `item_use`, …. `Quest.conditions_met: list[bool]` 가 조건별 완료 여부를 병렬 저장 (킬 카운트 같은 누적 조건은 미지원 — `required_by` 엣지만 쓰는 단일 충족 모델).
- `status`: `locked → active → completed | failed`.
- `apply_changes` 이후 `check_quests()` 가 관련 트리거로 조건 재평가. 완료/실패 시 `maybe_check_chapters()` 가 상위 전환.

세션 레이어(§5.2) `active_chapter.progress` 는 **`required=true` 퀘스트만** 카운트.

P1 은 narrator 가 `{type: "set", entity: "quests", id, field: "status", value: "completed"}` 로만 간접 반영. 자동 트리거는 P3.

### 11.8 동반자 (Companions, pocket-monster 방식) [P3]

`Character.companions: list[str]` — patron 이 "주머니에 넣고 다니는" 부하 캐릭터 ID 목록.

- **위치 동기화**: `effective_location(char, state)` 이 patron 의 `location_id` 를 반환. 동반자 본인의 `location_id` 는 스토리지 용도로만 유지.
- **전투 참여**: `start_combat(participants)` 가 participants 각자의 `companions` 를 자동 확장해 turn_order 에 포함 (중복 제거). 동반자는 자기 DEX 로 initiative 를 굴린다.
- **피아 식별**: 같은 patron 을 공유하는 두 엔티티를 아군으로 간주. NPC AI 는 patron 관점 affinity 로 적을 찾으므로 동반자는 자동으로 patron 의 적을 공격.
- **비전투 호출**: `target_view` / `surroundings` 의 NPC 목록에도 patron 과 함께 노출되며 별도 slot 이 아님.

제약: 동반자 본인에게는 AI 가 없어 1인칭 대사·반응은 narrator 서술로만 표현. 향후 `companion_voice_hint` 같은 필드를 고려.

P1 프론트 `Hero.companions: string[]` 는 이름 리스트만 노출. 내부 동반자 로직은 P3.

### 11.9 설계자(Design) 에이전트

`src/agents/design/creator.md` (레거시) — 엔티티 저작 가이드. 플레이 런타임에는 포함되지 않고, 디자이너가 신규 아이템·NPC·장소·퀘스트를 만들 때 참고하는 밸런스 테이블·체크리스트. back 에서는 `config/profiles/{name}/` 에 JSON 시드로만 반영. 저작 에이전트 자체는 당분간 생략.

---

## 12. 설계 결정 히스토리

### 12.1 왜 시그모이드 DC 인가?

기존 TTRPG (D&D) 는 선형 DC (`d20 + modifier >= DC`). 선형은 플레이어가 암산할 때 유리하지만, 이 게임에서는 엔진이 계산하므로 투명성 이점이 약함.

시그모이드의 장점:
- 극단값이 자연스럽게 수렴 (0~20 범위 자동 제한). 선형은 별도 분기 필요.
- stat >> DC 여도 최소 1은 굴려야 함 (기적/재앙 가능성 유지).
- 스탯 차이에 따른 체감이 비선형 — 실제 능력 차이의 체감에 가까움.

### 12.2 왜 에이전트를 2개로?

초기엔 3개 (DC판정 / 내러티브 / 기록). 기록을 분리하면 관심사 분리가 깔끔하지만:
- 내러티브 에이전트가 이미 전체 맥락을 갖고 있어서 summary/memorable 판정 품질이 더 높음
- LLM 호출 1회 절약 (latency, 비용)

→ 내러티브에 합쳐서 2개로.

### 12.3 왜 NPC 관점으로 target_view 를 조립하는가?

"LLM 에 뭘 줄까" 의 기준이 필요했음. "경비병이 1인칭이라면 뭘 알까?" 로 생각하면 자연스럽게 범위가 결정됨:
- 경비병이 아는 것: 자기 성격, 임무, 플레이어에 대한 인상, 최근 사건
- 경비병이 모르는 것: 플레이어 스탯, 다른 장소 상황, 플레이어 퀘스트 목록

→ target 엔티티의 지식 범위 = target_view. NPC/장소/오브젝트 공통 로직 (그래프 1-2홉).

### 12.4 왜 1턴 1액션 인가?

"설득하면서 동료가 금고를 턴다" 같은 복합 행동:
- DC판정이 하나의 action 만 반환하는 구조
- 복합 행동을 자동 분해하면 예측 불가능한 결과
- TTRPG 에서도 1턴 1행동이 표준

→ clarify 로 분해 유도. "설득과 도둑질 중 먼저 할 건?"

### 12.5 왜 매 턴 독립 에이전트인가?

Claude Code 대화창에 의존하면 플랫폼 종속. 독립 에이전트 구조면:
- 어떤 LLM 이든 교체 가능
- 컨텍스트 윈도우 한계와 무관 (매 턴 필요한 것만 전달)
- 테스트/디버깅이 쉬움 (각 턴을 독립적으로 재현 가능)

대신 히스토리 관리가 필요 → 히스토리 레이어 + 메모리 시스템.

### 12.6 왜 메모리에 importance 를 넣는가?

cap(최대 N 개) 도달 시 단순 시간순 제거는 "고블린 족장을 살려줬다" 같은 중요한 기억이 사라질 수 있음. importance 기반 제거면 사소한 기억부터 정리.

또한 모순 메모리(예: "신뢰함" → "배신당함")를 둘 다 저장하되, 시간순 해석으로 자연스러운 서사 가능.

### 12.7 왜 전투에서 엔진 자동 주사위인가? [P2]

매번 플레이어가 주사위 굴리면 전투가 번거로움. 엔진이 자동 처리하되, **행동 선택은 플레이어가 매 턴 수행**. 주사위의 번거로움만 없앤 것이지 agency 를 뺀 것이 아님.

특수 행동 ("샹들리에 떨어뜨리기") 은 DC판정이 `roll` 로 분류하여 플레이어가 직접 주사위.

### 12.8 전투 NPC AI 는 왜 확률 기반인가? [P2]

LLM 에 맡기면:
- 매 NPC 턴마다 LLM 호출 (비용, latency)
- 일관성 없는 판단

확률 규칙 엔진이면:
- 즉각 처리
- 예측 가능하면서도 랜덤성 있음
- config 로 튜닝 가능

가장 가까운 적 공격 확률 70%, 랜덤 30%. HP 낮으면 확률적 도주. 가중치 전부 config.

### 12.9 왜 CLI 에서 REST + SSE 로?

레거시는 `.venv/bin/python src/cli/main.py <command>` 기반 오케스트레이터. 스모크 테스트·디버깅에는 좋지만 프론트(React Native) 와 붙이려면:
- 네트워크 경계가 필요 (폰에서 `back/` 을 직접 실행 불가)
- 점진 표시가 필요 (내러티브 스트리밍)
- 상태 조회·갱신이 HTTP 관용어에 얹혀야 함

→ FastAPI 라우트 4개 + SSE. CLI 의 `scene` / `apply` / `roll` 은 각각 `GET /state` / 내부 `apply_changes` / `POST /roll` 로 흡수. CLI 는 디버그용으로만 유지 가능 (P1 필수 아님).

### 12.10 왜 두 단계 턴(pending_check) 인가?

`roll` 분기는 "엔진이 DC 를 계산하면 플레이어가 주사위를 굴려야" 진행된다. 한 HTTP 요청으로 처리하려면 두 옵션:

(a) WebSocket 양방향 — 프론트·백 양쪽에 상태기계. 연결 유실 시 복구 복잡.
(b) 서버가 DC 계산 후 랜덤 주사위를 자동으로 굴려 결과까지 반환 — 플레이어가 주사위를 "굴리는" 감각이 사라짐.

대신 턴을 쪼갰다:
- `/turn` 이 `pending_check` 로 끝 → 프론트에서 주사위 버튼 UI
- `/roll` 로 주사위 값 전달 → 내러티브 이어서

상태는 서버의 `GameState.pending_check` 에 저장되므로 연결이 끊겨도 `GET /state` → UI 복원 가능. 프론트 `use-game` 훅은 state machine (`idle → streaming → awaiting_roll → streaming → idle`) 으로 모델링.

### 12.11 왜 상태를 JSON 파일 한 덩이로?

P1 은 단일 사용자, LAN 내부. 요구 규모:
- 하나의 게임 세션당 엔티티 수백 개 이내
- 초당 쓰기 빈도 낮음 (턴 단위)
- 트랜잭션·다중 사용자·복잡한 쿼리 없음

DB 는 초기 오버헤드. 파일 한 덩이는:
- 인스펙션 쉬움 (에디터로 열면 끝)
- 버전관리·백업이 단순 (cp / git)
- 파일 이동만으로 게임 인스턴스 이전 가능

원자적 쓰기는 `.tmp` → `os.replace`, 동시성은 프로세스 레벨 `asyncio.Lock` 1개로 충분. 사용자 수·세션 수 늘어나면 P3 이후 SQLite 로 전환 검토.

### 12.12 왜 DC판정에는 히스토리를 주지 않는가?

DC판정은 "지금 이 입력이 어떤 종류의 행동인가, 얼마나 어려운가" 만 분류하면 된다. 프롬프트에 과거 턴 요약·메모리·세계관을 넣으면:
- 토큰 낭비 (판정은 가볍고 자주 호출됨)
- 판정이 서사적으로 오염 ("어제 배신당했으니 이번 설득은 hard" 같은 추론은 내러티브 몫)
- 재현성이 떨어짐 (같은 입력·같은 장면에서 판정이 달라짐)

장기 맥락의 영향은 이미 **현재 상태**에 누적되어 있다. NPC 의 affinity 가 내려갔거나 disposition 이 경계 쪽으로 움직였으면 `surroundings` 의 상태 태그에 그대로 드러난다. DC판정은 그 스냅샷만 보면 충분.

내러티브는 반대다. "왜 지금 이 반응인가" 를 서술해야 하므로 과거 턴·메모리가 필요.

→ 레이어 분리: **DC판정 = 장면 레이어만 / 내러티브 = 4 레이어 전부**.

### 12.13 왜 프론트 매핑을 단일 관문으로?

프론트 타입(`front/types/domain.ts`) 은 **UI 에 노출되는 필드만** 포함. 내부 도메인은 `disposition`, `tone_hint`, `location_id`, `memories` 등 많은 힌트·계산 필드를 가진다. 이것들이 무분별하게 프론트로 새면:
- 프론트가 내부 구조에 결합되어 바꾸기 어려움
- 플레이어가 UI devtools 로 "NPC 내심 점수" 같은 걸 보게 됨 (게임 경험 손상)

→ `mapping/to_front.py` 하나만 프론트 방향 직렬화를 담당. 다른 어떤 경로로도 내부 필드가 SSE/REST 응답에 실려선 안 됨. 이건 테스트로 강제 (`test_internal_fields_not_leaked`).

---

## 13. 코드 지도

### 13.1 모듈 구조

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

### 13.2 레이어 경계

- `domain/` + `ontology/` = 내부 풀 스키마. 레거시 계산 필드 포함.
- `pipeline/` = 턴 로직. 순수 파이썬, FastAPI 의존 없음 (테스트에서 TestClient 없이도 돌릴 수 있어야).
- `api/` = 얇은 어댑터. 라우팅·요청 검증·SSE 인코딩만.
- `mapping/to_front.py` = 유일한 프론트 노출 지점 (§12.12).
- `state/store.py` = 파일 I/O 경계. 파이프라인은 스토어를 통해서만 저장 상태에 접근.

---

## 14. 프론트 경계

### 14.1 노출 슬롯

| 프론트 타입 | 소스 | 노출 필드 |
|---|---|---|
| `Hero` | `characters[player_id]` | name, race, class, level, exp, expMax, hp, hpMax, mp, mpMax, stats, equipment, inventory, status, skills, companions |
| `Subject` | `characters[active_subject_id]` | name, role, race, class, trust, known, level, hp, hpMax, stats, inventory |
| `Quest` | `quests[active_quest_id]` | title, giver (이름), difficulty, goals, conditions, rewards, memo |
| `Place` | `locations[characters[player_id].location_id]` | name, date, hour, weather, features, surroundings |
| `LogEntry` | `turn_log` + 이벤트 부산물 | `gm / player / act / roll` 4종 union |

- `Subject.trust = characters[active_subject_id].relations.get(player_id, 50)` — **대상이 플레이어를 어떻게 느끼는가** (반대 방향 아님).
- `Subject.inventory` 는 내부 `inventory_ids` 를 Counter 로 집약해 `{name, qty}` 배열 (§11.4).
- `Place.date` 는 한국어 포맷 ("812년 4월 28일"), `hour` 는 0..23. `world_time` (ISO) 을 파싱.
- 내부 전용 필드(`disposition`, `tone_hint`, `memories`, `location_id`, `relations`, `combat_behavior` 등) 는 **절대 노출 금지**.

### 14.2 외부 API

| 메서드 | 경로 | 바디 | 응답 |
|---|---|---|---|
| POST | `/session/init` | `{profile: string}` | `{game_id, state: FrontState}` |
| GET  | `/session/{id}/state` | — | `FrontState` |
| POST | `/session/{id}/turn` | `{player_input: string}` | `text/event-stream` |
| POST | `/session/{id}/roll` | `{dice: int (1..20)}` | `text/event-stream` |

`FrontState = {hero, subject, quest, place, log}`.

### 14.3 에러 매핑

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

---

## 부록 A: 레거시 CLI ↔ 신규 API/파이프라인 대응

레거시 `.venv/bin/python src/cli/main.py <command>` 에 대응하는 back 의 엔드포인트/함수:

| 레거시 CLI | 역할 | back 대응 |
|---|---|---|
| `init` | 새 게임 인스턴스 생성 | `POST /session/init` → `state.init.init_game` |
| `scene --actor ID` | surroundings + session + history 조립 | `GET /session/{id}/state` (프론트 슬롯으로) + 내부 `pipeline.context.build_*` |
| `target-view --actor --target` | target_view 조립 | 내부 `ontology.target_view.build` (직접 노출 없음, narrate 호출 때만 사용) |
| `validate-target --actor --target` | target 유효성 확인 | 내부 `pipeline.judge` 의 폴백 로직 |
| `roll --actor --stat --tier [--target]` | sigmoid 판정 + social_bonus | `POST /session/{id}/turn` (action=roll 분기) + `POST /session/{id}/roll` |
| `initiative --actors a,b,c` | 전투 이니셔티브 [P2] | 내부 `pipeline.combat.start_combat` [P2] |
| `attack --actor --target` | 무기 전투 판정 [P2] | `/turn` action=combat 분기 [P2] |
| `cast --actor --skill --targets` | 스킬 시전 [P3] | `/turn` + `pipeline.skill.cast` [P3] |
| `defend --actor` | 방어 자세 [P2] | `/turn` [P2] |
| `flee --actor` | 도주 판정 [P2] | `/turn` [P2] |
| `death-save --actor` | HP 0 회복 판정 [P2] | 자동 (`pipeline.turn` 내부) [P2] |
| `move --actor --destination` | 이동 + 잠금 + world_time | narrator `{type: "move"}` state_change |
| `rest --actor [--minutes N]` [P3] | HP/MP 회복 + 시간 경과 | `POST /session/{id}/rest` [P3] |
| `train --actor --stat` [P3] | XP → 스탯 | `POST /session/{id}/train` [P3] |
| `learn --actor` [P3] | 스킬 습득 | `POST /session/{id}/learn` [P3] |
| `use --actor --item` [P3] | 소비 아이템 사용 | `POST /session/{id}/use` [P3] |
| `search --actor` [P3] | 숨겨진 아이템/통로 공개 | `/turn` + narrator `set hidden_items` [P3] |
| `equip / unequip` [P3] | 장비 장착/탈착 | `POST /session/{id}/equip` [P3] |
| `buy / sell` [P3] | 상거래 | `POST /session/{id}/trade` [P3] |
| `combat-start / combat-next / combat-end` [P2] | 전투 루프 | 내부 자동 (SSE `combat_*` 이벤트) [P2] |
| `apply --changes JSON` | state_changes 적용 | 내부 `pipeline.apply.apply_changes` (narrator 가 호출) |
| `memory --targets JSON --content --importance` | 직접 메모리 저장 | 내부만 (narrator 의 `memorable=true` 로만 저장) |

P1 범위는 이 표의 **굵지 않은 6줄** (init / scene / validate / roll / move / apply).

---

## 부록 B: Phase 현황

### B.1 P1 (현재 구현 중)

- FastAPI 골격, 세션 생성·로드·저장 (파일 JSON)
- 턴 파이프라인: judge → (roll 분기 시 pending → 프론트 주사위 → /roll) → narrate → apply
- 컨텍스트 조립: surroundings, target_view, history
- 도메인 스키마, GameState 컨테이너, 내부↔프론트 매핑
- SSE: `judge / pending_check / narrative_delta / state_patch / log_entry / done / error`
- 단일 프로필 로더 (`config/profiles/default/`)
- 최소 메모리·호감도·월드 시간 (grade·intent까지, disposition 보정은 P3)
- LAN 내부만 (env fail-fast, 인증 없음)

### B.2 구현된 확장 필드 (narrator 힌트용, P1 에서 이미 노출)

구조만 엔진이 제공하고 강제 규칙은 없는 "묘사용 힌트" 필드. narrator 가 자연어로 반영할지 판단.

- **날씨**: `Location.weather: list[str]` 가 surroundings 의 location 섹션에 노출. 엔진은 자동 변화시키지 않으며, narrator 가 `set locations.{id}.weather` state_change 로 갱신.
- **NPC 영업시간**: `Character.active_hours: str | None` (예: `"08:00-22:00"`, 자정 걸치는 `"22:00-06:00"` 지원). 값이 있으면 surroundings NPC 엔트리에 `active: bool` 플래그가 붙음. 엔진은 거래 등에서 강제하지 않음 (P3 에서 강제 고려).

### B.3 P2 (전투)

- `combat_state`, 이니셔티브, `/turn` action=combat 분기
- 전투 DC (방어도 합산), 무기 range 기반 스탯 선택
- NPC AI (확률 규칙, `combat_behavior`)
- 도주 (기회 공격 포함), death save, revive_coins
- SSE 이벤트 추가: `combat_start / combat_turn / combat_end`
- 내부 `state_change` 타입 `death` 활성화

### B.4 P3 (확장)

- 장비 장착/탈착, 인벤토리 무게, 거래 (buy/sell/흥정)
- 성장 루틴 (rest / train / learn)
- 스킬 시전 파이프라인 (`cast`), `ActiveBuff` 틱
- 퀘스트 자동 진행 (`check_quests`), 챕터·캠페인 전환
- 동반자 시스템
- 메타 액션 REST 엔드포인트 (버튼 기반 equip/rest 등)
- `rejected[]` 기반 내러티브 자가 보정 루프
- 월드 시간 세밀화 (이동·휴식·전투 턴별 경과)
- affinity disposition 보정 (lawful/aggressive/moral)
- 인증·외부 노출 (LAN 해제)

### B.5 명시적 제외

구현하지 않기로 결정한 영역:

- 비전투 NPC AI 자율 스케줄
- 아이템 내구도 / 파손
- 날씨·환경의 자동 이벤트
- 파티(파티원 선택·해산) 시스템 — §11.8 companions 가 동일 요구를 pocket-monster 방식으로 충족

### B.6 알려진 간극 (미구현이지만 열려 있음)

- 스킬 사용 중 사정거리 외 자동 재배치
- NPC ↔ NPC 상거래
- 잠긴 문 / 상자의 물리적 파괴 경로 (현재는 열쇠 / lockpick roll 만)
- 킬 카운트 같은 누적 퀘스트 조건

---

## 부록 C: 환경 변수

`run_api.py` 기동 시 fail-fast (누락 시 throw, `??` fallback 금지).

| 변수 | 용도 | 예시 |
|---|---|---|
| `HOST` | FastAPI 바인드 | `0.0.0.0` |
| `PORT` | 서비스 포트 | `8000` |
| `BASE_URL` | llama.cpp OpenAI-compat URL | `http://127.0.0.1:8080/v1` |
| `DATA_DIR` | 게임 저장 루트 | `./data` |
| `PROFILE_DIR` | 프로필 루트 | `./config/profiles` |
| `DEFAULT_PROFILE` | `/session/init` 기본 profile 이름 | `default` |

프론트 측 `EXPO_PUBLIC_API_URL` 은 `http://{HOST}:{PORT}` 를 가리키며, 폰 테스트 시 LAN 내부 IP 를 사용 (터널·외부 노출은 인증 붙을 때까지 보류).
