# Race fragment

## 스키마

```json
{
  "id": "<ASCII snake_case>",
  "name": "<한국어 종족명>",
  "description": "<한국어 한두 문장>",
  "racial_skills": []
}
```

## 규칙

- `name` — "인간" / "엘프" / "드워프" 식 한 단어 또는 짧은 명사구.
- `description` — 한두 문장. 종족의 신체·기질·역할 (예: "땅 밑 산에서 자란 단단한 종족. 망치질과 광맥에 능하다.").
- `racial_skills` — 빈 리스트 `[]`. 첫 단계라 skill 합성은 별도 단계에서.
- 기존 race 와 의미·역할이 중복되면 안 된다 (이미 "장수하는 지혜의 종족" 이 있으면 비슷한 컨셉 X).
