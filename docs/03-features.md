# 기능 확장 (§1-§2)

> 기본 런타임 ([02-runtime.md](./02-runtime.md) §1-§7) 위에 얹히는 시스템들. 전투, 시간, 호감도, 성장, 회복, 장비/거래, 기술, 사용, 진행, 동반자.
> 이 모든 룰의 *왜* 는 [01-overview.md](./01-overview.md) §3.17 — 룰은 인터랙티브 노블의 *현실감 발판* (narrator 가 거짓말 못 하게 잡는 physics) 이지 게임플레이 콘텐츠가 아니라는 메타-thesis 가 깔려 있다.
> 인덱스는 [01-overview.md](./01-overview.md). 런타임 메커닉은 [02-runtime.md](./02-runtime.md), 프론트 경계는 [04-boundary.md](./04-boundary.md), 백엔드 코드 지도는 [05-codemap.md](./05-codemap.md).

이 문서는 두 묶음을 다룬다. **§1 전투** 는 P2 부터 켜진다. **§2 확장 시스템** 은 9 개로 — 이 중 월드 시간과 호감도는 P1 부터 최소 형태로 들어가고 (호감도는 P3 에서 완성), 나머지 7 개는 P3 에서 추가. Phase 별 범위는 [01-overview.md](./01-overview.md) §2 참고.

---

## 1. 전투 [P2]

> 전투는 **자동 시뮬 한 사이클**로 진행된다. 플레이어가 `{action: "combat"}` (또는 `summon_combat` / `flee` / `pass`) 으로 들어오면 엔진이 `combat_state` 를 띄우고 그 자리에서 결판이 날 때까지 라운드를 자동으로 돌린다 — 양쪽 모두 자동, 플레이어는 첫 입력의 행동 (skill 또는 평타) 을 매 라운드 반복하고 NPC 는 `combat_behavior` AI 가 결정. 사이클이 끝나면 `combat_narrate` 에이전트가 events 전체를 받아 3–5 문장 시네마틱으로 풀어 쓴다. 플레이어가 매 라운드마다 끊고 입력하는 manual round 모드는 없고, 사이클이 도중에 멈추는 일도 없다 — 무조건 terminal outcome (victory / defeat / fled / downed) 까지 간다.
>
> 사이클 도중 플레이어가 0 HP 가 되면 `engines/combat.tick_death_save` 가 같은 sim 안에서 stable / dead 까지 자동 굴려 결판낸다 — dice 버튼은 더 이상 등장하지 않는다. `combat_auto.HARD_CAP` (기본 50) 은 코드 안전장치 — 양쪽이 결판을 못 내는 stalemate 가 길게 이어지면 `fled` 로 강제 종료해 상태 머신이 깔끔히 닫히게 한다. 실제 전투에서 발동할 일은 거의 없음.
>
> 라운드 루프를 돌리되 한 입력 = 한 사이클로 묶고 cinematic 을 모아 출력하는 게 핵심 — 무기 dice·스탯·기술·적 AI 같은 룰의 깊이를 살리면서도 플레이어가 매 라운드 끊기지 않는 페이스를 만든다. 자세한 결정 이유는 [01-overview.md](./01-overview.md) §3.15, 룰을 두는 메타-thesis 는 §3.17.

### 1.1 자동 사이클 — 라운드 시뮬

`flow/combat_auto.run_auto_combat` 가 양쪽 라운드를 모두 돌린다.

