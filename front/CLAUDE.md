# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
npm install            # install dependencies
npx expo start         # start Metro (pick platform from the prompt)
npm run ios            # open iOS simulator
npm run android        # open Android emulator
npm run web            # open web build
npm run lint           # expo lint (ESLint flat config via eslint-config-expo)
```

No test runner is configured. Type-check is implicit via the editor / Metro — TypeScript is `strict` and extends `expo/tsconfig.base`.

## Stack constraints worth knowing

- **Expo SDK 54**, RN 0.81, React 19. `newArchEnabled: true` and `experiments.reactCompiler: true` in `app.json` — hand-written memoization is usually unnecessary, and any class component / legacy native module must work under the New Architecture.
- **expo-router** with file-based routing and `typedRoutes: true`. Add a screen by creating a file under `app/`; do not wire navigation manually.
- Path alias `@/*` → project root (see `tsconfig.json`). Prefer `@/components/...` over relative paths.

## Architecture

The app is a single-screen Korean-language TRPG prototype. The tab bar is hidden (`app/(tabs)/_layout.tsx`) and `app/(tabs)/index.tsx` just mounts `<Shell />` inside a `SafeAreaView` + `KeyboardAvoidingView`. All UX lives below `components/Shell.tsx`.

**Layering (top → bottom):**

1. `app/` — route shells only. `_layout.tsx` loads Google Fonts (Inter / Source Serif 4 / Geist Mono) and gates rendering on their readiness.
2. `components/Shell.tsx` — composition root. Pulls game state from `useGame()` and panel definitions from `usePanels()`, and owns three pieces of local UI state: `activeId` (which context chip is open), `heroOpen`, and `typing` (keyboard-focused composer auto-collapses the active panel).
3. `components/{header,log,hero,composer,atoms}/` — feature folders. Each exposes a barrel `index.ts`; import the folder, not individual files (`import { Log } from './log'`). `atoms/` holds shared primitives (`Bar`, `StatRow`, `InlineNodes`, `LabeledRow`).
4. `hooks/` — stateful orchestration. `use-game.ts` owns the `log` array + roll lifecycle and is the single source of truth for `onSend` / `onRoll`. `use-panels.ts` is a pure derivation that turns domain objects into `PanelSlot[]` via builder functions from `services/`.
5. `services/` — **data boundary**. `services/index.ts` re-exports from `./mock`; the comment `Swap mock ↔ api implementation here.` is load-bearing. When a real backend is introduced, swap it at this barrel, not inside hooks. `mock.ts` also contains the `build*Slot` panel-shape builders (they depend on `Theme` so they belong with the mock data, not in hooks).
6. `types/game.ts` — canonical domain model. `LogEntry` is a discriminated union over `kind: 'gm' | 'player' | 'act' | 'roll'` and drives rendering in `components/log/LogItem.tsx`. Add a new log variant by extending this union + adding a case there.
7. `constants/theme.ts` — the only source of colors, spacing (`Theme.space.xs..xl`), radii, and type scale (`TYPE` + `typeStyle()` helper). **Never hard-code colors or spacing in components** — reach into `Theme`.

**Data flow:** `useGame` pushes `LogEntry`s through four `push*` helpers that share a monotonic `nextId` ref. `onSend` appends the player line, then schedules a fake GM reply on `setTimeout`, and with 50% probability follows up with an `act` entry that re-enables rolling. `onRoll` is a short state machine: `rolling=true → setTimeout 900ms → pushRoll → pushGM` follow-up. If you wire a real backend, keep this shape (optimistic player push, async GM/roll results) so the UI timing stays unchanged.

**Theming note:** three font families are always loaded at root and referenced via `Theme.fonts.*`. Mono is used for numeric/stat displays (see `HeroPill` — `fontVariant: ['tabular-nums']`), serif is reserved for narrative GM text, sans is the default UI font.
