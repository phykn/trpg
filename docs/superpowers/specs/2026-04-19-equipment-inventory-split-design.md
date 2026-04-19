# Equipment / Inventory Type Split

Date: 2026-04-19
Status: Approved design, pending implementation plan

## Goal

Split the current single `Hero.inventory: InventoryItem[]` (where `eq: boolean` distinguishes equipped vs carried) into two distinct concepts with distinct types:

- **Equipment** — fixed body slots; at most one item per slot.
- **Inventory** — carried, unequipped items; stackable by quantity.

The motivation is to make the domain model reflect what the data actually means. The current `eq` flag overloads one array with two different concepts, which blocks slot-aware features (e.g., "is the head slot empty?", "what's in the right hand?") without post-hoc filtering.

## Non-goals

- UI for moving items between inventory and equipment (dragging, equip/unequip buttons).
- Equipment stats, bonuses, enchants, or validation that an item fits a slot.
- Truncation/overflow behavior when the equipped list is long — deferred per user decision.
- Backend/API concerns — `services/` is still mock-only; swap point remains `services/index.ts`.

## Slot inventory

Eight fixed slots, English keys with Korean UI labels:

| Key          | Korean UI label |
|--------------|-----------------|
| `head`       | 머리            |
| `top`        | 상의            |
| `bottom`     | 하의            |
| `feet`       | 신발            |
| `leftHand`   | 왼손            |
| `rightHand`  | 오른손          |
| `acc1`       | 악세사리 1      |
| `acc2`       | 악세사리 2      |

Slot keys live on the `Equipment` type; Korean labels are a presentation concern and belong wherever UI code needs them (for the current spec, they are not shown — see UI section).

## Type changes (`front/types/game.ts`)

```ts
// Before
export type InventoryItem = { n: string; q: number; eq: boolean };

// After
export type InventoryItem = { n: string; q: number };

export type EquipItem = { n: string };

export type Equipment = {
  head: EquipItem | null;
  top: EquipItem | null;
  bottom: EquipItem | null;
  feet: EquipItem | null;
  leftHand: EquipItem | null;
  rightHand: EquipItem | null;
  acc1: EquipItem | null;
  acc2: EquipItem | null;
};

export type Hero = {
  // ...existing fields...
  equipment: Equipment;          // NEW
  inventory: InventoryItem[];    // `eq` removed from items
  // ...existing fields...
};
```

Rationale for a separate `EquipItem` type (rather than reusing `InventoryItem`):

- `q` (quantity) has no meaning per slot — each slot holds exactly one item or nothing.
- `eq` becomes redundant — occupancy of a slot *is* the "equipped" state.
- Keeping the types distinct leaves headroom for future slot-only fields (enchant, bonus) without polluting `InventoryItem`.

Short field names within items (`n`, `q`) follow the existing convention (`n`/`q`/`eq`, `t`/`m`). Slot keys on `Equipment` are full English words because that convention applies to item-level fields only — `Hero` itself already uses `race`, `class`, `level`, `inventory`, etc.

## Mock data migration (`front/services/mock.ts`)

`INITIAL_HERO` today has six `inventory` entries, three with `eq: true`. After the split:

```ts
equipment: {
  head: null,
  top: { n: '가죽 갑옷' },
  bottom: null,
  feet: null,
  leftHand: { n: '강철 단검' },
  rightHand: { n: '엘븐 롱보우 +1' },
  acc1: null,
  acc2: null,
},
inventory: [
  { n: '치유 물약', q: 3 },
  { n: '은화', q: 47 },
  { n: '알 수 없는 편지', q: 1 },
],
```

Slot assignment is a mechanical mapping of the current `eq: true` items to the most natural slot; there is no item-to-slot metadata anywhere else to consult.

## UI changes (`front/components/hero/HeroDetail.tsx`)

Current lines 7–8:

```ts
const equipped = (hero.inventory || []).filter(it => it.eq);
const carried  = (hero.inventory || []).filter(it => !it.eq);
```

After:

```ts
const equipped = [
  hero.equipment.head,
  hero.equipment.top,
  hero.equipment.bottom,
  hero.equipment.feet,
  hero.equipment.leftHand,
  hero.equipment.rightHand,
  hero.equipment.acc1,
  hero.equipment.acc2,
].filter((it): it is EquipItem => it !== null);

const carried = hero.inventory;
```

The render of the `장비` and `소지` rows stays visually identical — a flat ` · `-joined list, with the row omitted when empty. The iteration order above defines display order (head → top → bottom → feet → leftHand → rightHand → acc1 → acc2).

Known limitation (deferred): when the equipped list is long, the flat row will overflow its container. A dedicated slot-aware layout is out of scope for this change and will be addressed in a future task.

## Impact surface

Files that must change:

- `front/types/game.ts` — add `EquipItem`, `Equipment`; remove `eq` from `InventoryItem`; add `equipment` to `Hero`.
- `front/services/mock.ts` — update `INITIAL_HERO` per the migration above.
- `front/components/hero/HeroDetail.tsx` — switch to `hero.equipment` for the `장비` row.

No other consumers of `InventoryItem.eq` or `Hero.inventory` exist today (verified by repo-wide grep in the brainstorming step). No hooks, services, or log/panel code reads the equipped flag.

## Verification

- TypeScript compiles cleanly under `strict` (implicit via Metro / editor; no separate type-check script).
- `npm run lint` passes.
- `npx expo start` + web/iOS: the hero panel renders the same `장비` row content as before the change, and the `소지` row shows the three carried items.

## Open questions

None remaining — the slot set, type shape, mock migration, and UI behavior are all decided.
