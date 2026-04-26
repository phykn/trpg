# 기능 확장 (§1-§2)

> 기본 런타임 ([02-runtime.md](./02-runtime.md) §1-§7) 위에 얹히는 시스템들. 전투, 시간, 호감도, 성장, 회복, 장비/거래, 스킬, 사용, 진행, 동반자.
> 인덱스는 [01-overview.md](./01-overview.md). 런타임 메커닉은 [02-runtime.md](./02-runtime.md), 프론트 경계는 [04-boundary.md](./04-boundary.md), 백엔드 코드 지도는 [05-codemap.md](./05-codemap.md).

이 문서는 두 묶음을 다룬다. **§1 전투** 는 P2 부터 켜진다. **§2 확장 시스템** 은 9 개로 — 이 중 월드 시간과 호감도는 P1 부터 최소 형태로 들어가고 (호감도는 P3 에서 완성), 나머지 7 개는 P3 에서 추가. Phase 별 범위는 [01-overview.md](./01-overview.md) §2 참고.

---

## 1. 전투 [P2]

> P2 에서 전투가 켜진다. 플레이어가 `{action: "combat"}` 으로 들어오면 엔진이 `combat_state` 를 띄우고 라운드 루프로 진입. 라운드 본문은 LLM 안 부르고 결정론으로 진행, SSE `combat_start` / `combat_turn` / `combat_end` 로 진행 상황을 흘림. 한국어 묘사를 LLM 으로 살리는 것은 후속.

### 1.1 전투 DC 와 데미지

**DC (Difficulty Class — 난이도 등급)** 는 명중 굴림이 넘어야 하는 최소 d20 값. 적의 방어도가 높을수록 DC 도 높아져 맞히기 어려워진다.

```
enemy_defense = 10 + Σ(armor_effect.defense for slot in 방어 슬롯)
required_roll = round(20 / (1 + e^(-k(enemy_defense - player_stat))))
```

기준치 10 에 적이 입은 방어구의 방어도를 모두 더해 `enemy_defense` 를 만들고, 그 값과 공격자 스탯의 차이를 시그모이드로 눌러서 굴려야 할 d20 값을 정한다. 계수 `k` 는 [02-runtime.md](./02-runtime.md) §5.1 의 `rules.difficulty_class.sigmoid` 에서 튜닝.

- 어떤 스탯을 `player_stat` 으로 쓸지는 무기로 갈린다 — 사거리 1.5m 이하 근접 무기는 STR (힘), 그보다 멀면 DEX (민첩). DC 굴림과 데미지 modifier 가 같은 스탯을 공유.
- 무기 없는 맨손은 `UNARMED_DAMAGE="1d4"`, `UNARMED_RANGE=1.5` 폴백.
- **range 단위는 미터 (실수)**. 같은 location 안의 추상적 거리이고 격자·hex 같은 정밀한 위치 모델은 없다. 1.5m 이하 = 근접 (STR), 초과 = 원거리 (DEX). 같은 단위가 §2.6 스킬 cast 의 사정거리 검증에도 그대로 쓰인다. 다른 location 의 적은 무조건 사거리 밖.
- 방어도를 합산하는 슬롯은 `head / top / bottom / feet` 4 개. 각 슬롯의 ArmorEffect.defense 를 더한다 (§2.5).

**데미지** 는 D&D 5e 식 그대로:

- `damage = weapon_dice + primary_stat_modifier`
- `modifier = floor((primary_stat - 10) / 2)` — 스탯이 평균 10 이면 0, 거기서 2 씩 멀어질 때마다 ±1. 0 → -5, 10 → 0, 20 → +5 (§2.3 의 0..20 범위 안에서).
- 방어구는 DC 만 올린다. **명중하면 데미지 감소 없이 풀로 들어간다**. 방어구가 DC 와 데미지 양쪽을 깎는 이중 효과를 만들지 않는 것 — 한 군데서만 막는다.

**양손 공격** — 좌우 손에 무기를 모두 들고 있을 때:

- 한 턴에 손마다 따로 명중을 굴린다 (각각 `d20 + mod`) — 즉 두 번 공격 기회.
- 데미지는 비대칭. **주 손**은 `weapon_dice + mod`, **보조 손**은 `weapon_dice` 만 (mod 없음). D&D 5e 의 표준 페널티로, 양손이 한 손 대비 일방적으로 강해지지 않게 견제하는 장치.
- 주 손은 `Character.dominant_hand: Literal["left", "right"]` 로 결정. 미설정이면 `right` 기본.
- 양손 무기 (`two-handed`) 는 두 슬롯을 한 아이템이 통째로 차지하고 명중도 한 번만. 대신 weapon_dice 가 크고 mod 도 그대로 받는다.

**크리티컬 데미지**:

- `critical_success` 면 weapon_dice 만 두 번 굴리고 mod 는 한 번만 더한다 (`1d8 + 3` → `2d8 + 3`).
- 크리티컬 판정은 보정 없는 원본 d20 기준 ([02-runtime.md](./02-runtime.md) §5.3).
- `critical_failure` (원본 d20 = 1) 는 **자동 실패만 한다**. D&D 5e RAW 를 따라 자해, 장비 파손, 다음 턴 페널티 같은 옵션 룰은 도입하지 않음 (DMG variant 영역인데 변동성만 늘리고 재미는 별로). [02-runtime.md](./02-runtime.md) §5.3 표의 "의미" 컬럼에 "장비 파손/부상" 이 적혀있어도 그건 D&D 일반 의미 참고용 — **전투 데미지의 실제 룰은 본 절이 권위**.

