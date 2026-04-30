# CLAUDE.md

Reference for Claude Code when working under `client/`. User-facing setup and tests live in [README.md](./README.md); the server boundary contract is in `../docs/04-boundary.md`.

## Layout

`client/` is the Expo app. The server is a peer directory (`../server/`). Run all client commands from here.

## Commands

See [README.md](./README.md) for the full table. Notes:

- After editing `tailwind.config.js`, `babel.config.js`, `metro.config.js`, or `design/tokens.js`, restart Metro with `-c`.
- No test runner. Type-check via `node_modules/.bin/tsc --noEmit`, or implicitly through the editor / Metro (`strict` TS, extends `expo/tsconfig.base`).
- Prefer `--host=tunnel` over `--tunnel` (`@expo/ngrok@4.x` bug).

## Stack constraints

- **Expo SDK 54 / RN 0.81 / React 19**, with `newArchEnabled` + `experiments.reactCompiler` in `app.json` — manual memoization is usually unnecessary. Class components and legacy native modules must work under New Arch.
- **expo-router** with `typedRoutes`. Add a screen by creating a file under `app/`; don't wire navigation manually.
- **NativeWind v4**: `className="bg-canvas-subtle p-3 rounded-md"`, not StyleSheet objects. The `@tailwind` directive is in `global.css`, imported from `app/_layout.tsx`.
- Path alias `@/*` → this directory. Prefer `@/components/...` over relative paths.
- **Server communication uses expo/fetch.** Standard `fetch` doesn't support SSE body streaming on RN.

## Architecture

Single-screen Korean-language TRPG. The tab bar is hidden, and `app/(tabs)/index.tsx` mounts `<Shell />`. All UX lives under `components/Shell.tsx`.

**Layers (top → bottom):**

1. `app/` — route shell. `_layout.tsx` loads Google Fonts (Noto Serif KR for all Korean prose / labels / titles, Geist Mono for ASCII numerics and stat keys) and gates rendering until they're ready. `(tabs)/index.tsx` mounts `<Shell />`.
2. `components/Shell.tsx` — composition root. Branches on `useGame()`'s `status` between `loading / no-game / error / ready`. The game screen is delegated to `Playing`.
3. `components/Playing.tsx` — the game screen, mounted when `status === 'ready'`. Owns local UI state (`activeId / heroOpen / typing`); panels are composed via `buildPanelSlots(...)`.
4. `components/new-game/` — exposed when `status === 'no-game'`. `NewGame.tsx` calls `GET /profiles`, renders scenario/race cards plus name/appearance inputs, and calls `useGame().startNewGame(body)`. Internal helpers (`Section`, `SelectCard`, `Input`, `CenterMessage`) live in the same folder.
5. `components/{header,log,hero,composer,combat,ui}/` — feature folders, each with an `index.ts` barrel. Import the folder, not individual files. `ui/` holds shared primitives (`Bar`, `Row`, `StatRow`, `InlineParts`, `InlineNodes`, `LabeledRow`, `ExpandGroup`).
6. `hooks/useGame.ts` — single source of truth for game state and actions (`onSend / onRoll / onStop / startNewGame / refresh`). On mount, `getCurrentSession()` auto-restores the last game; on unmount, all abort controllers are cancelled together. The SSE-event-to-state-setter mapping is handled by the pure dispatcher in `hooks/handleStreamEvent.ts`.
7. `services/` — **data boundary**. `services/index.ts` re-exports from `services/api.ts`. The surface is `listProfiles / getSessionById / initSession / streamTurn / streamRoll / streamIntro` plus the localStorage helpers `loadStoredGameId / storeGameId / clearStoredGameId`. The active `game_id` is persisted client-side so two browsers don't fight over the server's global `.current` pointer. The server base URL and basic auth live here only — no other layer calls `fetch` directly.
8. `presenters/` — **domain → UI presenter**. `panels.ts` converts `domain` types (`Subject / Quest / Place`) into the `PanelSlot` render contract (`buildPanelSlots`). `format.ts` holds shared display helpers (`joinOrDash`, `joinInventoryOrDash`, `formatInventoryItem`). Pure mapping — no state, no IO.
9. `types/` — `domain.ts` (server game models: `Hero`, `Subject`, `Quest`, `Place`, `Stats`, `RollResult`, `FrontState`), `ui.ts` (client render contracts: `LogEntry`, `Panel`, `PanelSlot`, `Tone`, ...), `wire.ts` (server wire formats: `ProfileCard`, `RaceCard`, `InitRequest`, `SessionPayload`, `TurnRequest`, `PendingCheck`, `JudgeAction`, `StreamEvent`). The SSE `log_entry` payload reuses `ui.LogEntry` directly. `LogEntry` is a `kind: 'gm' | 'player' | 'act' | 'roll'` discriminated union — when extending the union, add the case to `components/log/LogItem.tsx`.
10. `design/tokens.js` (+ `tokens.d.ts`) — **single source of truth for design tokens**: `colors`, `spacing`, `radius`, `fontFamily`, `fontSize`, `toneColor`. Both `tailwind.config.js` (className utilities) and TS code that needs raw values consume it. **Don't hardcode colors or spacing in components** — use a className or import from `@/design/tokens`. It's CJS (`.js`) because the Tailwind config runs in Node; types live in the `.d.ts` sibling.

## Conventions

- Client types only carry fields the UI renders. Server-only fields are added during server work.
- UI structure is fixed. When data shape varies, move it to a different panel slot — don't branch the structure inside one slot.
- UI consistency fixes are holistic — don't patch only the flagged instance; unify the whole atom under one rule.
- env vars are fail-fast. `services/api.ts` throws at import time when `EXPO_PUBLIC_API_URL` / `EXPO_PUBLIC_API_USER` / `EXPO_PUBLIC_API_PASS` are missing.
- Korean only. The server builds every display string in Korean (dates, durations, composed strings included). The client renders verbatim.
