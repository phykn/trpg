# Skill fragment

## 스키마

```json
{
  "id": "<ASCII snake_case, 예: fireball, drill_strike>",
  "name": "<한국어 짧은 명사구>",
  "description": "<짧은 한국어 한 줄>",
  "level": <int — 사용자 캐릭터 레벨 이하>,
  "type": "attack" | "heal" | "buff" | "debuff",
  "target": "self" | "single" | "area",
  "primary_stat": "STR" | "DEX" | "CON" | "INT" | "WIS" | "CHA",
  "special_effect": "<짧은 한국어, 비어 있어도 OK>",
  "power": <int — attack/heal 의 베이스 값. buff/debuff 는 0 도 가능>,
  "mp_cost": <int>,
  "range": <float — m 단위, 보통 1.5 (근접) ~ 5.0 (원거리)>,
  "duration": <int — type 에 따라>
}
```

## 규칙

- `id` 는 같은 시나리오의 다른 skill 과 절대 중복 X.
- `level` — racial 스킬은 항상 1, 캐릭터 학습 스킬은 그 캐릭터 레벨 이하.
- `duration` 은 type 에 따라:
  - `attack` / `heal` → `0` (지속 시간 없음, 즉시 적용)
  - `buff` / `debuff` → `> 0` (지속 턴 수)
- `primary_stat` 매핑 가이드:
  - 무력형 attack → STR/DEX (검술·근접) 또는 INT (마법 화염·번개)
  - heal → WIS / INT
  - buff (방어·집중) → WIS / CON
  - debuff (저주·기만) → CHA / INT
- 컨셉 일관: skill 이름·description 의 톤이 owner (race 또는 character) 와 어긋나면 안 됨. 도적의 스킬이 빛 마법 식이면 톤 깨짐.
- 기존 skill 과 의미·이름 중복 금지.
- `id` 강제 힌트가 user 메시지에 오면 정확히 그 id 로.

## 검증

skill 단계는 `check.skills(character, skills_pool)` 로 자동 검증된다 — type ↔ duration 짝, 캐릭터 레벨 ≥ skill 레벨, 그리고 캐릭터의 racial/learned skill_ids 가 skills_pool 에 실재하는지.