**스킬 데미지** 는 §2.6 의 `power × primary_stat_modifier` 가 베이스, 거기에 judge 가 `special_effect` 텍스트를 읽어서 tier/grade 보정을 얹는다. 정확한 계수는 P2 작업 시.

### 1.2 전투 상태

전투가 시작되면 엔진이 `combat_state` 를 메모리에 띄운다:

```json
{
  "turn_order": ["player_01", "goblin_01", "goblin_02"],
  "current_turn": 0,
  "round": 1,
  "surprise": "enemy"
}
```

- `turn_order`: 행동 순서. 시작할 때 모두 `d20 + base_stat` (기본 DEX) 로 굴려 내림차순으로 정렬.
- `current_turn`: 지금 행동할 차례의 인덱스 (turn_order 안에서).
- `round`: 한 바퀴 돌면 +1.
- `surprise`: 기습 있으면 `"player"` / `"enemy"`, 없으면 null. 기습당한 쪽은 첫 라운드 통째로 행동 불가.

### 1.3 플레이어 턴

플레이어 차례마다 DC판정 에이전트가 호출돼 입력 자연어를 두 분기로 가른다.

- "고블린을 공격" 같은 일반 전투 행동 → `{action: "combat"}` → 엔진이 알아서 굴림.
- "샹들리에를 떨어뜨려" 같은 환경 활용 → `{action: "roll", tier, stat}` → 비전투 플로우의 일반 굴림 재사용.

플레이어는 매 턴 무엇을 할지 **선택** 한다. 자동화되는 건 주사위뿐.

오브젝트 (잠긴 문, 상자 등) 도 HP·방어도를 가져 일반 공격 대상이 될 수 있다 — 자물쇠 풀기를 포기하고 무력으로 부수고 싶을 때 쓰이는 통로. 열쇠나 lockpick 굴림과 병행 가능.

### 1.4 NPC AI

LLM 을 쓰지 않는 확률 기반 규칙 엔진. 각 NPC 의 행동은 `combat_behavior` 필드로 결정.

**공격 대상 선택** 은 두 모드 중 하나로 동작.

- `attack_priority` 가 설정돼 있으면 **단일 우선순위 모드**. 옵션은 `nearest` / `lowest_hp` / `highest_threat` / `healer_first` / `random` — 앞 4 개는 결정론, 마지막은 균등 랜덤. 이 필드가 있으면 가중치는 무시. `highest_threat` 의 위협 지표 (예: 최근 N 턴 자기에게 가한 누적 데미지) 와 `healer_first` 의 healer 판정 (heal 스킬 보유 또는 healer 태그) 의 정확한 정의는 P2 구현 시 확정.
- `attack_priority=None` 이면 **가중치 합산 모드**: `nearest_weight` (가장 가까운 적, 기본 70) 와 `random_weight` (그 외 랜덤, 기본 30) 의 정규화 확률로 추첨.
- **거리 metric**: `nearest` 는 §1.1 의 미터 단위 추상 거리로 두 엔티티 간을 비교. 같은 location 안에서만 정의되며, 다른 location 의 엔티티는 비교 대상이 아님.
- 적인지 아닌지는 **affinity < 0** 기준 (§2.2 의 [-100, +100] 스케일, 0 중립). 같은 location 안에서 살아있는 엔티티만 후보.

**도주** 는 HP 가 임계 이하로 떨어지면 시도된다.

- `flee_hp_percent` 미만일 때 `flee_prob = clamp((임계값 - 현재HP%) * 2, 0, 100)` 확률로 도주 시도. 즉 HP 가 임계 아래로 더 떨어질수록 시도 확률이 커지는 구조.
- 시도가 발동되면 `d20 + dex_mod` 로 굴려서 `flee.base_dc` (기본 12) 이상이면 성공 — 전투에서 빠진다.

`combat_behavior=None` 이면 단순 랜덤 공격. 가중치·임계값 모두 config.

### 1.5 도주 (Flee)

룰 자체는 `rules.combat.flee` 에 모여 있다 — `dice="1d20"`, `base_dc=12`, `dex_modifier=True`. 플레이어도 `flee` 명령으로 같은 메커닉 사용.

### 1.6 전투 종료

세 가지 중 하나에서 끝난다.

- 적 전멸
- 도주 성공 (어느 쪽이든)
- 플레이어 사망 → §1.7 로 분기

종료 시점에 엔진이 `combat_state` 를 지운다.

### 1.7 플레이어 사망 / Death Save [P2]

`rules.combat.death` 가 사망 처리 룰을 모은다.

