## CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

Reference for working under `client/`. End-user setup, phone testing, and deploy steps live in [README.md](./README.md). The server boundary contract lives in `../docs/04-boundary.md`.

## Commands

Run everything from `client/`. The active environment file is `.env`; `npm run deploy` temporarily swaps in `.env.release` and restores `.env` on exit.

```bash
npm start                   # Expo Go via QR (LAN / Tailscale Funnel — see README)
npm run web                 # web on localhost:8081
npm run lint                # expo lint (eslint flat config, dist/ ignored)
npm run deploy              # rm dist/ → swap .env.release → expo export -p web → wrangler deploy
npx tsc --noEmit            # type-check (strict, extends expo/tsconfig.base)
npx expo start -c           # clear Metro cache — required after editing tokens / tailwind / babel / metro config
```

`@/*` resolves to this directory. Prefer `@/components/...` over relative paths.

## Stack constraints

- **Expo SDK 54 / RN 0.81 / React 19** with `newArchEnabled` and `experiments.reactCompiler` in `app.json` — manual memoization is usually unnecessary, and any class component or legacy native module must work under New Arch.
- **expo-router** with `typedRoutes`. Add a screen by creating a file under `app/`; don't wire navigation manually. The tab bar is hidden (`tabBarStyle: { display: 'none' }`); the app is single-screen.
- **NativeWind v4**: write `className="bg-canvas-subtle p-3 rounded-md"`, not `StyleSheet` objects. The `@tailwind` directives load via `global.css`, imported once at the top of `app/_layout.tsx`.
- **Server calls use `expo/fetch`**, not the global `fetch`. Standard `fetch` does not support SSE body streaming on RN.
- **Korean only.** The server composes every display string (including dates, durations, joined lists). The client renders verbatim — do not localize or reformat in `presenters/` or components.

## Architecture

Single-screen Korean-language TRPG. `app/(tabs)/index.tsx` mounts `<ScreenShell><Shell/></ScreenShell>`; everything below sits under `components/Shell.tsx`.

**Layers, top → bottom:**

1. `app/` — route shell. `_layout.tsx` loads Noto Serif KR (all Korean prose / labels / titles) + Geist Mono (ASCII numerics and stat keys), and returns `null` until both font families are ready.
2. `components/ScreenShell.tsx` — `SafeAreaView` + keyboard-aware bottom padding. Wraps every screen.
3. `components/Shell.tsx` — composition root. Branches on `useGame().status` between `loading / no-game / error / ready`. The `ready` branch delegates to `Playing`; `no-game` mounts `NewGame`.
4. `components/Playing.tsx` — game screen. Owns ephemeral UI state (`activeId`, `menuOpen`, `pendingAction`, BGM toggle, input draft). Reads `pending` to decide between `RollPrompt` and `Composer`.
5. `components/{header,log,hero,composer,combat,new-game,story-graph,ui}/` — feature folders. Each has an `index.ts` barrel; import the folder, not individual files. `ui/` is shared primitives (`Bar`, `Row`, `StatRow`, `InlineParts`, `InlineNodes`, `LabeledRow`, `ExpandGroup`, `ConfirmDialog`, `Glyph`, `CenterMessage`, `ErrorState`).
6. `hooks/useGame.ts` — single source of truth for game state and actions (`onSend / onRoll / onStop / startNewGame / goToNewGame / refresh`). On mount, restores the last game via the `trpg.current_game_id` localStorage key. All in-flight `AbortController`s are cancelled on unmount and on `onStop`. The SSE-event → state-setter dispatch is the pure function in `hooks/handleStreamEvent.ts`; `state` and `log_entry` events are authoritative for the UI, and `judge` / `combat_*` events are observability-only.
7. `hooks/useStoryGraph.ts` — per-`gameId` localStorage merge for the story graph (key prefix `trpg.story_graph.`). Newer server snapshots merge over the cached one rather than replace, so transient absences don't blank the map.
8. `services/` — **data boundary**. Surface: `listProfiles / getSessionById / initSession / streamTurn / streamRoll / streamIntro`, plus storage helpers (`loadStoredGameId / storeGameId / clearStoredGameId`, `getStorage`). The server base URL and basic auth header live here only; no other layer should call `fetch` directly. The active `game_id` lives in browser localStorage — the server has no "last game" notion, so two browsers don't fight over a shared pointer.
9. `presenters/` — **domain → UI projection**. `panels.ts` builds `PanelSlot[]` from `Hero / Subject / Quest`. `format.ts` holds string helpers (`joinOrDash`, `formatInventoryItem`, `characterMeta`, `DASH`). `storyGraph.ts` is the merge / fingerprint / validation core for the map. Pure mapping only — no state, no I/O.
10. `types/` — `domain.ts` (server game models the UI consumes), `ui.ts` (render contracts), `wire.ts` (REST + SSE payloads), `storyGraph.ts` (graph nodes/edges, discriminated by `kind`). The SSE `log_entry` payload reuses `ui.LogEntry` directly. `LogEntry` is a `kind: 'gm' | 'player' | 'act' | 'roll'` discriminated union — when extending the union, add the case to `components/log/LogItem.tsx`.
11. `design/tokens.js` (+ `tokens.d.ts`) — **single source of truth for design tokens**: `colors`, `spacing`, `radius`, `fontFamily`, `fontSize`, `toneColor`, `shadow`. Both `tailwind.config.js` (className utilities) and TS code consuming raw values import from here. The file is CJS (`.js`) because Tailwind config runs in Node; types live in the `.d.ts` sibling. **Don't hardcode colors or spacing** — use a className or import from `@/design/tokens`. Color naming follows GitHub Primer (`canvas`, `fg`, `border`, `accent`, ...).

## Conventions

- Env vars fail fast. `services/api.ts` throws at import time when `EXPO_PUBLIC_API_URL` / `EXPO_PUBLIC_API_USER` / `EXPO_PUBLIC_API_PASS` are missing.
- Client types carry only fields the UI renders. Server-only fields are added during server work, not anticipated here.
- UI structure is fixed. When data shape varies, move it to a different panel slot — don't branch structure inside one slot.
- UI consistency fixes are holistic — don't patch only the flagged instance; unify the whole atom under one rule.
- `pending` (`PendingCheck`) is the state that flips composer mode: when it's set, render `RollPrompt`; when clear, render `Composer`. The `roll` log entry clears it the moment the dice lands, before the GM narration finishes streaming.

## Misc

- For Playwright / browser-MCP runs, use viewport **412×915** (Pixel 6/7 / Galaxy S25 tall). It stays under the desktop breakpoint, keeps full Korean tab labels visible, and fits typical session content without scrolling.
- Prefer `npx expo start --host=tunnel` over `--tunnel` (`@expo/ngrok@4.x` flag bug).
