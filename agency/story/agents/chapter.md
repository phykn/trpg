# Chapter fragment

## 스키마

```json
{
  "id": "ch<번호>",
  "title": "<한국어, 짧은 명사구>",
  "summary": "<한두 문장 — 챕터의 큰 흐름·목표>",
  "quest_ids": ["<quest id>", ...],
  "status": "locked" | "active",
  "required": true | false
}
```

## 규칙

- `quest_ids` — **시나리오의 quests 안에 존재**하는 id 들. 보통 2~5 개.
- 시작 챕터는 `status: "active"`, 다음 챕터는 `"locked"`.
- `progress` 필드는 적지 말 것 (런타임이 채움).
- `required: true` 인 챕터는 메인 줄거리, `false` 는 사이드.