- `instant_death: bool = False` — True 면 HP 가 0 이 되는 순간 즉시 사망. NPC·몬스터는 보통 이게 True 로 박혀있고, 플레이어는 `revive_coins` 가 먼저 동작한다.
- `revive_coins: int = 0` — 플레이어 전용 목숨 토큰. 0 보다 크면 HP 가 0 이 돼도 토큰 1 개를 깎고 `max_hp * revive_ratio` (기본 0.5) 만큼 회복하면서 즉시 부활. 토큰을 다 쓴 다음에야 dying / dead 상태로 넘어간다.
- 토큰이 없고 `instant_death=False` 면 HP ≤ 0 일 때 death save 단계 진입 — `death_saves={successes, failures}` 카운터가 할당된다.
- 매 턴 `d20 ≥ save_dc` (기본 10) 이면 성공, 미만이면 실패. 성공 3 회 → 안정화 (HP=1 로 복귀). 실패 3 회 → 사망. death save 도중 새 데미지를 맞으면 실패 카운트 +1, critical_failure 면 +2.
- D&D 5e 의 **nat-20 자동 1HP 회복** (death save 굴림이 자연 20 이면 즉시 살아남) 은 도입하지 않는다. 부활 통로는 `revive_coins` 토큰으로 일원화했고, 추가 자동 부활 경로를 두면 토큰의 의미가 흐려져서 의도적으로 단순화한 것.

### 1.8 SSE 확장 [P2]

P2 에 새 SSE 이벤트 3 종이 추가된다. P1 의 이벤트 집합 ([02-runtime.md](./02-runtime.md) §2.4) 을 덮어쓰지 않고 위에만 얹는다.

- `combat_start`: `{turn_order, round}`
- `combat_turn`: `{actor, action, grade, damage?}`
- `combat_end`: `{outcome: "victory" | "defeat" | "fled"}`

---

## 2. 확장 시스템

확장 시스템 9 종은 `config/rules.py` 에서 모든 수치를 튜닝한다. 4 묶음으로 묶여 있다:

1. **기반** — 시간, 호감도. 다른 시스템들이 참조하는 척도.
2. **캐릭터 자원** — 성장 (영구 스탯·레벨), 회복 (HP/MP 사이클).
3. **장착·행동** — 장비/거래, 스킬, 사용 (소비 아이템).
4. **메타** — 진행 (퀘스트), 동반자.

### 2.1 월드 시간 (World Time)

게임 세계의 현재 시각은 `state.world_time` (ISO 8601 문자열) 한 군데에 박혀 있다.

**엔진 가산** — 시간을 흐르게 만드는 주체:

- **P1** 은 단순. 턴당 +1 분.
- **P3** 은 액션 종류별로 분 단위 (`rules.time.cost`):
  - `combat_turn_min`: 전투 1 턴이 차지하는 시간
  - `explore_action_min`: 탐험·조사의 기본 소요
  - `explore_critical_fail_min`: critical_failure 일 때 추가로 까먹는 시간
  - `travel_per_connection_min`: location 간 기본 이동 비용
  - `Connection.travel_min` 이 따로 박혀 있는 엣지는 기본값 대신 그 값을 사용 (per-edge override)

**narrator 의 시간 점프 (`set_time`)**: 분 단위 산수는 엔진이 독점하지만, 장면 전환·휴식·시간 비약 ("다음 날 아침이 밝았다") 처럼 절대 시각으로 점프해야 할 상황엔 narrator 가 `{type: "set_time", value: "<ISO>"}` state_change 를 발행할 수 있다 ([02-runtime.md](./02-runtime.md) §6.1). 같은 턴 안에서 엔진이 먼저 가산한 뒤 narrator 의 set_time 이 후행으로 덮어쓴다. 가드 3 종:

- 현재 `world_time` 보다 과거 ISO 는 `rejected[]` 로 reject (시간 역행 금지).
- `world_time` 외의 단일 필드는 set_time 으로 못 박는다 — 일반 `set` 경로와 분리된 전용 type.
- HP/MP 같은 엔진 전용 수치는 narrator 가 여전히 못 만진다. 즉 **시간만 점프하고 회복은 안 됨** — P1 의 "휴식한다" 는 §2.4 의 폴백을 그대로 따른다 (실제 회복은 P3 rest 엔드포인트).

**캘린더** 는 그레고리력 그대로. 월별 일수, 윤년, 23:59 → 다음 날 00:00 모두 ISO 8601 표준. 연도 라벨만 게임 세계 기준 ("812년") 이고, 별도 가상 캘린더는 도입하지 않는다.

**프론트 산출** (`mapping/to_front.py` 가 `world_time` 을 파싱):

- `Place.date` — "812년 4월 28일" 한국어 포맷.
- `Place.hour` — 0..23 정수.
- `Place.period` — `rules.time.period_thresholds` 로 hour 를 매핑한 라벨. 구간은 모두 반-개구간 `[start, end)` (경계 시각은 다음 period 에 속함 — 예: 07:00 은 "오전", 12:00 은 "오후"). 기본값:

  | period | hour `[start, end)` |
  |---|---|
  | 새벽 | 05–07 |
  | 오전 | 07–12 |
  | 오후 | 12–18 |
  | 저녁 | 18–21 |
  | 밤   | 21–05 |

  자정을 가로지르는 "밤" 은 `start > end` 표기 — mapping 이 이를 인지해 `hour ≥ 21 or hour < 5` 로 매칭 (동일한 반-개구간 규칙).

프론트는 가공 없이 그대로 표시.

### 2.2 호감도 (Affinity) [P1 최소, P3 완성]

호감도는 캐릭터의 `relations[target_id]` 에 저장된다. 범위는 **[-100, +100]**, 0 이 중립.

