# Item fragment

## 스키마 (핵심 필드만)

```json
{
  "id": "<ASCII snake_case>",
  "name": "<한국어 아이템명>",
  "description": "<한 문장 짧게, 생략 가능>",
  "weight": <float, kg — 무기 1.0~3.0, 방어구 2.0~10.0, 소모품 0.1~0.5>,
  "price": <int, 골드 — 무기 30~200, 방어구 20~150, 소모품 5~30>,
  "consumable": <bool>,
  "effects": <weapon | armor | consumable | null>
}
```

`effects` 의 모양 (`type` 으로 discriminated):

- 무기: `{"type":"weapon", "weapon_dice":"1d6"|"1d8"|"2d4"|..., "range": 1.5, "two_handed": false}`
- 방어구: `{"type":"armor", "defense": <int 1~5>}`
- 소모품: `{"type":"consumable", "effect":"heal"|"damage"|"mp_restore"|"buff", "amount":<int>, "description": <str|null>, "duration": <int|null>}`

## 규칙

- 무기·방어구는 `consumable: false` (또는 생략), 소모품은 `consumable: true` + `effects.type:"consumable"`.
- `weapon_dice` 는 `<숫자>d<숫자>` 형식 (예: `1d6`, `2d4`).
- `required` (사용 요구 능력치) 필드는 강한 무기·방어구에만 박는다 — `{"STR": <int>}` 같은 Stats 부분 객체. 보통 생략.
- `on_use` 는 quest trigger 용 자유 텍스트. 보통 생략.
- 기존 item 과 컨셉 중복 금지.
