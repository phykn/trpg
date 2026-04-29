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
  ],
  "item_ids": ["<item id>", ...]
}
```

## 규칙

- `tags` 와 `weather` 는 기존 시드와 같은 어휘 패턴을 따르라 (기존이 `"outdoor"`, `"town"`, `"맑음"` 식이면 같은 식으로).
- `connections[*].target_id` 는 **반드시 시나리오의 다른 location id** 여야 한다. 자기 자신을 가리키면 안 됨.
- 단발 호출(파이프라인이 아닌 `run_story.py location`) 일 때 `connections[*].target_id` 는 **이미 디스크에 만들어져 있는** location 의 id 만 가리킬 수 있다. 아직 없는 미래 id 를 적으면 검증에서 실패한다.
- 양방향 연결은 강제하지 않음 (있어도 OK, 없어도 OK).
- `item_ids` — 이 장소에 놓여 있는 item 의 id. 시나리오의 items 안에 실재해야 함. user 메시지에 "item_ids 에 정확히 [...] 를 넣어라" 지시가 있으면 그대로 넣는다. 없으면 빈 리스트.
- `sleep_risk` 는 location 의 안전도에 따라 지정한다:
  - `"safe"` (default, 생략 가능) — 여관·집·마을 안전 구역. 풀회복.
  - `"risky"` — 야외·황무지·마을 외곽. 50% 확률로 야간 인카운터.
  - `"dangerous"` — 던전·적 영역·야생 깊은 곳. 60% 확률로 야간 인카운터.
- `sleep_encounters` — `risky`/`dangerous` 일 때 야간에 등장할 수 있는 character id 의 리스트 (보통 잡몹·들쥐·산적). characters 안에 실재해야 한다. 비워두면 폴백으로 풀회복.
- `hidden_items`, `hidden_connections`, `difficulty` 는 생략 (Pydantic default 로 충분).