엔진이 두 단계로 갱신: ① `grade · intent` (· P3 에서는 `disposition` 까지) 으로 Δaffinity 산출 → ② [-100, +100] 으로 clamp 후 쓰기. **narrator 는 숫자를 정하지 않는다** — `{type: "affinity"}` state_change 로 호출만 트리거하고, 얼마가 변할지는 엔진이 결정 ([02-runtime.md](./02-runtime.md) §6).

- grade → delta:
  - success / partial_success → `rules.social.affinity_success`
  - failure → `rules.social.affinity_failure`
  - critical_success → `rules.social.affinity_critical`
  - critical_failure → `-rules.social.affinity_critical`
- intent 보정:
  - `hostile`: delta 부호 반전.
  - `deceptive`: critical_success / success / partial_success 시 0 (속임수 성공해도 호감도는 안 오름), failure / critical_failure 시 delta ×2 (들킨 거짓말은 두 배로 깎임).
- disposition 보정 [P3]:
  - lawful ≥ 70 + intent=deceptive + delta<0: ×1.5 (율법가는 거짓에 더 크게 실망)
  - aggressive ≥ 70 + intent=hostile + delta<0: ÷2 (공격적 성향은 도발을 덜 싫어함)
  - moral ≥ 70 + intent=friendly + delta>0: ×1.5

> **disposition** (lawful / aggressive / moral 등 NPC 성향 척도) 은 별도 0..100 스케일. affinity 만 [-100, +100].

### 2.3 성장 (Growth) [P3]

캐릭터 강화의 단일 통로는 `level_up`. 레벨이 곧 게이트고, 레벨업 한 번이 스탯·HP/MP·스킬 권한의 동시 갱신을 일으킨다. 별도의 train / learn 엔드포인트는 두지 않는다 — 모든 강화 경로를 `level_up` 으로 통합.

**현재 구현 상태**: 1·2·3 단계 (페어 트레이드 + HP/MP 재계산 + 게이트 해제) 는 `pipeline/growth.py` + `POST /session/{id}/level-up` endpoint 에 들어가 있다. 4 단계 (스킬 학습 후보 LLM 추천) 는 §2.6 스킬 시스템과 같은 작업.

- **레벨**: 0..20. 시작 0, 만렙 20 (레벨업 20 번 가능).
- **시작 스탯**: 모든 스탯 = 10. 스탯 범위 0..20.
- **xp 곡선** (선형): 레벨 N → N+1 비용 = `base_xp × N`. base_xp 의 절대값은 P3 게임 페이스 튜닝.

**`level_up(stat_up, stat_down)` endpoint** — xp 임계 도달 후 플레이어가 적당한 시점에 명시 호출 (자동 트리거 안 함). 한 호출에 묶여서 처리되는 4 단계:

1. **스탯 페어 트레이드** — `stat_up` +1, `stat_down` -1. 페어는 6각형 정반대편으로 고정:

   | up   | down |
   |---   |---   |
   | STR  | CHA  |
   | DEX  | WIS  |
   | CON  | INT  |

   양방향. `stat_down` 이 페어 외 스탯이거나, 이미 0 이거나, `stat_up` 이 이미 20 이면 reject. 페어가 0 에 닿으면 그 방향 leveling 자체가 차단된다 — 자연 천장. 한 페어를 풀몰빵해도 레벨업 10 회가 한계라, 그 뒤로는 다른 페어로 분산할 수밖에 없다 (빌드 다양성을 별도 anti-rule 없이 강제).

2. **HP/MP max 갱신** (스탯 연동, **매번 재계산**):

   - `max_HP = (10 + CON) + level × (5 + floor(CON / 4))`
   - `max_MP = (5 + INT) + level × (3 + floor(INT / 4))`

   현재 HP/MP 가 새 max 보다 크면 max 로 clamp. 스탯 변경 (페어 트레이드) 도 max 재계산을 트리거 — CON 을 깎으면 max_HP 도 즉시 같이 줄어든다. 빌드 변경의 무게를 즉시 반영.

   레벨 0 시작값 (모든 스탯 10): `max_HP = 20`, `max_MP = 15`.

3. **스킬 사용 게이트 해제** — 캐릭터 레벨이 오르면 `learned_skills` 안의 스킬 중 `skill.level ≤ character.level` 인 것이 사용 가능 상태로 전환 (§2.6).

4. **스킬 학습 후보 제시** — LLM 이 캐릭터 과거를 보고 후보 **3 개** 산출. 플레이어가 1 개 골라 `learned_skills[]` 에 추가하거나 거부 (다음 레벨업까지 보류). 별도 endpoint·자원 비용 없음. 입력 신호와 LLM/엔진 분담은 §2.6.

**NPC 도 같은 룰** — 모든 캐릭터가 **페어 트레이드 불변식**을 따른다: `STR+CHA = 20`, `DEX+WIS = 20`, `CON+INT = 20` (자연 귀결로 stat 합 = 60). 즉 NPC 의 강함은 stat 합이 아니라 **level → HP/MP + 스킬 조합 + 분포 편향** 으로 표현. boss 도 페어 합 20/20/20 을 유지하되 극단적 분포 (예: STR 20 / CHA 0, CON 19 / INT 1, DEX 4 / WIS 16) 로 압도감을 만든다. 시드 NPC 든 LLM 즉석 NPC (§2.4) 든 모두 이 룰.

P1 폴백 없음 — xp/레벨 시스템 자체가 P3 에서 도입.

### 2.4 회복 (Recovery) [P3]

