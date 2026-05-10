# Target Node Actions Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let a visible target node expose both `공격` and `접근` actions so combat can start from UI without losing the narrative approach option.

**Architecture:** Keep `PanelAction` unchanged. Replace the story-graph node helper with an array-returning helper, then let map panels render every returned action. Graph mode uses the explicit attack action; legacy mode keeps the Korean text fallback.

**Tech Stack:** Expo React Native, Jest, TypeScript.

---

### Task 1: Node Action Helper

**Files:**
- Modify: `client/logic/story-graph/_nodeActions.ts`
- Modify: `client/logic/story-graph/__tests__/_nodeActions.test.ts`

- [x] **Step 1: Write the failing test**

Change the reachable target test to expect two actions:

```ts
const actions = actionsForNode(target);
expect(actions).toEqual([
  expect.objectContaining({
    kind: 'graph_action',
    label: '공격',
    graphAction: { verb: 'attack', what: 'wolf_01' },
    textFallback: '늑대를 공격합니다',
  }),
  expect.objectContaining({
    kind: 'text',
    label: '접근',
    text: '늑대에게 접근합니다',
  }),
]);
```

- [x] **Step 2: Verify RED**

Run:

```powershell
npm test -- _nodeActions.test.ts --runInBand
```

Expected: FAIL because `actionsForNode` does not exist.

- [x] **Step 3: Implement helper**

Add `actionsForNode(node): PanelAction[]`. Keep `actionForNode(node)` as a compatibility wrapper returning the first action or `null` until all callers move.

- [x] **Step 4: Verify GREEN**

Run:

```powershell
npm test -- _nodeActions.test.ts --runInBand
```

Expected: PASS.

### Task 2: Render Multiple Actions

**Files:**
- Modify: `client/components/story-graph/MapPanel.tsx`
- Modify: `client/components/story-graph/NeighborhoodPanel.tsx`

- [x] **Step 1: Replace single selected action**

Use `actionsForNode(selectedNode)` and render one button per action in the selected-node header.

- [x] **Step 2: Run focused tests and typecheck**

```powershell
npm test -- _nodeActions.test.ts --runInBand
npx tsc --noEmit
```

- [x] **Step 3: Run client regression**

```powershell
npm test -- --runInBand
npm run lint
```

- [x] **Step 4: Commit and push**

```powershell
git add docs\superpowers\plans\2026-05-10-target-node-actions.md client\logic\story-graph\_nodeActions.ts client\logic\story-graph\__tests__\_nodeActions.test.ts client\components\story-graph\MapPanel.tsx client\components\story-graph\NeighborhoodPanel.tsx client\locale\ko.ts
git commit -m "feat: expose attack and approach node actions"
git push
```
