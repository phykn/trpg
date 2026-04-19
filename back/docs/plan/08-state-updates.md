# 8. 상태 업데이트

> 상위: [plan.md](../plan.md)

## 8.1 state_changes 형식

내러티브 에이전트가 배출할 수 있는 타입은 **4종** (`Literal["set","move","move_item","affinity"]`):

```json
[
  {"type": "set",       "entity": "characters", "id": "guard_01", "field": "disposition.aggressive", "value": 80},
  {"type": "move",      "target": "player_01",  "destination": "plaza_01"},
  {"type": "move_item", "item":   "iron_key",   "from": "chest_01", "to": "player_01"},
  {"type": "affinity",  "actor":  "player_01",  "target": "guard_01", "grade": "success", "intent": "friendly"}
]
```

- `set.entity` ∈ `characters | items | locations`. `set.field` 는 점 표기 경로 (`disposition.lawful`, `weather` 등).
- **list 필드 (`relations`, `inventory_ids`, `memories`, `goals`, `basic_skills`, `learned_skills`, `companions`) 는 `set` 으로 조작 불가**. 엔진 전용(HP/MP/exp/gold/alive/in_combat/death_saves 등) 도 금지.
- `affinity` 는 `grade × intent × target.disposition` 으로 `rules.social` 기반 delta 를 엔진이 산출. narrator 는 숫자를 정하지 않는다 (§11.1).
- `move` / `move_item` / `affinity` 적용 시 엔진이 자동으로 **퀘스트 트리거** 실행 (`location_enter`, `item_use`, `character_death`) [P3].

**검증과 `rejected[]`**: `apply_changes` 는 narrator 출력을 Pydantic union 으로 validate. 스키마 위반 (잘못된 필드명, 알 수 없는 타입, 엔진 전용 필드 set 등)은 해당 항목만 `rejected[]` 로 돌려보내고, 나머지 유효 변경은 적용. 반환: `{applied, rejected, world_time, created_ids?, quest_updates?, chapter_updates?}`. 오케스트레이터는 `rejected[]` 를 로깅만 하고 narrator 재호출은 하지 않는다 [P3 에서 재호출 루프 검토].

**내부 전용 타입** (엔진/CLI 만 사용, narrator 는 발행 금지):
- `{"type": "death", "target": "<id>"}` — 캐릭터 사망 처리 + 시체/드랍/퀘스트 연쇄. [P2]
- `{"type": "create", "entity": "items|characters|locations|races|quests", "data": {...}}` — 런타임 엔티티 생성, ID 자동 부여. [P3]

경계를 둔 이유: 내러티브 에이전트가 직접 엔티티를 생성/살해하지 못하게 해 상태의 결정권을 엔진에 묶어 둠.

## 8.2 프론트 반영

`apply_changes` 후 엔진은 변경된 슬롯만 `mapping/to_front.py` 로 재직렬화해 `state_patch` 이벤트 방출. 예를 들어 `characters[player_01].location_id` 변경 → `state_patch: {place: {...}}`. 슬롯 단위는 Hero / Subject / Quest / Place 4종 (Log 는 별도 `log_entry` 이벤트). §12.