**자연 회복 없음** — HP/MP 는 시간이 흘러도 자동으로 차지 않는다. 잠을 자야만 회복. 깎인 자원이 시간만으로 안 메워지니까 휴식 장소·타이밍 선택이 자원 사이클의 핵심이 된다.

**자연어 트리거** — 별도 endpoint 가 아니라 judge 가 자연어 입력을 `{action: "rest"}` 로 분류한다 ("잠을 잔다" / "야영한다" / "눈을 붙인다" 류). 짧은 휴식 ("한숨 돌린다") 은 여전히 `pass`. `/turn` 이 rest 분기로 빠지면 잠 시간 = `rules.time.sleep_hours` (기본 8) 만큼 `world_time` 진행 (§2.1). 인카운터 없으면 HP/MP 둘 다 max 로 **풀회복** — 부분 휴식이나 시간당 비례 회복 같은 중간 단계는 없다.

**장소별 위험도** — `Location.sleep_risk: Literal["safe", "risky", "dangerous"]`:

| risk      | 인카운터 확률 | 의미                                | 시드 부여 기준                                            |
|---        |---            |---                                  |---                                                        |
| safe      | 0%            | 여관·집·안전 캠프. 풀회복 보장.     | 마을·도시 내부, 여관·여인숙·집, 결계·요새 안, NPC 보호된 캠프 |
| risky     | 25%           | 야외, 한적한 길가. 가끔 습격.       | 도로·길가, 평원, 농지 외곽, 들판, 안전지대 사이 야영지        |
| dangerous | 60%           | 던전 안, 적지. 자다가 자주 습격.    | 던전·동굴 내부, 깊은 숲, 몬스터 영역, 적지·전장, 황무지       |

확률 수치는 `rules.recovery.encounter_chance` config 로 튜닝. 시드 작성 시 미설정이면 `safe` 가 기본 (안전 추정).

**인카운터 처리** — 잠 자기 직전 위험도 굴림 → 발생 시:

- 회복 0 (잠 못 잠).
- `surprise="enemy"` 로 전투 시작 (§1.2). 플레이어는 첫 라운드 행동 불가.
- 적 결정: `Location.sleep_encounters: list[character_id]` 풀이 우선. 풀이 비어있으면 narrator 가 LLM 즉석 생성.

**LLM 즉석 적 산출 분담** (풀이 비었을 때, §2.6 스킬 추천과 같은 패턴 — LLM 은 분류만, 엔진은 수치) **— 후속 단계, 현 구현은 풀 비어있으면 풀회복으로 fallback**:

- LLM 이 정함: `name`, `description`, `race` (또는 `appearance` 한 줄), `role`, `disposition`, `special_traits`. 장소 컨텍스트 (지형·시간·이전 사건) 를 보고 결정 — 숲 → 늑대, 동굴 → 박쥐, 도시 뒷골목 → 도적.
- 엔진이 정함: `id`; `level` (장소 위험도 매핑 — risky 는 플레이어 level ±2, dangerous 는 ±4 같은 식. 결과는 `max(0, ...)` 로 clamp — 시작 level=0 부근에서 음수 방지); HP/MP (§2.3 공식); stats (**페어 트레이드 불변식 — STR+CHA=20, DEX+WIS=20, CON+INT=20** 강제, 합 60 은 자동, 컨셉에 맞춰 분포 — 트롤 = STR 18 / CHA 2, DEX 6 / WIS 14, CON 16 / INT 4 같은 식); `combat_behavior` 디폴트.
- 새 character 는 `create` state_change 로 `state.characters` 에 등록 (§6.1 의 내부 전용 타입).

**전투 중 rest 거절** — combat_state 가 살아 있으면 "전투 중에는 잠들 수 없다" 한 줄로 거절. judge prompt 가 1차 차단, turn.py 가 2차 방어.

코드 위치 — `src/pipeline/recovery.py` 에 회복 룰, `pipeline/turn.py` 의 `_run_rest` 가 라우팅. (성장 §2.3 도입 시 `src/pipeline/growth/` 별도 분리 검토 — 회복은 자원 사이클, 성장은 영구 능력 변경.)

### 2.5 장비 / 인벤토리 / 거래 [P3]

**현재 구현 상태**: `pipeline/inventory.py` + `/equip` `/unequip` `/buy` `/sell` endpoint 까지 들어가 있다. 자연어 통합·프론트 UI 는 후속.

**장비 슬롯 (프론트 기준 8 종)**: `head / top / bottom / feet / leftHand / rightHand / acc1 / acc2`. `Equipment` 타입이 단일 소스이고, 각 슬롯은 `EquipItem | null`.

