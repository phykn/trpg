# 9. 메모리 시스템

> 상위: [plan.md](../plan.md)

## 9.1 구조

모든 엔티티(NPC, 장소, 플레이어) 공통:

```python
class Memory:
    content: str       # "플레이어가 뇌물을 줘서 통과시켜줌"
    importance: int    # 1: 사소, 2: 보통, 3: 중요
    turn: int          # 기록된 턴 번호
```

## 9.2 저장

내러티브 에이전트가 `memorable=true` 로 판정하면, 엔진이 `memory_targets` 의 각 엔티티 `memories[]` 에 저장. narrator 는 `memories[]` 필드를 `set` 으로 건드릴 수 없고 (§8), 오직 이 경로로만 추가.

## 9.3 용량 관리

- 엔티티당 최대 N 개 (`rules.memory.cap`, 기본 20).
- cap 도달 시: importance 낮은 것부터 제거. 같은 importance 면 오래된 것 (turn 작은 것) 부터 제거.
- 모순되는 메모리는 둘 다 저장. 내러티브 에이전트가 시간순으로 해석 ("예전엔 믿었는데 배신당했다").

## 9.4 활용

- `target_view` 에 target 의 `memories[]` 포함 → 내러티브가 NPC 기억을 반영.
- 스탯 어뷰즈 방지: "또 설득하려 한다" 가 쌓이면 NPC affinity/disposition 이 내려가고, 그 결과가 **다음 턴의 `surroundings` 상태 태그**에 드러난다 (예: `경계중(affinity 25)`). DC판정은 이 태그를 보고 자연스럽게 tier 를 올린다 — 메모리 자체를 직접 읽지 않는다.