- **이니셔티브**: `roll_initiative` 로 d20 + DEX_mod 를 굴려 `turn_order` 결정. 매 라운드 같은 순서로 진행.
- **공격 굴림**: 라운드별 actor 마다 `engines/combat.attack` 이 d20 + stat_modifier vs `enemy_defense` 로 명중·등급 결정. weapon dice + stat_mod 로 데미지. 어떤 스탯을 쓸지는 무기로 갈림 — 사거리 1.5m 이하 근접 무기는 STR, 그보다 멀면 DEX. 무기 없는 맨손은 `UNARMED_DAMAGE="1d4"`, `UNARMED_RANGE=1.5` 폴백.
- **방어도**: `enemy_defense = 10 + Σ(armor_effect.defense for slot in 방어 슬롯)`. 합산 슬롯은 `armor` + `accessory` (방패·방어 링) — `ArmorEffect` 가 든 두 슬롯 모두 더해진다 (§2.5).
- **range 단위는 미터 (실수)**. 같은 location 안의 추상적 거리. 다른 location 의 적은 사거리 밖이라 combat 액션 자체가 막힘. 같은 단위가 §2.6 기술 cast 의 사정거리 검증에도 쓰임.
- **플레이어 행동 반복**: 첫 입력의 행동 (`PlayerAction.kind ∈ {attack, skill, pass, flee}`) 을 매 라운드 반복. skill cast 는 매 라운드 MP/level 검증을 통과하면 그 skill 로, 부족하면 평타로 폴백. `pass` / `flee` 는 라운드 1 만 적용되고 라운드 2+ 는 평타로 폴백. `use` / `equip` / `unequip` 같은 passive 액션은 라운드 1 에 한 번 실행되고 라운드 2+ 는 평타로 진행 (사이클 자체는 결판까지 감).
- **NPC AI**: `pick_npc_target` 가 `combat_behavior.attack_priority` (`nearest` / `lowest_hp` / `highest_threat` / `healer_first` / `random`) 와 가중치 모드 (`nearest_weight`, `random_weight`) 로 타겟 선택. `highest_threat` 의 위협 지표는 `combat_state.damage_dealt` 누적값. NPC 도 `should_attempt_flee` / `try_flee` 로 자체 도주 가능.
- **종료 조건**: `check_combat_end` 가 매 actor 행동 후 victory (적 전원 처치/도주) / defeat (플레이어 사망) 검사. 모든 사이클은 terminal outcome 까지 간다 — 도중에 멈추지 않는다.

### 1.2 outcome 결정

자동 사이클의 마지막 outcome 은 4 종:

| outcome | 의미 |
|---|---|
| `victory` | 적 전원 무력화 또는 도주. |
| `defeat` | 플레이어 사망 (death_save dead 포함). |
| `fled` | 플레이어 `flee` 시도 성공 (또는 HARD_CAP 안전장치 발동). |
| `downed` | 플레이어 0 HP → death_save 자동 굴림 → stable. HP=1 로 회복 후 사이클 종료. |

모든 outcome 은 `combat_state` 를 정리하고 SSE `combat_end` 를 발사한다.

**outcome breakdown (수치 후행)**: 시네마틱 본문 뒤로 엔진이 한 덩이의 act 로그 (`combat_auto.format_outcome_summary`) 를 따로 발행한다 — 적별 누적 데미지·잔여 HP·처치 여부, 플레이어가 받은 누적 피해. narrator 가 본문에서 수치를 노출하지 못하는 서술 규율을 보완하는 정직한 후행 정산. 프론트는 `act` 톤 메시지로 그대로 받아 본문 아래에 붙인다.

### 1.3 전투 상태 (`combat_state`)

전투가 시작되면 엔진이 메모리에 띄우고 사이클 끝에 항상 정리한다. 다음 `/turn` 에는 항상 평시 상태에서 시작한다.

```python
class CombatState:
    turn_order: list[str]                 # 이니셔티브 순서 (d20 + DEX_mod)
    current_turn: int = 0
    round: int = 1                        # 사이클 안에서만 의미
    surprise: Literal["player", "enemy"] | None = None
    enemy_ids: list[str]
    damage_dealt: dict[str, int]          # actor_id → 누적 데미지 (highest_threat AI 용)
```

### 1.4 플레이어 사망 / Death Save

`rules.combat.death` 가 사망 처리 룰을 모은다.

- `instant_death: bool = False` — True 면 HP 가 0 이 되는 순간 즉시 사망. NPC·몬스터는 보통 이게 True, 플레이어는 `revive_coins` 가 먼저 동작.
- `revive_coins: int = 0` — 플레이어 전용 목숨 토큰. 0 보다 크면 HP 가 0 이 돼도 토큰 1 개를 깎고 `max_hp * revive_ratio` (기본 0.5) 만큼 회복하며 즉시 부활. 토큰을 다 쓴 다음에야 dying / dead 단계로 넘어간다.
- 토큰이 없고 `instant_death=False` 면 자동 사이클 안에서 `tick_death_save` 가 stable / dead 까지 d20 을 자동 굴린다 — `≥ save_dc` (기본 10) 면 성공, 미만이면 실패. 성공 3 회 → 안정화 (HP=1, outcome=downed). 실패 3 회 → 사망 (outcome=defeat). 도중에 새 데미지가 들어오면 실패 카운트 +1, critical_failure 면 +2.
- D&D 5e 의 **nat-20 자동 1HP 회복** 은 도입하지 않는다. 부활 통로는 `revive_coins` 토큰으로 일원화.
- dice 버튼은 더 이상 death save 용으로도 등장하지 않는다 — 모두 sim 안에서 자동 처리.

