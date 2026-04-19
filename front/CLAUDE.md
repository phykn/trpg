# CLAUDE.md

Guidance for Claude Code working in this repo.

## Layout

`front/` is the Expo app; the repo root holds only docs/meta. There is no backend yet — the data boundary is `services/`. Run all commands from this directory.

## Commands

See [README.md](./README.md) for the full list. Notes:

- Restart Metro with `-c` after editing `tailwind.config.js`, `babel.config.js`, `metro.config.js`, or `design/tokens.js`.
- No test runner. Type-check is implicit via the editor / Metro (`strict` TS, extends `expo/tsconfig.base`).
- Prefer `--host=tunnel` over `--tunnel` (the latter hits an `@expo/ngrok@4.x` bug).

## Stack constraints

- **Expo SDK 54 / RN 0.81 / React 19**, `newArchEnabled` + `experiments.reactCompiler` in `app.json` — hand-written memoization is usually unnecessary; class components / legacy native modules must work under New Arch.
- **expo-router** with `typedRoutes`. Add a screen by creating a file under `app/`; do not wire navigation manually.
- **NativeWind v4**: write `className="bg-canvas-subtle p-3 rounded-md"`, not StyleSheet objects. `@tailwind` directives live in `global.css`, imported at `app/_layout.tsx`.
- Path alias `@/*` → this directory. Prefer `@/components/...` over relative paths.

## Architecture

Single-screen Korean TRPG prototype. Tab bar is hidden; `app/(tabs)/index.tsx` mounts `<Shell />`. All UX lives below `components/Shell.tsx`.

**Layers (top → bottom):**

1. `app/` — route shells. `_layout.tsx` loads Google Fonts (Inter / Source Serif 4 / Geist Mono) and gates rendering on readiness.
2. `components/Shell.tsx` — composition root. Owns `activeId`, `heroOpen`, `typing` local UI state; pulls game state from `useGame()` and builds panels via `buildPanelSlots(...)`.
3. `components/{header,log,hero,composer,ui}/` — feature folders, each with a barrel `index.ts`. Import the folder, not individual files. `ui/` holds shared primitives.
4. `hooks/use-game.ts` — single source of truth for `log` + `onSend` / `onRoll`. Async work goes through a `schedule()` helper that clears all timers on unmount.
5. `services/` — **data boundary**. `services/index.ts` re-exports `rules` (game mechanics: `rollD20`, `resolveCheck`, `Check`) and `panels` (domain → `PanelSlot` builders, including `buildPanelSlots`). This barrel is the swap point for a real backend.
6. `debug/` — **mock fixtures only**. Seed data (`INITIAL_*`), placeholder narrative (`fakeGMReply`, `checkPrompt`, `rollFollowup`), and the stand-in `PENDING_CHECK`. Consumed by `useGame()` to drive the prototype. Delete this folder when wiring a real backend.
7. `types/` — `domain.ts` (game model from backend: `Hero`, `Subject`, `Quest`, `Place`, `Stats`, `RollResult`, ...), `ui.ts` (frontend rendering contracts: `LogEntry`, `Panel`, `PanelSlot`, `Tone`, ...), and `wire.ts` (backend wire formats: `ChatRequest`, `ChatChunk`, ...). `LogEntry` is a discriminated union over `kind: 'gm' | 'player' | 'act' | 'roll'` — extend the union and add a case in `components/log/LogItem.tsx`.
8. `design/tokens.js` (+ `tokens.d.ts`) — **single source of truth for design tokens**: `colors`, `spacing`, `radius`, `fontFamily`, `fontSize`, `toneColor`. Consumed by `tailwind.config.js` (className utilities) and TS code that needs raw values. **Never hard-code colors or spacing in components** — use className or import from `@/design/tokens`. CJS (`.js`) because Tailwind config runs in Node; types come from the `.d.ts` sibling.

## Conventions

- Frontend types include only fields the UI renders. Backend-only fields are added when the backend lands.
- The UI structure is fixed; data variations belong in different panel slots, not conditional rendering inside one slot.
- UI consistency fixes are holistic — unify the whole atom under one rule rather than patching the reported instance.