- `equip` / `unequip` 엔드포인트. 아이템의 `required` (Stats) 가 미충족이면 장착 거부.
- `Item.effects` 가 `WeaponEffect` 면 무기, `ArmorEffect` 면 방어구.
- **무기 슬롯**: `leftHand` / `rightHand` 어느 쪽이든 무기 장착 가능. 양손에 다 들면 두 손 모두 공격에 사용 (off-hand mod 페널티는 §1.1). 양손 무기 (two-handed) 는 한 아이템이 두 슬롯을 모두 차지.
- **weapon_dice 표준표** (D&D 5e PHB 기반, 시드 작성 가이드라인):

  | 분류                  | 예시                                | dice  |
  |---                    |---                                  |---    |
  | simple light          | 단검·곤봉·다트                       | 1d4   |
  | simple one-handed     | 메이스·창·핸드액스·라이트해머        | 1d6   |
  | simple two-handed     | 그레이트클럽·쿼터스태프              | 1d8   |
  | martial light         | 시미터·숏소드                        | 1d6   |
  | martial one-handed    | 롱소드·워해머·배틀액스·플레일        | 1d8   |
  | martial two-handed    | 그레이트소드·할버드·파이크           | 2d6   |
  | martial heavy         | 그레이트액스·모울                    | 1d12  |
  | 활                    | 숏보우 1d6 / 롱보우 1d8              | —     |

  마법·이종족 무기는 위 표 + 보정 (예: 마법 롱소드 = 1d8 + 1). 시드에 명시 안 된 무기는 컨셉에 가장 가까운 행으로 매핑.
- **방어도**: `head / top / bottom / feet` 4 슬롯의 ArmorEffect 합산.
- 실효 스탯 = 베이스 스탯 + 장비 수정자. `get_effective_stat()` 이 매번 합산해서 반환. 활성 버프는 스탯에 직접 영향 안 줌 — DC 판정 시 judge 컨텍스트로만 작용 (§2.6 `ActiveBuff`).

레거시 슬롯 (`head/left_hand/right_hand/chest/legs/necklace/ring_1/ring_2`) 은 폐기. 외부 계약 (프론트, API) 은 위 8 슬롯이 기준.

**인벤토리**: `inventory_ids: list[str]`. 들 수 있는 최대 무게 = `rules.carry.weight_per_strength` (기본 10.0) × STR. `buy` / `move_item` 시 `check_can_carry()` 가 검증.

**거래** (affinity 게이트는 `rules.social.*`, 가격 산식은 `rules.trade.*`):

- `buy`: `rules.social.trade_threshold` (기본 0 — affinity ≥ 0 이면 거래 가능) 통과 → 골드·무게 검증 → affinity 할인 적용 후 이전.
- `sell`: 가격 × `rules.trade.sell_ratio` (기본 0.5) × affinity 보너스.
- **흥정**: `rules.trade.affinity_price_per_point` (기본 0.01) × affinity 가 할인/보너스 비율 ([-100, +100] 스케일, 0 중립). 절대값은 `rules.trade.affinity_price_cap` (기본 0.5) 로 clamp — 즉 affinity 20 → 20% 할인, 50 → 50% 할인 (캡), 100 도 50% 할인 (캡 동일), -50 → 50% 가산. `affinity_price_per_point=0` 으로 끄면 고정 가격.

프론트 `Subject.inventory: InventoryItem{name, qty}[]` 는 내부 `inventory_ids` 를 같은 `item_id` 끼리 묶어 개수를 세서 만든다.

### 2.6 스킬 시스템 [P3]

**현재 구현 상태**: cast 핵심 (S1) 만 — `pipeline/skill.py` + `/cast` endpoint 로 level/MP/range 검증, target self/single/area, grade_multipliers 보정, ActiveBuff 추가/tick 동작. 의미 매칭 (judge 가 learned_skills 컨텍스트 받아 자동 발동), racial_skills 매칭 제외 룰, "맨손으로/스킬 없이" 회피 통로, LLM 학습 후보 3개 (§2.3 4단계) 는 후속.

`Skill(id, name, description, level, type, target, primary_stat, special_effect, power, mp_cost, range, duration)`.

**LLM/엔진 분담** (`level_up` 시 LLM 이 추천 후보 산출):

- LLM 이 정함: `name`, `description`, `type`, `target`, `primary_stat`, `special_effect` (자유 텍스트 묘사).
- 엔진이 정함: `id`, `level` (=캐릭터 현재 레벨), `mp_cost`, `power`, `range`, `duration` — type/level 기준 템플릿에서 산출.

**LLM 입력 신호** (`level_up` 추천 후보 산출 시 — P3 튜닝, 압축 전략):

- `character.memories` (§7) — 인상 깊은 일.
- 최근 N 턴 `turn_log` (§3.3) — 서사적 컨텍스트.
- 최근 N 턴 플레이어 입력 원문 — 가장 날것의 의도.

**필드 의미**:

- `level: int` (0..20) — 사용 요구 캐릭터 레벨. `racial_skills` 는 `level=0` (종족 기본, 시작부터 사용), `learned_skills` 는 `level≥1`. `cast` 시 `character.level ≥ skill.level` 검증 (§2.3 게이트 해제).
- `type`: attack / heal / buff / debuff.
- `target`: self / single / area.
- `primary_stat: Stat` — 그 스킬 `power` 가 기반하는 스탯.
- `special_effect: str` — LLM 이 자유 텍스트로 적은 묘사 ("불꽃을 휘감아 적의 갑옷을 녹임"). cast 시 judge 가 컨텍스트로 받아 **DC tier/grade 보정** (§2.2 호감도와 같은 패턴 — LLM 은 분류만, 엔진은 수치).

**보유 분류**:

- `racial_skills` (종족 기본 — 시드에 박힘, 보통 `level=0`) / `learned_skills` (LLM 추천으로 습득) 두 컬렉션으로 분리 저장. `all_skills()` 로 병합 조회.
- 일반 공격·점프 같은 보편 행동은 스킬 목록에 안 들어간다 — 엔진 기본 동사로 따로 처리.