### 1.5 ambush (수면 중 기습)

수면 중 인카운터 (§2.4) 는 자동 모드의 유일한 예외 — `surprise=enemy` 로 `combat_state` 를 띄우고 `cap=1` 로 1 라운드만 돈다 (player surprise pass, NPC 만 행동). 그 후 `combat_state` 는 보존된 채 플레이어가 깨어나서 다음 입력으로 사이클을 이어 받는다. 일반 전투는 항상 결판까지 가지만, ambush 는 player 가 의식 없이 깨어나기 직전이라 입력 기회를 한 번 주기 위한 의도된 단절.

### 1.6 SSE 신호

`combat_*` 3 종은 [02-runtime.md](./02-runtime.md) §2.4 표에 통합:

- `combat_start`: 전투 진입 알림. `{turn_order, round, surprise, enemy_ids}` — UI 에 "전투 시작" 배지를 띄울 신호.
- `combat_turn`: 자동 사이클 안에서 한 actor 의 한 행동 상세. `{actor, action ∈ {attack|skill|miss|pass|flee|use|equip|unequip}, grade?, damage?, killed?, target?, skill_name?, skill_id?, round?}`. UI 는 보통 무시 — 정확한 상태는 `state` 와 `log_entry` 에 실린다. 테스트가 관찰 가능 신호로 사용.
- `combat_end`: §1.2 의 4 종 outcome 모두 발사. 사이클은 항상 terminal 로 끝난다.

---

## 2. 확장 시스템

확장 시스템 9 종은 `rules/config.py` 에서 모든 수치를 튜닝한다 ([05-codemap.md](./05-codemap.md) §1). 4 묶음으로 묶여 있다:

1. **기반** — 시간, 호감도. 다른 시스템들이 참조하는 척도.
2. **캐릭터 자원** — 성장 (영구 스탯·레벨), 회복 (HP/MP 사이클).
3. **장착·행동** — 장비/거래, 기술, 사용 (소비 아이템).
4. **메타** — 진행 (퀘스트), 동반자.

### 2.1 월드 시간 (World Time)

분/시 단위 시계는 없다. 게임 세계의 시간 변수는 `state.turn_count` 단 하나이고, `domain/clock.py:day_phase` 가 거기서 `새벽 / 오전 / 오후 / 밤` 4 phase 를 파생한다.

**구조** — phase 당 `RULES.time.phase_turns` (기본 10) 턴 × 4 phase = **40 턴이 1 일 사이클**.

  | turn_count % 40 | day_phase |
  |---|---|
  | 0–9 | 새벽 |
  | 10–19 | 오전 |
  | 20–29 | 오후 |
  | 30–39 | 밤 |

게임 시작 직후 (turn 0) 는 항상 "새벽" 이다.

**시간이 흐르는 경로** — `state.turn_count` 를 늘리는 곳:

- 매 턴 종료 시 `flow/turn.py / roll.py / combat_phase.py / rest.py` 가 `turn_count += 1`. 일반 액션은 1 턴 = 1 phase-tick. 자동 전투 사이클도 한 입력 = 1 phase-tick (사이클 안에서 라운드를 N번 돌아도 phase 는 1 만 흐름).
- 수면(§2.4) 만 점프형: `engines/recovery.py` 의 full recovery 가 `state.turn_count = next_dawn_turn(state.turn_count)` 로 다음 새벽 boundary 까지 한 번에 이동.

**narrator 와의 경계**: state_change 에 `set_time` 같은 타입은 없다. narrator 는 시간을 직접 만지지 못하고, 분위기 묘사 (`session.day_phase`) 만 입력으로 받는다. 시간 비약 ("다음 날 아침") 은 휴식(`rest`) 액션을 통해서만 실제로 발생한다.

**프론트 산출** (`mapping/to_front.py`):

- `Place.dayPhase` — 현재 `day_phase` 한국어 라벨 그대로. 분/시는 클라이언트로 보내지 않는다.

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

