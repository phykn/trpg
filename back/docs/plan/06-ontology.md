# 6. 온톨로지 (그래프)

> 상위: [plan.md](../plan.md)

## 6.1 구조

노드 = 엔티티 (캐릭터, 아이템, 장소). 엣지 = 관계.

**구조적 엣지**:
- `location_id`: NPC → 장소
- `equipment`: NPC → 아이템
- `inventory_ids`: NPC → 아이템
- `connections`: 장소 → 장소

**의미적 엣지** (init 시 자동 추론):
- 퀘스트 condition 의 `target_id` → `required_by` 엣지
- 퀘스트 `giver_id` → `gives_quest` 엣지
- 퀘스트 condition `character_death` → `kill_target_of` 엣지
- 퀘스트 `rewards.items` → `reward_of` 엣지

**config 정의 관계** (서사적):
- NPC 의 `hints`: 아는 정보/퀘스트 연결
- Item 의 `key_item_id`: 열쇠 → 문 연결
- Item 의 `unlocks`: 아이템 → 오브젝트 연결

**런타임 관계**:
- `memories[]`: 엔티티별 기억 (§9)

## 6.2 target_view 조립

target 에서 그래프 1-2홉을 탐색하되, **이종 엣지 타입도 순회** 가능.

예: `guard_01 → gives_quest → quest_01 → condition → plaza_01` (퀘스트 관련 장소까지 도달).

구현은 `src/ontology/graph.py` 가 매 호출마다 `GameState` 에서 임시 그래프를 구성. 성능 최적화(인덱싱·캐시)는 P1 이슈 아님.

## 6.3 장소 확장

```python
Location(
    hidden_items=[...],         # 수색 성공 시 발견
    hidden_connections=[...],   # 수색 성공 시 통로 발견
    difficulty="normal",        # 수색 난이도 등급 (tier)
)

Connection(
    target_id="cellar",
    difficulty="hard",          # 자물쇠 난이도 등급 (tier)
    key_item_id="iron_key",     # 이 열쇠 보유 시 자동 해제
)
```

모든 엔티티의 판정 난이도는 `difficulty: "easy" | "normal" | "hard"` tier 문자열로 통일 (엔티티 종류가 용도를 결정: 장소 → 수색, 통로 → 자물쇠, 아이템 → 잠금/해독 등).