**의미 매칭 발동** — cast 는 플레이어 입력에 스킬 이름이 정확히 안 박혀 있어도 일어날 수 있다. judge 가 캐릭터의 `learned_skills` 를 컨텍스트로 받아 입력의 의도와 의미적으로 부합하는 스킬을 매칭한다 (예: "조용히 다가가 등에 칼" → 「그림자 보행」). 단 `racial_skills` 는 **자동 매칭 대상이 아니다** — 종족 기본기는 이름을 명시적으로 호출했을 때만 발동. racial 은 학습 궤적이 아니라 종족 고정 기능이라, 의미 매칭에 끼우면 과한 자동 발동이 일어나니 의도적으로 분리.

- **회피**: "맨손으로" / "스킬 없이" / "그냥 평타" 같은 표현이 보이면 매칭 시도 안 함 — 플레이어가 의도적으로 스킬을 끄는 통로.
- **알림 필수**: 매칭 발동 시 본문이나 `log_entry` 에 "「스킬명」 발동" 표시. 자동 매칭이 일어났을 때 투명성을 보장하는 장치.
- 게이트 (레벨) 나 MP 검증 실패면 매칭은 그냥 무시 — 평타로 진행하는 사일런트 폴백.

`cast` 파이프라인: 레벨 게이트 검증 → MP 검증 → 사정거리 검증 → AoE 대상 자동 계산 → judge 가 `special_effect` 컨텍스트로 tier/grade 보정 → 데미지/회복/버프 적용 → 퀘스트 트리거.

`ActiveBuff(description: str, duration: int)` — type=buff/debuff 인 스킬 cast 또는 §2.7 아이템 use 로 생성. `Character.active_buffs: list[ActiveBuff]` 에 append 로 저장. **스탯에 직접 영향 안 줌** — DC 판정 시 judge 가 `description` 을 컨텍스트로 받아 tier/grade 보정 (§2.2 호감도와 같은 패턴, special_effect 와 동일 경로). `duration` 은 매 턴 종료 시 -1, 0 이 되면 리스트에서 제거.

P1 프론트 `Hero.skills: string[]` 는 UI 태그만 노출. 효과 계산 자체는 P3.

### 2.7 사용 / 소비 (Use) [P3]

**현재 구현 상태**: `pipeline/inventory.use` + `/use` endpoint. heal/damage/mp_restore/buff 분기, on_use 트리거 패스스루 (quest trigger 평가는 §2.8), consumable=True 시 인벤 차감.

`use` 엔드포인트 (`actor`, `item`, 선택 `target`):

- `Item.effects` 의 세 번째 분류 — §2.5 의 WeaponEffect / ArmorEffect 와 나란히 `ConsumableEffect` 가 존재하며 `use` 가 이 분기를 처리한다.
- `ConsumableEffect` 에 따라 효과 적용:
  - `heal`: HP 회복
  - `damage`: HP 감소 (투척물·폭탄 같은 적대적 사용)
  - `mp_restore`: MP 회복
  - `buff`: §2.6 의 `ActiveBuff` 를 `target` 에 부여. description + duration (예: 힘 물약 → "근력 일시 강화, 무거운 물건 다루기 쉬워짐" / 5 턴 — STR DC 판정 시 judge 가 보정).
- `Item.on_use` 트리거 실행 (예: 열쇠, 퀘스트 아이템) — `Item.effects` 와 별개의 선택 필드, 자유 텍스트 또는 trigger id. ConsumableEffect 의 정형 효과로 표현 안 되는 1 회성 동작 전용.
- 아이템이 `consumable` 이면 사용 후 인벤토리에서 제거.

### 2.8 진행 (Progression) [P3]

**현재 구현 상태**: `pipeline/quest.py` + apply_move/inventory.use_with_quest_hook/combat.apply_attack_to_defender 의 hook 까지 들어가 있다. 이벤트 매칭 (character_death / location_enter / item_use), single-fire, fail_triggers, prereq 잠금 해제, 보상 자동 적용 (gold/exp/items → player), chapter.progress 갱신과 active → completed 전환 모두 동작. P1 의 narrator set status/summary 경로는 그대로 유지 — 자동 트리거와 병행.

**구조**: `Campaign` → `Chapter` → `Quest` 3-tier.

