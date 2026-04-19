# 10. 전투 [P2]

> 상위: [plan.md](../plan.md)

> P1 은 `{action: "combat"}` 을 `SSE error(CombatNotSupported)` 로 반환한다. 아래는 P2 예정 설계.

## 10.1 전투 DC

전투에서는 **10 + 대상 방어도 합산**이 DC:
```
enemy_defense = 10 + Σ(armor_effect.defense for slot in 방어 슬롯)
required_roll = round(20 / (1 + e^(-k(enemy_defense - player_stat))))
```

- 무기 range ≤ 1.5 → STR, 초과 → DEX 를 `player_stat` 으로 사용.
- 장비 없을 때는 `UNARMED_DAMAGE="1d4"`, `UNARMED_RANGE=1.5` 폴백.
- 방어도 합산 슬롯은 P2 에서 확정 (현재 프론트는 head/top/bottom/feet 체계, §11.4 참조).

## 10.2 전투 상태

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

## 10.3 플레이어 턴

매 턴 DC판정 에이전트 호출:
- "고블린을 공격" → `{action: "combat"}` → 엔진 자동 주사위
- "샹들리에 떨어뜨리기" → `{action: "roll", tier, stat}` → 플레이어 주사위 (비전투 플로우 재사용)

플레이어는 매 턴 행동을 **선택**함. 자동인 건 주사위만.

## 10.4 NPC AI

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

## 10.5 도주 (Flee)

`rules.combat.flee`: `dice="1d20"`, `base_dc=12`, `dex_modifier=True`. 플레이어도 `flee` 명령으로 동일 메커닉 사용.

**기회 공격**: `opportunity_attack=True` (기본)일 때, 도주 굴림 전에 같은 location 의 적대적 전투 참가자들이 각 1회 자동 공격. 기회 공격으로 HP 0 이 되면 도주 굴림 없이 실패.

## 10.6 전투 종료

- 적 전멸
- 도주 성공
- 플레이어 사망 → §10.7

전투 종료 시 엔진이 `combat_state` 삭제.

## 10.7 플레이어 사망 / Death Save

`rules.combat.death`:
- `instant_death: bool = False` — True 면 HP 0 즉시 사망 (NPC/몬스터는 기본 True, 플레이어는 `revive_coins` 우선).
- `revive_coins: int = 0` — 플레이어 전용 목숨 토큰. 0 초과면 HP 0 이 되어도 토큰 1개 소모하고 `max_hp * revive_ratio` (기본 0.5) 로 즉시 부활. 토큰 소진 후에만 dying/dead 전이.
- 토큰 없고 `instant_death=False` 면 HP ≤ 0 시 death save 진입. `death_saves={successes, failures}` 할당.
- 매 턴 `d20 ≥ save_dc` (기본 10). 성공 3회 → 안정화 (HP=1). 실패 3회 → 사망. 대미지 재피격 시 실패 카운트 +1. critical_failure 시 +2.

## 10.8 SSE 확장 [P2]

- `combat_start`: `{turn_order, round}`
- `combat_turn`: `{actor, action, grade, damage?}`
- `combat_end`: `{outcome: "victory" | "defeat" | "fled"}`

P1 이벤트 집합(§4.4) 을 덮어쓰지 않고 추가만.
