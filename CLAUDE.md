# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repo layout

This is a monorepo-style layout with a single Expo app under `front/`. There is no backend in-tree yet — the data boundary lives in `front/services/` (see Architecture). All commands below are run from `front/`.

## Commands

```bash
cd front
npm install            # install dependencies
npx expo start         # start Metro (pick platform from the prompt)
npx expo start --clear # also: -c. Clear Metro cache — required after editing tailwind.config.js, babel.config.js, metro.config.js, or design/tokens.js. Combine with other flags freely, e.g. --tunnel --clear.
npm run ios            # open iOS simulator
npm run android        # open Android emulator
npm run web            # open web build
npm run lint           # expo lint (ESLint flat config via eslint-config-expo)
```

No test runner is configured. Type-check is implicit via the editor / Metro — TypeScript is `strict` and extends `expo/tsconfig.base`.

## Stack constraints worth knowing

- **Expo SDK 54**, RN 0.81, React 19. `newArchEnabled: true` and `experiments.reactCompiler: true` in `front/app.json` — hand-written memoization is usually unnecessary, and any class component / legacy native module must work under the New Architecture.
- **expo-router** with file-based routing and `typedRoutes: true`. Add a screen by creating a file under `front/app/`; do not wire navigation manually.
- **NativeWind v4** (Tailwind for React Native) is the styling layer. Write `className="bg-canvas-subtle p-3 rounded-md"`, not StyleSheet objects. The `@tailwind` directives live in `front/global.css`; root layout imports it at `front/app/_layout.tsx`. After editing `tailwind.config.js`, `babel.config.js`, `metro.config.js`, or `design/tokens.js`, restart Metro with `-c`.
- Path alias `@/*` → `front/` (see `front/tsconfig.json`). Prefer `@/components/...` over relative paths.

## Architecture

The app is a single-screen Korean-language TRPG prototype. The tab bar is hidden (`front/app/(tabs)/_layout.tsx`) and `front/app/(tabs)/index.tsx` just mounts `<Shell />` inside a `SafeAreaView` + `KeyboardAvoidingView`. All UX lives below `front/components/Shell.tsx`.

All paths below are relative to `front/`.

**Layering (top → bottom):**

1. `app/` — route shells only. `_layout.tsx` loads Google Fonts (Inter / Source Serif 4 / Geist Mono) and gates rendering on their readiness.
2. `components/Shell.tsx` — composition root. Pulls game state from `useGame()` and panel definitions from `usePanels()`, and owns three pieces of local UI state: `activeId` (which context chip is open), `heroOpen`, and `typing` (keyboard-focused composer auto-collapses the active panel).
3. `components/{header,log,hero,composer,ui}/` — feature folders. Each exposes a barrel `index.ts`; import the folder, not individual files (`import { Log } from './log'`). `ui/` holds shared primitives (`Bar`, `Row`, `StatRow`, `InlineNodes`, `InlineParts`, `LabeledRow`, `ExpandGroup`).
4. `hooks/` — stateful orchestration. `use-game.ts` owns the `log` array + roll lifecycle and is the single source of truth for `onSend` / `onRoll`. Panel slots are built inline in `Shell.tsx` via `buildPanelSlots(state)` — no hook wrapper.
5. `services/` — **data boundary**. `services/index.ts` re-exports the four modules below; the barrel is the swap point when a real backend is introduced. Split by concern:
   - `data.ts` — seed domain data (`INITIAL_HERO`, `INITIAL_SUBJECT`, `INITIAL_QUEST`, `INITIAL_PLACE`, `INITIAL_LOG`).
   - `rules.ts` — pure game mechanics (`rollD20`, `resolveCheck`, `PENDING_CHECK`).
   - `content.ts` — narrative strings (`fakeGMReply`, `checkPrompt`, `rollFollowup`).
   - `panels.ts` — `build*Slot` builders + `PANEL_FACTORIES` registry + `buildPanelSlots`. Builders emit semantic `tone` tokens (not raw theme colors) so UI remains the sole theme consumer. Add a new panel by appending a factory to `PANEL_FACTORIES`.
6. `types/` — canonical type model, split by consumer:
   - `types/domain.ts` — backend-facing shapes (`Hero`, `Subject`, `Quest`, `Place`, `Stats`, `LogEntry`, ...). `LogEntry` is a discriminated union over `kind: 'gm' | 'player' | 'act' | 'roll'` — extend the union and add a case in `components/log/LogItem.tsx`. Prefer concise field names (`InventoryItem.qty`, `Memo.tag`/`msg`) but never single letters; `Stats` keeps TRPG-standard `STR`/`DEX`/`CON`/`INT`/`WIS`/`CHA`.
   - `types/ui.ts` — frontend-only panel contracts (`BarDef`, `DisplayPart`, `PanelSection`, `Panel`, `PanelSlot`, `Tone`). `Tone` is the semantic color token; resolve via `toneColor()` in `constants/tone.ts`.
7. `design/tokens.js` (+ `tokens.d.ts`) — **single source of truth for design tokens**. Exports `colors`, `spacing`, `radius`, `fontFamily`, `fontSize`, and `toneColor` (semantic `Tone` → color map). Consumed by (a) `tailwind.config.js` for className utilities and (b) TS code that needs raw values (SVG stroke, animations). Naming follows GitHub Primer: `canvas.*` surfaces, `fg.*` foreground by emphasis, `border.*`, `accent.*`, semantic `danger`/`success`, and domain meters `hp`/`mp`/`exp`. **Never hard-code colors or spacing in components** — use className (`bg-canvas-subtle`) or import from `@/design/tokens` for dynamic values. Note: tokens are CJS (`.js`) because Tailwind config runs in Node; types come from the `.d.ts` sibling.

**Data flow:** `useGame` pushes `LogEntry`s through four `push*` helpers that share a monotonic `nextId` ref (seeded from `max(INITIAL_LOG.id) + 1`). Async work goes through the `schedule(fn, ms)` helper, which registers timers in a ref-held `Set` and clears them all on unmount. `onSend` appends the player line, then schedules a fake GM reply, and with 50% probability follows up with an `act` entry (via `checkPrompt`) that re-enables rolling. `onRoll` resolves through `rules.resolveCheck` and emits a `rollFollowup` narration from `content.ts`. If you wire a real backend, keep this shape (optimistic player push, async GM/roll results) so the UI timing stays unchanged.

**Theming note:** three font families are always loaded at root and referenced via `Theme.fonts.*`. Mono is used for numeric/stat displays (see `HeroPill` — `fontVariant: ['tabular-nums']`), serif is reserved for narrative GM text, sans is the default UI font.
