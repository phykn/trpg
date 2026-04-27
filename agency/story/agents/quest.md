# Quest fragment

## 스키마 (핵심 필드만)

```json
{
  "id": "q_<짧은 식별어>",
  "title": "<한국어, 짧은 명사구>",
  "summary": "<한 문장 — 누구의 의뢰인지·무엇을 하는지>",
  "giver_id": "<characters/ 의 id>",
  "difficulty": "매우 쉬움" | "쉬움" | "보통" | "어려움" | "매우 어려움" | "전설" | "신화",
  "triggers": [
    {"id":"<짧은 키>", "name":"<한국어 한 줄>", "type":"character_death"|"location_enter"|"item_use", "target_id":"<해당 종류의 id>"}
  ],
  "conditions": ["<자유 텍스트 제약, 옵션>"],
  "rewards": {"gold": <int>, "exp": <int>},
  "status": "locked" | "active",
  "required": true | false,
  "prerequisite_ids": ["<다른 quest 의 id>", ...]
}
```

## 규칙

- `giver_id` — **시나리오의 characters 안에 존재**. 의뢰자 캐릭터.
- `triggers[*].target_id` 는 `type` 에 따라 가리키는 풀이 다르다:
  - `character_death` → characters 안의 id (보통 적)
  - `location_enter` → locations 안의 id
  - `item_use` → items 안의 id
- `prerequisite_ids` — 다른 quest 의 id (해당 quest 가 끝나야 잠금 해제). 보통 생략.
- 시작부터 활성인 quest 는 `status: "active"`, 후속·잠금은 `"locked"`.
- `triggers` 는 보통 1~3 개. 모두 충족돼야 quest 가 completed 로 전환.
- `fail_triggers` 도 같은 모양 (실패 조건). 보통 생략.
- 기존 quest 와 의도 중복 금지.
- `triggers_met` / `fail_triggers_met` 같은 런타임 필드는 박지 말 것.

## 보상 (rewards)

`difficulty` 와 균형 맞춰 박는다:

| difficulty | exp | gold |
|---|---|---|
| 매우 쉬움 | 25 | 10 |
| 쉬움 | 50 | 25 |
| 보통 | 100 | 50 |
| 어려움 | 200 | 100 |
| 매우 어려움 | 400 | 200 |
| 전설 | 800 | 500 |
| 신화 | 1500 | 1000 |

플레이어 레벨업 비용은 `100 × current_level` (linear, level 0→1=100). 메인 퀘스트 한 개로 1~2 레벨 점프가 자연스럽고, 사이드 퀘스트는 그 절반 정도.
