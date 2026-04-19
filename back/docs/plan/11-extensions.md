# 11. 확장 시스템

> 상위: [plan.md](../plan.md)

Phase 별로 구현 범위가 다름. 수치는 모두 `config/rules.py` 에서 튜닝.

## 11.1 호감도 (Affinity) [P1 최소, P3 완성]

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

## 11.2 월드 시간 (World Time)

`state.world_time` (ISO 8601). [P1 은 턴당 +1분 고정 / P3 는 액션별 `advance_time(action_type, grade, state, rules)`].

P3 `rules.time.cost` (단위: 분):
- `combat_turn_min`: 전투 1턴 경과 시간
- `explore_action_min`: 탐험/조사 기본 소요
- `explore_critical_fail_min`: critical_failure 추가 지연
- `travel_per_connection_min`: 기본 이동 비용

`Connection.travel_min` 설정 시 per-edge override 가 기본값을 대체.

프론트 `Place.date` ("812년 4월 28일"), `Place.hour` (0..23) 은 `mapping/to_front.py` 가 `world_time` 을 파싱해 분리.

## 11.3 성장 (Growth) [P3]

`src/pipeline/growth/` 에 3종 루틴:

- **rest**: `rules.time.recovery` 에 따라 HP/MP 회복. `--minutes N` 또는 `--full`. world_time 동기 경과.
- **train**: `xp_pool` 을 소모해 스탯 +1. 비용 = `base_xp + xp_per_point * max(0, current-10)`. 상한 `max_stat` (기본 20). **시간 경과 없음** (즉시 반영; 훈련 장면 연출은 narrator).
- **learn**: 스킬을 `learned_skills[]` 에 추가. `skill.xp_cost` 소모. **시간 경과 없음**.

P1 에서는 자연어 "휴식한다" → `{action: "skip"}` + narrator `set` 으로만 간접 반영 (HP/MP 는 엔진 전용이라 실제 회복 없음). P3 에서 명시 엔드포인트로 노출.

## 11.4 장비 / 인벤토리 / 거래 [P3]

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

## 11.5 스킬 시스템 [P3]

`Skill(id, name, description, type, target, power, mp_cost, range, required_stats, xp_cost, buff_stat, duration)`.

- `type`: attack / heal / buff / debuff.
- `target`: self / single / area.
- 캐릭터는 `basic_skills` (종족/직업 기본) / `racial_skills` / `learned_skills` 로 분리 저장. `all_skills()` 로 병합 조회.
- `cast` 파이프라인: MP 검증 → 사정거리 검증 → AoE 대상 자동 계산 → 데미지/회복/버프 적용 → 퀘스트 트리거.
- `ActiveBuff` 는 `duration` 턴 동안 유지. 턴 종료 시 `tick` 이 감소.

P1 프론트 `Hero.skills: string[]` 는 UI 태그만 노출. 효과 계산은 P3.

## 11.6 사용 / 소비 (Use) [P3]

`use --actor A --item I [--target T]`:
- `ConsumableEffect(heal, damage)` 에 따라 HP 변화.
- `Item.special` 의 `on_use` 트리거 실행 (예: 열쇠, 퀘스트 아이템).
- 아이템이 `consumable` 이면 인벤토리에서 제거.

## 11.7 진행 (Progression) [P3]

**구조**: `Campaign` → `Chapter` → `Quest` 3-tier.

- `Quest(giver_id, prerequisite_ids, conditions[], fail_conditions[], rewards, status, required)`.
- `QuestCondition(type, target_id)`. 타입: `location_enter`, `character_death`, `item_use`, …. `Quest.conditions_met: list[bool]` 가 조건별 완료 여부를 병렬 저장 (킬 카운트 같은 누적 조건은 미지원 — `required_by` 엣지만 쓰는 단일 충족 모델).
- `status`: `locked → active → completed | failed`.
- `apply_changes` 이후 `check_quests()` 가 관련 트리거로 조건 재평가. 완료/실패 시 `maybe_check_chapters()` 가 상위 전환.

세션 레이어(§5.2) `active_chapter.progress` 는 **`required=true` 퀘스트만** 카운트.

P1 은 narrator 가 `{type: "set", entity: "quests", id, field: "status", value: "completed"}` 로만 간접 반영. 자동 트리거는 P3.

## 11.8 동반자 (Companions, pocket-monster 방식) [P3]

`Character.companions: list[str]` — patron 이 "주머니에 넣고 다니는" 부하 캐릭터 ID 목록.

- **위치 동기화**: `effective_location(char, state)` 이 patron 의 `location_id` 를 반환. 동반자 본인의 `location_id` 는 스토리지 용도로만 유지.
- **전투 참여**: `start_combat(participants)` 가 participants 각자의 `companions` 를 자동 확장해 turn_order 에 포함 (중복 제거). 동반자는 자기 DEX 로 initiative 를 굴린다.
- **피아 식별**: 같은 patron 을 공유하는 두 엔티티를 아군으로 간주. NPC AI 는 patron 관점 affinity 로 적을 찾으므로 동반자는 자동으로 patron 의 적을 공격.
- **비전투 호출**: `target_view` / `surroundings` 의 NPC 목록에도 patron 과 함께 노출되며 별도 slot 이 아님.

제약: 동반자 본인에게는 AI 가 없어 1인칭 대사·반응은 narrator 서술로만 표현. 향후 `companion_voice_hint` 같은 필드를 고려.

P1 프론트 `Hero.companions: string[]` 는 이름 리스트만 노출. 내부 동반자 로직은 P3.