캐릭터 강화의 단일 통로는 `level_up`. 레벨이 곧 게이트고, 레벨업 한 번이 스탯·HP/MP·기술 권한의 동시 갱신을 일으킨다. 별도의 train / learn 엔드포인트는 두지 않는다 — 모든 강화 경로를 `level_up` 으로 통합.

**현재 구현 상태**: 1·2·3·4 단계 모두 들어가 있고, 자연어로 한 통로에 모임 — judge 가 입력을 보고 `level_up { stat_up, stat_down }` / `learn_skill { index }` 액션으로 분류하면 `flow/turn.py` 의 액션 분기에서 처리. 옛 `POST /level-up` / `POST /learn-skill` REST 엔드포인트는 폐기.
- 1·2·3 단계: `engines/growth.py` 가 페어 트레이드 + HP/MP 재계산 + 게이트 해제 (cast 시점 검증으로 자연 해제) 를 담당.
- 4 단계: `agents/skill_recommend/` + `flow/skill_recommend.py` — level_up 직후 LLM 호출해 후보 3 개 산출. LLM 이 name/description/type/target/primary_stat/special_effect 정하고 엔진이 id/level/template 수치 (mp_cost/power/range/duration) 를 채움. 후보는 `state.pending_skill_candidates` 에 저장. 다음 턴에 플레이어가 자연어로 "첫 번째 기술을 배운다" 같이 적으면 judge 가 `learn_skill { index }` 로 분류해 1 개 선택 또는 거부 (다음 레벨업까지 보류). LLM 호출 실패는 silent fallback (빈 후보).

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

3. **기술 사용 게이트 해제** — 캐릭터 레벨이 오르면 `learned_skill_ids` 안의 기술 중 `skill.level ≤ character.level` 인 것이 사용 가능 상태로 전환 (§2.6).

4. **기술 학습 후보 제시** — LLM 이 캐릭터 과거를 보고 후보 **3 개** 산출. 플레이어가 1 개 골라 `learned_skill_ids[]` 에 추가하거나 거부 (다음 레벨업까지 보류). 별도 endpoint·자원 비용 없음. 입력 신호와 LLM/엔진 분담은 §2.6.

**NPC 도 같은 룰** — 모든 캐릭터가 **페어 트레이드 불변식**을 따른다: `STR+CHA = 20`, `DEX+WIS = 20`, `CON+INT = 20` (자연 귀결로 stat 합 = 60). 즉 NPC 의 강함은 stat 합이 아니라 **level → HP/MP + 기술 조합 + 분포 편향** 으로 표현. boss 도 페어 합 20/20/20 을 유지하되 극단적 분포 (예: STR 20 / CHA 0, CON 19 / INT 1, DEX 4 / WIS 16) 로 압도감을 만든다. 시드 NPC 든 LLM 즉석 NPC (§2.4) 든 모두 이 룰.

P1 폴백 없음 — xp/레벨 시스템 자체가 P3 에서 도입.

### 2.4 회복 (Recovery) [P3]

**자연 회복 없음** — HP/MP 는 시간이 흘러도 자동으로 차지 않는다. 잠을 자야만 회복. 깎인 자원이 시간만으로 안 메워지니까 휴식 장소·타이밍 선택이 자원 사이클의 핵심이 된다.

**자연어 트리거** — 별도 endpoint 가 아니라 judge 가 자연어 입력을 `{action: "rest"}` 로 분류한다 ("잠을 잔다" / "야영한다" / "눈을 붙인다" 류). 짧은 휴식 ("한숨 돌린다") 은 여전히 `pass`. `/turn` 이 rest 분기로 빠지면 `state.turn_count` 가 다음 새벽 boundary 로 점프 (§2.1). 인카운터 없으면 HP/MP 둘 다 max 로 **풀회복** — 부분 휴식이나 시간당 비례 회복 같은 중간 단계는 없다.

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

**LLM 즉석 적 산출 분담** (풀이 비었을 때, §2.6 기술 추천과 같은 패턴 — LLM 은 분류만, 엔진은 수치) — `flow/encounter.py:summon_encounter` + `agents/encounter_summon` 으로 구현됨. `flow/rest.py` 가 `summon_cb` 로 wire-in 하고, encounter_summon agent 가 페어 트레이드 invariant 까지 schema validator 로 강제:

