# Character fragment (NPC / 몬스터)

## 스키마 (핵심 필드만)

```json
{
  "id": "<ASCII snake_case, 예: smith_01, goblin_02>",
  "name": "<한국어>",
  "race_id": "<races/ 의 id 중 하나>",
  "job": "<짧은 한국어, 예: 대장장이 / 정찰병 / 마을 장로>",
  "role": "<배경 한 줄>",
  "appearance": "<외형 한 줄>",
  "description": "<한두 문장 — 성격·역할>",
  "tone_hint": "<말투 한 줄>",
  "level": <int 1~15>,
  "location_id": "<locations/ 의 id, 또는 null>",
  "max_hp": <int — 공식으로 계산>,
  "hp": <max_hp 와 같은 값>,
  "max_mp": <int — 공식으로 계산>,
  "mp": <max_mp 와 같은 값>,
  "stats": {"STR":<0-20>, "DEX":<0-20>, "CON":<0-20>, "INT":<0-20>, "WIS":<0-20>, "CHA":<0-20>},
  "disposition": {"lawful":<0-100>, "moral":<0-100>, "aggressive":<0-100>},
  "inventory_ids": ["<item id>", ...],
  "equipment": {"<slot>": "<item id>"},
  "combat_behavior": {"attack_priority": "...", "flee_hp_percent": <int>},
  "learned_skills": [
    {
      "id": "<ASCII snake_case>",
      "name": "<한국어 짧은 명사구>",
      "description": "<짧은 한국어 한 줄>",
      "level": <int — character.level 이하>,
      "type": "attack" | "heal" | "buff" | "debuff",
      "target": "self" | "single" | "area",
      "primary_stat": "STR" | "DEX" | "CON" | "INT" | "WIS" | "CHA",
      "power": <int>,
      "mp_cost": <int>,
      "duration": <int — type 에 따라 다름, 아래 룰>
    }
  ]
}
```

## 규칙

- `race_id` — **반드시 시나리오의 races 안에 존재**.
- `location_id` — 시나리오의 locations 안에 존재 (또는 `null`).
- `inventory_ids` 와 `equipment` 슬롯의 모든 값들 — 시나리오의 items 안에 존재.

### 스탯 — 페어 트레이드 (절대 위반 금지)

6 스탯은 세 페어로 묶이고, 각 페어 합이 정확히 20:

- `STR + CHA = 20`
- `DEX + WIS = 20`
- `CON + INT = 20`

총합 항상 60. 기본값 10/10/10/10/10/10 (= 페어 20×3). 컨셉에 따라 페어 안에서 트레이드: 강한 적 → STR 14 / CHA 6, 둔한 거구 → DEX 6 / WIS 14, 영리한 약골 → CON 6 / INT 14. 페어 합 20 유지.

### Level 과 HP / MP — 공식대로 박기

- `level` 은 컨셉에 맞게: 평민·노파 1, 일반 병사·도적 3~5, 정예·우두머리 6~10, 고대 괴수·보스 10~15.
- `max_hp = (10 + CON) + level × (5 + CON ÷ 4)`
- `max_mp = (5 + INT) + level × (3 + INT ÷ 4)`
- `hp = max_hp`, `mp = max_mp` (시드는 풀체력 시작).

예) level=5, CON=14, INT=10 → max_hp = (10+14) + 5×(5+14÷4) = 24 + 5×(5+3) = 64. max_mp = (5+10) + 5×(3+10÷4) = 15 + 5×(3+2) = 40.

### Equipment — combat_behavior 박은 NPC 는 무기 장착

- `equipment` 슬롯은 `head/top/bottom/feet/leftHand/rightHand/acc1/acc2` 중 하나.
- weapon → `leftHand` 또는 `rightHand`. armor → `head/top/bottom/feet`. consumable 은 equipment 에 못 박는다.
- two-handed weapon 은 `leftHand` 와 `rightHand` 양쪽에 같은 id 를 박는다.
- `combat_behavior` 가 박힌 NPC 는 `inventory_ids` 의 무기 1 개를 `equipment.rightHand` (또는 양손이면 양쪽) 에 박아라.
- equipment 슬롯의 id 는 `inventory_ids` 안에도 있어야 한다.
- 인벤 무게 합은 `STR × 10` kg 을 넘으면 안 된다 (carry capacity).

### combat_behavior — 적대 NPC 에만

- 적대 NPC: `aggressive` 70~100 + `combat_behavior` 박기 (예: `{"attack_priority":"nearest", "flee_hp_percent":25}`).
- `attack_priority` 는 정확히 5 개 중 하나: `"nearest"` | `"lowest_hp"` | `"highest_threat"` | `"healer_first"` | `"random"`.
- 비적대 NPC 는 `aggressive` 70 미만 + `combat_behavior` 박지 말 것.

### Skill — NPC / 몬스터는 기본 스킬 1~3 개

- 주인공은 빈 채로 시작해 게임 중에 배우지만, 시드 NPC 는 race · job 에 어울리는 `learned_skills` 1~3 개를 갖고 등장.
- 각 skill `level` 은 **character.level 이하**. 소유자가 못 쓰는 스킬을 박으면 안 된다.
- skill `id` 는 같은 character 안에서 유일.
- `duration` 은 type 에 따라:
  - `attack` / `heal` → `0` (지속 시간 없음, 즉시 적용)
  - `buff` / `debuff` → `> 0` (지속 턴 수)
- 컨셉 매핑 예) 도적·전사: STR/DEX 기반 attack · 마법사: INT 기반 attack/buff · 노인·정보꾼: WIS 기반 buff/debuff · 거대 몬스터: STR/CON 기반 area attack.

### 그 밖에

- `is_player`·`gold`·`xp_pool`·`active_buffs`·`memories` 등은 박지 말 것 (런타임이 채움).
- `tone_hint` 는 짧고 구체 ("퉁명스러운 단답, 가끔 긴 한숨" 식).
- 기존 character 와 이름·역할 중복 금지.

## 검증

작성된 character 는 빌드 단계에서 `backend/src/engines/invariants.py` 의 `check.seed_character` 로 자동 검증된다. 룰 어기면 위반 메시지가 self-correction 루프로 돌아온다 — 한 번에 모든 위반이 보고되니 그에 맞춰 모두 고쳐라.
