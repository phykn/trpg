# Item fragment

## Schema (core fields only)

```json
{
  "id": "<ASCII snake_case>",
  "name": "<Korean item name>",
  "description": "<one short Korean sentence, optional>",
  "weight": <float, kg — weapons 1.0~3.0, armor 2.0~10.0, consumables 0.1~0.5>,
  "price": <int, gold — weapons 30~200, armor 20~150, consumables 5~30>,
  "consumable": <bool>,
  "effects": <weapon | armor | consumable | null>
}
```

`effects` shape (discriminated by `type`):

- Weapon: `{"type":"weapon", "weapon_dice":"1d6"|"1d8"|"2d4"|..., "range": 1.5}`
- Armor: `{"type":"armor", "defense": <int 1~5>}`
- Consumable: `{"type":"consumable", "effect":"heal"|"damage"|"mp_restore"|"buff", "amount":<int>, "description": <str|null>, "duration": <int|null>}`
- Key item (when the hint says `kind: "key"`): **`effects: null`, `consumable: false`** plus `on_use: "<one-line purpose>"` (e.g., `"성문 자물쇠를 연다"`). A key is not a consumable — declaring it as `effects.type:"consumable"` puts keys and healing potions in the same category, so the judge will match a key against an input like "약초 먹는다". `on_use` alone is what classifies it as a trigger.

## Rules

- Weapons and armor are `consumable: false` (or omit the field); consumables are `consumable: true` plus `effects.type:"consumable"`.
- `weapon_dice` follows `<digits>d<digits>` (e.g., `1d6`, `2d4`).
- `required` (the stat threshold to use this item) **must always be `null` (or omitted) at the seed stage**. It looks like a partial Stats object, but Pydantic auto-fills missing stats with `10`, so if any of the owner's stats sit below 10 the invariant trips falsely. This field gets populated only later, during in-game crafting of stronger weapons.
- `on_use` is free-form text used to author quest triggers. Usually omitted.
- Do not duplicate the concept of an existing item.
