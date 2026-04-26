# Character fragment (NPC / 몬스터)

## 스키마 (핵심 필드만)

```json
{
  "id": "<ASCII snake_case, 예: smith_01, goblin_02>",
  "name": "<한국어>",
  "race_id": "<races/ 의 id 중 하나>",
  "job": "<짧은 한국어, 예: 대장장이 / 정찰병 / 마을 장로>",
  "role": "<배경 한 줄, 예: '마을 대장장이' / '고블린 침공군의 정찰'>",
  "appearance": "<외형 한 줄>",
  "description": "<한두 문장 — 성격·역할>",
  "tone_hint": "<말투 한 줄, 짧고 구체적으로>",
  "location_id": "<locations/ 의 id, 또는 null>",
  "max_hp": <int>,
  "hp": <max_hp 와 같은 값>,
  "stats": {"STR":<0-20>, "DEX":<0-20>, "CON":<0-20>, "INT":<0-20>, "WIS":<0-20>, "CHA":<0-20>},
  "disposition": {"lawful":<0-100>, "moral":<0-100>, "aggressive":<0-100>},
  "inventory_ids": ["<item id>", ...],
  "equipment": {"<slot>": "<item id>"},
  "combat_behavior": {"attack_priority": "...", "flee_hp_percent": <int>}
}
```

## 규칙

- `race_id` — **반드시 시나리오의 races 안에 존재**. 임의 race 명 금지.
- `location_id` — 시나리오의 locations 안에 존재 (또는 `null` 로 어디에도 안 둠).
- `inventory_ids` 와 `equipment` 슬롯의 모든 값들 — 시나리오의 items 안에 존재.
- `equipment` 의 슬롯 키는 정확히 `head, top, bottom, feet, leftHand, rightHand, acc1, acc2` 중 하나. 다른 키 금지.
- 평범한 마을 NPC: `stats` 모두 10±, `hp/max_hp` 15~25, `disposition` 50± 근처, `combat_behavior` 생략.
- 적대 몬스터: `aggressive` 70~100, `combat_behavior` 박기 (예: `{"attack_priority":"nearest", "flee_hp_percent":25}`), `stats` 종족 컨셉 따라.
- `is_player`·`level`·`gold`·`xp_pool`·`learned_skills`·`active_buffs`·`memories` 등은 박지 말 것 (런타임이 채움).
- `tone_hint` 는 짧고 구체 ("퉁명스러운 단답, 가끔 긴 한숨" 식).
- 기존 character 와 이름·역할 중복 금지.
