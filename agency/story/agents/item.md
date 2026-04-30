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

- 무기: `{"type":"weapon", "weapon_dice":"1d6"|"1d8"|"2d4"|..., "range": 1.5}`
- 방어구: `{"type":"armor", "defense": <int 1~5>}`
- 소모품: `{"type":"consumable", "effect":"heal"|"damage"|"mp_restore"|"buff", "amount":<int>, "description": <str|null>, "duration": <int|null>}`
- 키 아이템 (`kind: "key"` 힌트 받았을 때): **`effects: null`, `consumable: false`** + `on_use: "<용도 한 줄>"` (예: `"성문 자물쇠를 연다"`). 키는 소모품이 아니다 — `effects.type:"consumable"` 로 지정하면 judge 가 회복약과 키를 같은 카테고리로 보고 "약초 먹는다" 같은 입력에 키를 매칭하는 사고가 난다. `on_use` 만으로 trigger 분류된다.

## 규칙

- 무기·방어구는 `consumable: false` (또는 생략), 소모품은 `consumable: true` + `effects.type:"consumable"`.
- `weapon_dice` 는 `<숫자>d<숫자>` 형식 (예: `1d6`, `2d4`).
- `required` (사용 요구 능력치) 필드는 **시드 단계에서는 절대 채우지 말 것 — 항상 `null` (또는 생략)**. Stats 부분 객체로 보이지만 Pydantic 이 비어 있는 stat 도 `10` 으로 자동 채우기 때문에, owner 의 stat 이 10 미만이면 invariant 가 잘못 잡는다. 게임 중 강한 무기 가공 단계에서나 채워질 필드.
- `on_use` 는 quest trigger 용 자유 텍스트. 보통 생략.
- 기존 item 과 컨셉 중복 금지.