- LLM 이 정함: `name`, `description`, `race` (또는 `appearance` 한 줄), `role`, `disposition`, `special_traits`. 장소 컨텍스트 (지형·시간·이전 사건) 를 보고 결정 — 숲 → 늑대, 동굴 → 거미, 도시 뒷골목 → 도적.
- 엔진이 정함: `id`; `level` (장소 위험도 매핑 — risky 는 플레이어 level ±2, dangerous 는 ±4 같은 식. 결과는 `max(0, ...)` 로 clamp — 시작 level=0 부근에서 음수 방지); HP/MP (§2.3 공식); stats (**페어 트레이드 불변식 — STR+CHA=20, DEX+WIS=20, CON+INT=20** 강제, 합 60 은 자동, 컨셉에 맞춰 분포 — 트롤 = STR 18 / CHA 2, DEX 6 / WIS 14, CON 16 / INT 4 같은 식); `combat_behavior` 디폴트.
- 새 character 는 `create` state_change 로 `state.characters` 에 등록 (§6.1 의 내부 전용 타입).

**전투 중 rest 거절** — combat_state 가 살아 있으면 "전투 중에는 잠들 수 없다" 한 줄로 거절. judge prompt 가 1차 차단, turn.py 가 2차 방어.

코드 위치 — `engines/recovery.py` 에 회복 룰, `flow/rest.py:run_rest` 가 라우팅 (turn.py 의 `RestAction` 분기에서 호출). 회복은 자원 사이클, 성장은 영구 능력 변경 — 두 시스템은 별도 모듈로 분리.

### 2.5 장비 / 인벤토리 / 거래 [P3]

**현재 구현 상태**: `engines/inventory/` (carry/equipment/trade/use 분리) + 자연어 통합. judge 가 `surroundings.inventory` (`kind: weapon|armor|...`) 와 `surroundings.equipment` (3 슬롯 → {id, name}) 보고 `EquipAction` / `UnequipAction` / `BuyAction` / `SellAction` 을 발행하면 `flow/turn.py` 의 액션 분기가 그 자리에서 엔진을 호출. 옛 `/equip` `/unequip` `/buy` `/sell` REST 엔드포인트는 폐기 — 모든 장비·거래는 자연어로 들어온다 ("철검을 든다", "여관 주인에게 사과 5개 사겠다"). 엔진이 slot 자동 결정 (무기=weapon, ArmorEffect 는 armor 우선·차오르면 accessory, 장식품=accessory).

**장비 슬롯 (3 종)**: `weapon / armor / accessory`. `Equipment` 타입이 단일 소스이고, 각 슬롯은 `EquipItem | null`.

- judge 의 `equip` / `unequip` 액션이 그 자리에서 처리. 아이템의 `required` (Stats) 가 미충족이면 `InventoryInvalid` → `format.py` 가 한국어 한 줄로 변환해 GM log 로 흘림 (HTTP 422 안 일어남).
- `Item.effects` 가 `WeaponEffect` 면 무기, `ArmorEffect` 면 방어 효과 물건 (갑옷·방패·정수 +1 같은 링).
- **무기 슬롯**: `weapon` 한 자리. 한 캐릭터당 무기는 한 자루 — 양손/이도류 구분은 다루지 않는다.
- **악세사리 슬롯**: `accessory` 한 자리. ArmorEffect 도 들어올 수 있어서 방패는 갑옷 위에 추가로 장착 가능 — 전투 산식은 armor + accessory 의 `defense` 를 모두 합산한다.
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
- **방어도**: `armor` + `accessory` 두 슬롯의 `ArmorEffect.defense` 합산 (§1.1 의 `enemy_defense` 와 같은 식).
- **스탯 단일 출처**: 엔진은 `Character.stats` 를 직접 읽는다 — 장비는 weapon dice 와 armor defense 만 더하지 스탯 자체에 보정을 걸지 않는다. 활성 버프도 스탯에 직접 영향 안 줌 — DC 판정 시 judge 가 `description` 을 컨텍스트로 받아 tier/grade 만 보정 (§2.6 `ActiveBuff`).

레거시 슬롯 (`head/left_hand/right_hand/chest/legs/necklace/ring_1/ring_2`) 은 폐기. 외부 계약 (프론트, API) 은 위 3 슬롯이 기준.

**인벤토리**: `inventory_ids: list[str]`. 들 수 있는 최대 무게 = `rules.carry.weight_per_strength` (기본 10.0) × STR. `buy` / `move_item` 시 `check_can_carry()` 가 검증.

**거래** (affinity 게이트는 `rules.social.*`, 가격 산식은 `rules.trade.*`):