```python
Chapter(
    title: str,
    summary: str,                     # 동적 진행 요약. 시드 초기값 → narrator 가 매 턴 set 으로 갱신 ([02-runtime.md](./02-runtime.md) §3.2)
    quest_ids: list[str],
    status: Literal["locked", "active", "completed"],
    required: bool,                   # chapter.progress 카운트 대상 여부
    # 런타임 파생 필드 (시드 JSON 에 박지 않음, 엔진이 매 턴 계산)
    progress: {done: int, total: int} = {done: 0, total: 0},  # required=true 퀘스트 중 completed 수 / 전체 수. 프론트 표시·엔진 트리거 평가용 ([02-runtime.md](./02-runtime.md) §3.2 - 세션 레이어엔 안 실음)
)

Quest(
    title: str,
    summary: str,                     # 동적 진행 요약. 시드 초기값 → narrator 가 매 턴 set 으로 갱신 ([02-runtime.md](./02-runtime.md) §3.2)
    giver_id: str,
    difficulty: Tier,                 # 7단계 한글 라벨 ([02-runtime.md](./02-runtime.md) §4.3)
    prerequisite_ids: list[str],
    triggers: list[QuestTrigger],     # 자동 성공 트리거. 프론트 goals[] 산출 베이스
    conditions: list[str],            # 자유 텍스트 제약 ("기한 없음", "민간인 피해 최소화" 등). 프론트 conditions[] 로 그대로 노출
    fail_triggers: list[QuestTrigger],
    rewards: QuestRewards,
    status: Literal["locked", "active", "completed", "failed"],
    required: bool,
    # 런타임 필드 (시드 JSON 에 박지 않음, 엔진이 갱신)
    triggers_met: list[bool] = [],         # triggers 와 같은 길이. apply_changes 후 check_quests 가 토글
    fail_triggers_met: list[bool] = [],    # fail_triggers 와 같은 길이
)

QuestTrigger(
    id: str,                 # 식별자 ("scout_killed" 등)
    name: str,               # 프론트 goals[] 에 노출되는 한글명 ("정찰병 처치")
    type: str,               # location_enter | character_death | item_use | …
    target_id: str,
)

QuestRewards(
    gold: int,
    exp: int,
    items: list[str] = [],   # [P3]. P1 프론트엔 미노출
)
```

- **단일 충족 모델** — `triggers_met` 은 트리거별로 한 번만 토글된다. 즉 "고블린 5 마리 처치" 같은 누적 조건은 미지원. 그런 의존이 필요하면 quest 를 5 개로 쪼개고 `required_by` 엣지로 묶는 식.
- `status`: `locked → active → completed | failed`.
- `apply_changes` 이후 `check_quests()` 가 관련 트리거로 재평가. quest 가 완료/실패되면 `maybe_check_chapters()` 가 상위 챕터의 전환 가능성을 본다.
- **보상 자동 적용** — `quest.status` 가 `"completed"` 로 바뀌는 시점에 엔진이 `rewards.gold` → `actor.gold`, `rewards.exp` → `actor.xp_pool`, `rewards.items` → `actor.inventory_ids` 를 가산. 여기서 `actor` = **퀘스트를 수령한 플레이어 캐릭터** (P1·P2 단일 플레이어 전제). 동반자나 NPC 는 보상 대상이 아니다. narrator 는 서술에서 "보상을 받았다" 정도만 흘리면 충분 — 구체 수치를 본문에 명시할 필요 없음. `QuestRewards.exp` 는 `actor.xp_pool` 에 적립되는 같은 자원 — §2.3 의 "xp" 표기와 동일물이다 (시드는 reward 측에서 `exp`, 캐릭터 자원 필드명은 `xp_pool`).
- 프론트 노출 ([04-boundary.md](./04-boundary.md) §1): `goals[]` 는 `triggers.map(t => t.name)`, `conditions[]` 는 자유 텍스트 그대로, `difficulty` 는 `{value: 1..7, max: 7, label}` 로 변환, `rewards` 는 `{gold, exp}` 만.

`chapter.progress` 의 `done` / `total` 은 챕터의 quest 중 **`required=true` 인 것만** 카운트한다 (선택 퀘스트는 분모·분자 모두에서 제외). 프론트 표시와 엔진 트리거 평가에서만 사용 — 세션 레이어 ([02-runtime.md](./02-runtime.md) §3.2) 에는 싣지 않는다 (narrator 는 `summary` + `goals` 로 진행을 본다).

P1 은 narrator 가 `{type: "set", entity: "quests|chapters", id, field: "status"|"summary", value: ...}` 로 간접 반영 — 진행 요약 (`summary`) 갱신과 상태 (`status`) 전환만 가능. 자동 트리거는 P3.

### 2.9 동반자 (Companions, pocket-monster 방식) [P3]

`Character.companions: list[str]` — patron (이 동반자를 거느린 캐릭터) 이 "주머니에 넣고 다니는" 부하 캐릭터 ID 목록.

- **위치 동기화**: 동반자의 위치는 patron 의 `location_id` 를 따른다 (`effective_location()` 이 반환). 동반자 본인의 `location_id` 필드는 사용하지 않는다 — 둘이 어긋날 일이 없게 위치를 한 군데서만 본다.
- **전투 참여**: `start_combat(participants)` 가 각 participant 의 `companions` 를 자동 확장해 turn_order 에 포함 (중복 제거). 동반자는 자기 DEX 로 이니셔티브를 굴림.
- **피아 식별**: 같은 patron 을 공유하면 아군. NPC AI 는 patron 관점의 affinity 로 적을 찾으므로, 동반자는 자동으로 patron 의 적을 공격하게 된다 (별도 표식 없이 affinity 만으로 처리).
- **비전투 노출**: `target_view` / `surroundings` 의 NPC 목록에 patron 과 함께 등장 (별도 UI 슬롯 아님).

**제약**: 동반자 본인에게는 AI 가 없다. 1 인칭 대사·반응은 narrator 서술로만 표현. P3 이후 `companion_voice_hint` 같은 힌트 필드를 검토할 수 있음.

P1 프론트 `Hero.companions: list[str]` 는 백엔드가 각 char_id 를 `"이름 (종족 직업)"` 문자열로 조립해 만든 배열. 프론트는 그대로 표시. 내부 동반자 로직 (위치 동기화·전투 참여·피아 식별) 은 P3.
