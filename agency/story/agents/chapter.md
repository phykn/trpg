# Chapter fragment

## 스키마

```json
{
  "id": "ch<번호>",
  "title": "<한국어, 짧은 명사구>",
  "summary": "<한두 문장 — 챕터의 큰 흐름·목표>",
  "quest_ids": ["<quest id>", ...],
  "prerequisite_ids": ["<다른 chapter 의 id>", ...],
  "status": "locked" | "active",
  "required": true | false
}
```

## 규칙

- `quest_ids` — **시나리오의 quests 안에 존재**하는 id 들. 보통 2~5 개. 한 quest 는 정확히 한 chapter 에만 속함.
- `prerequisite_ids` — 다른 chapter 의 id. 그 chapter 들이 모두 `completed` 가 되면 이 chapter 가 `locked → active` 로 풀린다. 시작 chapter (prereq 비어 있음) 는 게임 시작 시 `active`, 나머지는 `locked`.
- `status` 는 `prerequisite_ids` 가 비어 있으면 `"active"`, 아니면 `"locked"` — 힌트의 status 지시를 그대로 따른다.
- `progress` 필드는 적지 말 것 (런타임이 채움).
- `required: true` 인 챕터는 메인 줄거리, `false` 는 사이드.
