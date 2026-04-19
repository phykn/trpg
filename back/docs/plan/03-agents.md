# 3. 에이전트

> 상위: [plan.md](../plan.md)

## 3.1 DC판정 에이전트

**역할**: 플레이어 입력을 해석하여 판정 여부, 난이도 등급, 관련 스탯, 대상을 결정.

**입력**:
- `player_input`: 플레이어 원문 텍스트
- `surroundings`: 현재 장소 + 주변 엔티티 상태 태그 (§5.4.1)

**출력**:
```json
{
  "action": "skip" | "roll" | "combat" | "clarify",
  "tier": "easy" | "normal" | "hard",
  "stat": "STR" | "DEX" | "CON" | "INT" | "WIS" | "CHA",
  "targets": ["<entity_id>", "<entity_id>"],
  "question": "되물을 내용 (clarify일 때만)"
}
```

`targets` 는 판정 대상 ID 배열. 단일 대상이면 길이 1, 복수 대상(예: 두 경비병 동시 설득)이면 엔진이 actor 의 affinity 가 가장 낮은 대상을 기준으로 `social_bonus` 를 계산한다.

**action 유형**:

| action | 의미 | 다음 단계 |
|---|---|---|
| `skip` | 판정 불필요 (이동, 인사 등) | target_view 없이 바로 내러티브 |
| `roll` | 주사위 필요 | 엔진이 DC 계산 → `pending_check` 저장 → 프론트 주사위 버튼 → `/roll` |
| `combat` | 일반 전투 행동 | [P1 에러 반환] / [P2] 엔진이 자동 주사위 → 내러티브 |
| `clarify` | 해석 불가 / 복합 행동 | 플레이어에게 되물음, 파이프라인 재시작 |

**규칙**:
- 매 턴 호출 (전투/비전투 무관)
- 명시적 대상 없으면 현재 location 이 기본값
- `stat` 은 행동의 성격으로 판단 (플레이어 수치를 볼 필요 없음)
- **히스토리·세션·월드 레이어를 받지 않는다**. 오직 현재 장면(`surroundings`) 만으로 판정. 장기 맥락·과거 턴 요약·엔티티 메모리는 내러티브 전용 (§5, §14.12).

## 3.2 내러티브 에이전트

**역할**: 이야기 서술 + 턴 요약 + 메모리 판정.

**입력**:
- `player_input`: 플레이어 원문
- `judge_result`: DC판정 에이전트 출력
- `grade`: 주사위 결과 등급 (roll/combat 일 때만, §7.3)
- `world_layer`: 세계관 (§5.1)
- `session_layer`: 챕터/퀘스트 요약 (§5.2) [P3 에서 세밀화, P1 은 active_quest 제목만]
- `history_layer`: 최근 N턴 대화 + 이전 턴 요약 (§5.3)
- `target_view`: 대상 엔티티 기준 그래프 1-2홉 (§5.4.2). skip 이면 surroundings 만.

**출력**: 스트리밍. 본문(한국어 2인칭 3-6문장) + delimiter 뒤 JSON.

```
<서술 본문>
---JSON---
{
  "summary": "경비병 설득 성공",
  "state_changes": [
    {"type": "affinity", "actor": "player_01", "target": "guard_01", "grade": "success", "intent": "friendly"}
  ],
  "memorable": true,
  "memory_targets": ["guard_01"],
  "memory": "플레이어가 뇌물을 줘서 통과시켜줌",
  "importance": 3
}
```

**필드**:
- `summary`: 히스토리 로그에 저장될 한 줄 요약 (대상/결과 명시, ~60자)
- `state_changes`: 엔진에 전달할 상태 변경 목록 (§8)
- `memorable`: 이 턴이 기억할 만한지
- `memory_targets`: 기억을 저장할 엔티티 ID 목록 (복수 가능)
- `memory`: 저장할 기억 내용 (`memorable=true` 일 때 필수)
- `importance`: 기억 중요도 (1: 사소, 2: 보통, 3: 중요)

**서술 규율**:
- 수치/확률/DC 를 본문에 노출하지 않음 ("설득을 시도한다" ○, "DC 15 설득" ✗)
- HP·데미지·XP·골드는 엔진이 이미 적용. 본문에서 숫자로 다시 제시하지 않음.
- NPC 목소리는 `target_view.tone_hint`, `disposition` 을 따름.
- `state_changes` 타입은 `set | move | move_item | affinity` 4종만. 위반 항목은 `apply_changes` 가 `rejected[]` 로 돌려보내고 원본 변경은 적용되지 않음.

## 3.3 LLM 런타임

- 단일 모델, 단일 `BASE_URL` (llama.cpp OpenAI-compat 서버). judge·narrate 모두 같은 클라이언트.
- `src/llm/client.py` 가 `LLMClient` 노출 (기존 `src/llm_client/` 에서 `src/llm/` 로 이전).
- 시스템 프롬프트는 `src/llm/prompts/judge.md`, `src/llm/prompts/narrate.md` 에서 로드.