- `buy`: `rules.social.trade_threshold` (기본 0 — affinity ≥ 0 이면 거래 가능) 통과 → 금화·무게 검증 → affinity 할인 적용 후 이전.
- `sell`: 가격 × `rules.trade.sell_ratio` (기본 0.5) × affinity 보너스.
- **흥정**: `rules.trade.affinity_price_per_point` (기본 0.01) × affinity 가 할인/보너스 비율 ([-100, +100] 스케일, 0 중립). 절대값은 `rules.trade.affinity_price_cap` (기본 0.5) 로 clamp — 즉 affinity 20 → 20% 할인, 50 → 50% 할인 (캡), 100 도 50% 할인 (캡 동일), -50 → 50% 가산. `affinity_price_per_point=0` 으로 끄면 고정 가격.

프론트 `Subject.inventory: InventoryItem{name, qty}[]` 는 내부 `inventory_ids` 를 같은 `item_id` 끼리 묶어 개수를 세서 만든다.

### 2.6 기술 시스템 [P3]

**현재 구현 상태**: cast 핵심 (S1) + judge 의미 매칭 (S2) + 학습 후보 (§2.3 4단계 / S3) 까지 들어갔고 자연어 통합. judge 가 `combat` 액션의 `skill_id` 필드 (또는 의미 매칭, S2) 로 어느 기술을 쓸지 결정하고, `flow/combat_auto.py` 의 자동 사이클 안에서 `engines/skill.py:cast` 가 매 라운드 호출된다 (MP/level 부족 시 평타 폴백). 옛 `POST /cast` REST 엔드포인트는 폐기.
- S1: `engines/skill.py` 가 level/MP/range 검증, target self/single/area, grade_multipliers 보정, ActiveBuff 추가/tick 을 담당. attack/debuff 만 d20 굴림으로 grade 결정 (`compute_cast_grade`); heal/buff/self 는 자동 success.
- S2: judge prompt 가 `surroundings.skills` (racial + learned 두 컬렉션을 합친 뒤 level/MP 통과한 것만 노출, `source: "racial"|"learned"` 로 구분) 와 회피 통로 ("맨손으로/기술 없이/그냥 평타") 를 보고 `CombatAction.skill_id` 를 채운다. turn.py 가 combat 분기에서 skill_id 가 있으면 plain attack 대신 cast 로 진행하고 GM 로그에 `「기술명」 발동` 알림. racial·learned 모두 자동 매칭 대상.
- S3: `agents/skill_recommend/` + `flow/skill_recommend.py` — level_up 직후 LLM 호출해 캐릭터 컨텍스트(memories/turn_log/recent_inputs) 보고 후보 3개 산출. §2.3 4단계와 같은 코드.

`Skill(id, name, description, level, type, target, primary_stat, special_effect, power, mp_cost, range, duration)`.

**LLM/엔진 분담** (`level_up` 시 LLM 이 추천 후보 산출):

- LLM 이 정함: `name`, `description`, `type`, `target`, `primary_stat`, `special_effect` (자유 텍스트 묘사).
- 엔진이 정함: `id`, `level` (=캐릭터 현재 레벨), `mp_cost`, `power`, `range`, `duration` — type/level 기준 템플릿에서 산출.

**LLM 입력 신호** (`level_up` 추천 후보 산출 시 — P3 튜닝, 압축 전략):

- `character.memories` (§7) — 인상 깊은 일.
- 최근 N 턴 `turn_log` (§3.3) — 서사적 컨텍스트.
- 최근 N 턴 플레이어 입력 원문 — 가장 날것의 의도.

**필드 의미**:

- `level: int` (0..20) — 사용 요구 캐릭터 레벨. `racial_skill_ids` 는 `level=0` (종족 기본, 시작부터 사용), `learned_skill_ids` 는 `level≥1`. `cast` 시 `character.level ≥ skill.level` 검증 (§2.3 게이트 해제).
- `type`: attack / heal / buff / debuff.
- `target`: self / single / area.
- `primary_stat: Stat` — 그 기술 `power` 가 기반하는 스탯.
- `special_effect: str` — LLM 이 자유 텍스트로 적은 묘사 ("불꽃을 휘감아 적의 갑옷을 녹임"). cast 시 judge 가 컨텍스트로 받아 **DC tier/grade 보정** (§2.2 호감도와 같은 패턴 — LLM 은 분류만, 엔진은 수치).

