# Combat Action Buttons Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Show simple combat controls while combat is active: `공격`, `방어`, and `도망`.

**Architecture:** Keep combat action construction in `logic/combat/actions.ts`. `CombatStrip` renders the resulting `PanelAction[]` and `Playing` sends them through the existing `runAction` path, so graph mode uses direct graph actions and legacy mode can still use Korean text fallbacks.

**Tech Stack:** Expo React Native, Jest, TypeScript.

---

### Task 1: Combat Action Builder

**Files:**
- Create: `client/logic/combat/actions.ts`
- Create: `client/logic/combat/__tests__/actions.test.ts`
- Modify: `client/logic/combat/types.ts`
- Modify: `client/logic/combat/index.ts`
- Modify: `client/locale/ko.ts`

- [x] **Step 1: Write the failing test**

Add a test that builds actions from one live enemy with `id: "enemy_01"` and asserts:

```ts
expect(actions).toEqual([
  expect.objectContaining({
    kind: 'graph_action',
    label: '공격',
    graphAction: { verb: 'attack', what: 'enemy_01' },
    textFallback: '늑대를 공격합니다',
  }),
  expect.objectContaining({
    kind: 'graph_action',
    label: '방어',
    graphAction: { verb: 'pass' },
    textFallback: '방어합니다',
  }),
  expect.objectContaining({
    kind: 'graph_action',
    label: '도망',
    graphAction: { verb: 'move', how: 'flee' },
    textFallback: '도망칩니다',
  }),
]);
```

- [x] **Step 2: Verify RED**

```powershell
npm test -- actions.test.ts --runInBand
```

- [x] **Step 3: Implement the action builder**

Define `CombatEnemy` as the generated enemy payload plus optional `id`. Define `CombatBadge` as the generated badge with that enemy type. `buildCombatActions(combat)` picks the first alive enemy and returns attack/defend/flee actions.

- [x] **Step 4: Verify GREEN**

```powershell
npm test -- actions.test.ts --runInBand
```

### Task 2: Wire Buttons Into CombatStrip

**Files:**
- Modify: `client/components/combat/CombatStrip.tsx`
- Modify: `client/screens/play/Playing.tsx`
- Modify: `client/services/graphAdapter.ts`
- Modify: `client/services/__tests__/graphAdapter.test.ts`

- [x] **Step 1: Preserve graph enemy id**

Add `id: enemy.id` to `adaptCombat` so combat buttons can attack by grounded graph id.

- [x] **Step 2: Render action buttons**

Add `onAction` and `actionDisabled` props to `CombatStrip`. Render action buttons only when `buildCombatActions(combat)` returns actions.

- [x] **Step 3: Run focused verification**

```powershell
npm test -- actions.test.ts graphAdapter.test.ts --runInBand
npx tsc --noEmit
```

- [x] **Step 4: Run client regression**

```powershell
npm test -- --runInBand
npm run lint
```

- [x] **Step 5: Commit and push**

```powershell
git add docs\superpowers\plans\2026-05-10-combat-action-buttons.md client\logic\combat client\components\combat\CombatStrip.tsx client\screens\play\Playing.tsx client\services\graphAdapter.ts client\services\__tests__\graphAdapter.test.ts client\locale\ko.ts
git commit -m "feat: add combat action buttons"
git push
```
