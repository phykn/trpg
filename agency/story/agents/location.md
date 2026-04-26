# Location fragment

## 스키마 (핵심 필드만)

```json
{
  "id": "<ASCII snake_case, 예: tavern_02, gate_01>",
  "name": "<한국어 장소명>",
  "description": "<한두 문장 — 장소의 외형·분위기>",
  "tags": ["outdoor"|"indoor", "town"|"wilderness"|"dungeon"|... ],
  "weather": ["맑음"|"비"|"안개"|"눈"|...],
  "connections": [
    {"target_id": "<다른 location 의 id>"}
  ]
}
```

## 규칙

- `tags` 와 `weather` 는 기존 시드와 같은 어휘 패턴을 따르라 (기존이 `"outdoor"`, `"town"`, `"맑음"` 식이면 같은 식으로).
- `connections[*].target_id` 는 **반드시 시나리오의 다른 location id** 여야 한다. 자기 자신을 가리키면 안 됨.
- 양방향 연결은 강제하지 않음 (있어도 OK, 없어도 OK).
- `sleep_risk`, `sleep_encounters`, `hidden_items`, `hidden_connections`, `item_ids`, `difficulty` 같은 P3 필드는 생략 (default).