**보유 분류**:

- `racial_skill_ids` (종족 기본 — 시드에 들어 있음, 보통 `level=0`) / `learned_skill_ids` (LLM 추천으로 습득) 두 컬렉션으로 분리 저장. `Character.known_skill_ids` 로 병합 조회.
- 일반 공격·점프 같은 보편 행동은 기술 목록에 안 들어간다 — 엔진 기본 동사로 따로 처리.

**의미 매칭 발동** — cast 는 플레이어 입력에 기술 이름이 정확히 들어 있지 않아도 일어날 수 있다. judge 가 캐릭터의 `racial_skill_ids` + `learned_skill_ids` 를 합쳐서 컨텍스트로 받고, 입력의 의도와 의미적으로 부합하는 기술을 매칭한다 (예: "조용히 다가가 등에 칼" → 「그림자 보행」). 두 컬렉션 모두 자동 매칭 대상이고, 출력에는 `source: "racial"|"learned"` 가 붙어 어느 쪽인지 구분된다.

- **회피**: "맨손으로" / "기술 없이" / "그냥 평타" 같은 표현이 보이면 매칭 시도 안 함 — 플레이어가 의도적으로 기술을 끄는 통로.
- **알림 필수**: 매칭 발동 시 본문이나 `log_entry` 에 "「기술명」 발동" 표시. 자동 매칭이 일어났을 때 투명성을 보장하는 장치.
- 게이트 (레벨) 나 MP 검증 실패면 매칭은 그냥 무시 — 평타로 진행하는 사일런트 폴백.

`cast` 파이프라인: 레벨 게이트 검증 → MP 검증 → 사정거리 검증 → AoE 대상 자동 계산 → judge 가 `special_effect` 컨텍스트로 tier/grade 보정 → 데미지/회복/버프 적용 → 퀘스트 트리거.

`ActiveBuff(description: str, duration: int)` — type=buff/debuff 인 기술 cast 또는 §2.7 아이템 use 로 생성. `Character.active_buffs: list[ActiveBuff]` 에 append 로 저장. **스탯에 직접 영향 안 줌** — DC 판정 시 judge 가 `description` 을 컨텍스트로 받아 tier/grade 보정 (§2.2 호감도와 같은 패턴, special_effect 와 동일 경로). `duration` 은 매 턴 종료 시 -1, 0 이 되면 리스트에서 제거.

P1 프론트 `Hero.skills: string[]` 는 UI 태그만 노출. 효과 계산 자체는 P3.

### 2.7 사용 / 소비 (Use) [P3]

**현재 구현 상태**: `engines/inventory/use.py` + 자연어 통합. judge 가 `surroundings.inventory` 컨텍스트로 받아 `UseAction { item_id, target_id? }` 로 분류하면 `flow/turn.py` 가 그 자리에서 엔진을 호출. 옛 `POST /use` REST 엔드포인트는 폐기. heal/damage/mp_restore/buff 분기, on_use 트리거 패스스루 (quest trigger 평가는 §2.8), consumable=True 시 인벤 차감. "약초를 먹는다" / "포션을 마신다" / "연막탄을 던진다" 모두 같은 통로.

`use` 액션 (`actor`, `item`, 선택 `target`):

- `Item.effects` 의 세 번째 분류 — §2.5 의 WeaponEffect / ArmorEffect 와 나란히 `ConsumableEffect` 가 존재하며 `use` 가 이 분기를 처리한다.
- `ConsumableEffect` 에 따라 효과 적용:
  - `heal`: HP 회복
  - `damage`: HP 감소 (투척물·폭탄 같은 적대적 사용)
  - `mp_restore`: MP 회복
  - `buff`: §2.6 의 `ActiveBuff` 를 `target` 에 부여. description + duration (예: 힘 물약 → "근력 일시 강화, 무거운 물건 다루기 쉬워짐" / 5 턴 — STR DC 판정 시 judge 가 보정).
- `Item.on_use` 트리거 실행 (예: 열쇠, 퀘스트 아이템) — `Item.effects` 와 별개의 선택 필드, 자유 텍스트 또는 trigger id. ConsumableEffect 의 정형 효과로 표현 안 되는 1 회성 동작 전용.
- 아이템이 `consumable` 이면 사용 후 인벤토리에서 제거.

### 2.8 진행 (Progression) [P3]

**현재 구현 상태**: `engines/quest.py` + `engines/apply._apply_move` / `engines/inventory/use.use` / `engines/combat.apply_attack_to_defender` / `engines/skill.cast` 의 hook 까지 들어가 있다. 이벤트 매칭 (character_death / location_enter / item_use), single-fire, fail_triggers, prereq 잠금 해제, 보상 자동 적용 (gold/exp/items → player), chapter.progress 갱신과 active → completed 전환 모두 동작. P1 의 narrator set status/summary 경로는 그대로 유지 — 자동 트리거와 병행.

**구조**: `Campaign` → `Chapter` → `Quest` 3-tier.

```python
Chapter(
    title: str,
    summary: str,                     # 동적 진행 요약. 시드 초기값 → narrator 가 매 턴 set 으로 갱신 ([02-runtime.md](./02-runtime.md) §3.2)
    quest_ids: list[str],
    status: Literal["locked", "active", "completed"],
    required: bool,                   # chapter.progress 카운트 대상 여부
    # 런타임 파생 필드 (시드 JSON 에 넣지 않음, 엔진이 매 턴 계산)
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
    # 런타임 필드 (시드 JSON 에 넣지 않음, 엔진이 갱신)
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
- 프론트 노출 ([04-boundary.md](./04-boundary.md) §1): `goals[]` 는 `triggers.map(t => t.name)`, `conditions[]` 는 자유 텍스트 그대로, `difficulty` 는 Tier 라벨 문자열 그대로 (옛 `{value, max, label}` 객체 변환은 폐기), `rewards` 는 `{gold, exp}` 만.

`chapter.progress` 의 `done` / `total` 은 챕터의 quest 중 **`required=true` 인 것만** 카운트한다 (선택 퀘스트는 분모·분자 모두에서 제외). 프론트 표시와 엔진 트리거 평가에서만 사용 — 세션 레이어 ([02-runtime.md](./02-runtime.md) §3.2) 에는 싣지 않는다 (narrator 는 `summary` + `goals` 로 진행을 본다).

P1 은 narrator 가 `{type: "set", entity: "quests|chapters", id, field: "status"|"summary", value: ...}` 로 간접 반영 — 진행 요약 (`summary`) 갱신과 상태 (`status`) 전환만 가능. 자동 트리거는 P3.

### 2.9 동반자 (Companions, pocket-monster 방식) [P3]

**현재 구현 상태**: `engines/apply._apply_move` 가 patron 이동 시 companions 의 `location_id` 도 같이 옮기고, `engines/combat.start_combat` 가 양측 companions 를 turn_order 에 자동 합류한다. `engines/combat.pick_npc_target` 는 진영 (player 측 vs enemy 측) 기준으로 적 후보를 그러모음. 동반자 1인칭 대사·반응은 narrator 서술로만 (별도 AI 없음, docs 명세 그대로).

`Character.companions: list[str]` — patron (이 동반자를 거느린 캐릭터) 이 "주머니에 넣고 다니는" 부하 캐릭터 ID 목록.

- **위치 동기화**: 동반자의 위치는 patron 의 `location_id` 를 따른다 (`effective_location()` 이 반환). 동반자 본인의 `location_id` 필드는 사용하지 않는다 — 둘이 어긋날 일이 없게 위치를 한 군데서만 본다.
- **전투 참여**: `start_combat(participants)` 가 각 participant 의 `companions` 를 자동 확장해 turn_order 에 포함 (중복 제거). 동반자는 자기 DEX 로 이니셔티브를 굴림.
- **피아 식별**: 같은 patron 을 공유하면 아군. NPC AI 는 patron 관점의 affinity 로 적을 찾으므로, 동반자는 자동으로 patron 의 적을 공격하게 된다 (별도 표식 없이 affinity 만으로 처리).
- **비전투 노출**: `target_view` / `surroundings` 의 NPC 목록에 patron 과 함께 등장 (별도 UI 슬롯 아님).

**제약**: 동반자 본인에게는 AI 가 없다. 1 인칭 대사·반응은 narrator 서술로만 표현. P3 이후 `companion_voice_hint` 같은 힌트 필드를 검토할 수 있음.

P1 프론트 `Hero.companions: list[str]` 는 백엔드가 각 char_id 를 `"이름 (종족 직업)"` 문자열로 조립해 만든 배열. 프론트는 그대로 표시. 내부 동반자 로직 (위치 동기화·전투 참여·피아 식별) 은 P3.
