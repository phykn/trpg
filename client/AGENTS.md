## AGENTS.md

This file provides guidance to Codex (Codex.ai/code) when working with code in this repository.

Reference for working under `client/`. End-user setup, phone testing, and deploy steps live in [README.md](./README.md).

## Commands

Run everything from `client/`. Development scripts load `.env.shared` then `.env.dev`; `npm run deploy` loads `.env.shared` then `.env.release`.

```bash
npm start                   # Expo Go via QR (LAN / Tailscale Funnel — see README)
npm run web                 # web on localhost:8081
npm run lint                # expo lint (eslint flat config, dist/ ignored)
npm run deploy              # load .env.release → expo export -p web → wrangler deploy
npx tsc --noEmit            # type-check (strict, extends expo/tsconfig.base)
npm start -- -c             # clear Metro cache — required after editing tokens / tailwind / babel / metro config
```

`@/*` resolves to this directory. Prefer `@/components/...` over relative paths.

## Stack constraints

- **Expo SDK 54 / RN 0.81 / React 19** with `newArchEnabled` and `experiments.reactCompiler` in `app.json` — manual memoization is usually unnecessary, and any class component or legacy native module must work under New Arch.
- **expo-router** with `typedRoutes`. Add a screen by creating a file under `app/`; don't wire navigation manually. The tab bar is hidden (`tabBarStyle: { display: 'none' }`); the app is single-screen.
- **NativeWind v4**: write `className="bg-canvas-subtle p-3 rounded-md"`, not `StyleSheet` objects. The `@tailwind` directives load via `global.css`, imported once at the top of `app/_layout.tsx`.
- **Server calls use `expo/fetch`**, not the global `fetch`. Keep all API calls inside `services/api/`; only `services/api/transport.ts` imports `expo/fetch`.
- **Locale-aware UI.** The server composes every game display string for the active locale, including dates, durations, joined lists, stat labels, confirmations, and log entries. The client renders server strings verbatim — do not translate or reformat them in `logic/<x>/panel.ts` or `components/<x>/`. Client-owned labels live in the client locale catalog; today `locale/ko.ts` is the Korean catalog, and new UI locales should add parallel locale modules instead of inline literals. Short uppercase English may be used as a visual atom in the GeistMono type system for form/category markers such as `NAME`, `GENDER`, `WORLD`, `RACE`, and `LANGUAGE`. Log entry types are distinguished visually (font size, accent border, mono box) — no inline text label.

## Architecture

Single-screen locale-aware TRPG. `app/(tabs)/index.tsx` mounts `<ScreenShell><Shell/></ScreenShell>`; everything else lives under `screens/`, `components/`, `logic/`, or `services/`.

**Layers, top → bottom:**

1. `app/` — expo-router route shell. `_layout.tsx` loads Noto Serif KR (CJK prose / labels / titles) + Geist Mono (ASCII numerics and stat keys), and returns `null` until both font families are ready.
2. `components/ui/ScreenShell.tsx` — `SafeAreaView` + keyboard-aware bottom padding. Wraps every screen.
3. `screens/Shell.tsx` — composition root. Branches on `useGame().status` between `loading / no-game / error / ready`. The `ready` branch delegates to `screens/play/Playing`; `no-game` mounts `screens/new-game/NewGame`.
4. `screens/play/Playing.tsx` — game screen. Owns ephemeral UI state (`activeId`, `nearbyOpen`, `pendingAction`, BGM toggle, input draft). Uses graph confirmation and pending-roll state to decide whether modal/panel input is blocked.
5. `screens/new-game/` — character creation screen.
6. `components/<name>/` — domain view files only. Currently: `Log`, `LogItem`, `RollResult`, `Composer`, `SendButton`, `StopButton`, `GameOverPanel`, `LevelUpPrompt`, `CombatStrip`, `ContextCard`, `IconButton`, `PanelBody`, `RollPanel`, `DecisionStateStrip`. Domains: `composer`, `log`, `combat`, `info-panel`, `roll`, `decision-state`. Import via `logic/<name>/` barrel — not directly. Screen-specific helpers (e.g. `screens/new-game/{Input,Section,SelectCard}.tsx`) live next to the screen, not here.
7. `logic/<name>/` — domain calculation, types, hooks. Each barrel (`logic/<name>/index.ts`) re-exports view components from `@/components/<name>/...` to preserve the external alias surface. Feature-internal helpers (e.g. `logic/story-graph/presenters.ts` for merge/fingerprint, `logic/story-graph/_nodeActions.ts` for intent builders) live here. Domains: `hero`, `subject`, `quest`, `info-panel`, `composer`, `log`, `combat`, `roll`, `decision-state`, `story-graph`, `audio`. View-less domains (`audio`, `subject`, `quest`) have no `components/<x>/` counterpart.
8. `components/ui/` — design-system primitives with no domain knowledge. `Surface` (paper/floating + optional stripeColor), `Chip` (tab/action), `Bar`, `Row`, `StatRow`, `InlineParts`, `InlineNodes`, `LabeledRow`, `Expandable`, `ExpandableTitle`, `ExpandGroup`, `ConfirmDialog`, `Glyph`, `CenterMessage`, `ErrorState`, `ScreenShell`, `useEntryAnimation`, `format` (joinOrDash, characterMeta, withDeath, signed, ...). Plus `types.ts` (`Tone`, `BarDef`, `PartsCell`, `ConfirmInfo`).
9. `logic/game/useGame.ts` — single source of truth for graph game state and actions (`onSend / onQuestAction / onGraphAction / onCombatCommand / onConfirmPending / onRollPending / startNewGame / goToNewGame / refresh`). On mount, restores the last graph game via the `trpg.current_game_id` localStorage key. Graph REST responses carry authoritative state; do not add a second transport path here.
10. `logic/story-graph/` — story graph types and current-snapshot presenters for the bottom nearby/task list. Do not add localStorage graph merging or map UI here unless the map feature is explicitly restored.
11. `services/` — data boundary. Graph play surface: `listProfiles / getGraphSessionById / initGraphSession / requestGraphIntro / sendGraphInput / sendGraphAction / sendGraphCombatCommand / confirmGraphAction / rollGraphPending / getGraphLevelUpOptions / sendGraphLevelUp`, plus story-dev helpers and storage helpers. `services/api/` owns API calls by responsibility (`transport`, `graph`, `storyDev`, `bootstrap`) while preserving the `@/services` export surface. `services/wire/` owns the client network contract (`FrontState`, graph payloads, `SessionPayload`, `InitRequest`, etc.). The server base URL and basic auth header live in `services/api/transport.ts` only; no other layer should call `fetch` directly. The active `game_id` lives in browser localStorage — the server has no "last game" notion, so two browsers don't fight over a shared pointer.
12. `locale/ko.ts` — Korean client-owned label catalog. Many groups (`action` / `form` / `ability` / `panel` / `legend` / `status` / `empty` / `level` / `quest` / `hero` / `subject` / `combat` / `menu` / `shell` / `newGame` / `confirm` / `error` / `roll` / `composer` / `gameOver`) plus a separate `compose` export with dynamic-assembly functions (e.g. `compose.moveTo(name)`, `compose.deceased(name)`). Server-composed strings render verbatim; locale files cover labels the client owns.
13. `design/tokens.js` (+ `tokens.d.ts`) — single source of truth for design tokens: `colors`, `spacing`, `radius`, `fontFamily`, `fontSize`, `toneColor`, `shadow`. Both `tailwind.config.js` (className utilities) and TS code consuming raw values import from here. The file is CJS (`.js`) because Tailwind config runs in Node; types live in the `.d.ts` sibling. **Don't hardcode colors or spacing** — use a className or import from `@/design/tokens`. Color naming follows GitHub Primer (`canvas`, `fg`, `border`, `accent`, ...).

## Folder rule (MECE)

Every file lives in exactly one bucket. Decision tree:

| Question | Goes to |
|---|---|
| expo-router route? | `app/` |
| Screen composition? | `screens/<name>/` |
| Touches fetch / storage / wire format? | `services/` |
| Design token? | `design/` |
| Client-side hardcoded label / storage key? | `locale/` |
| Domain visual part? | `components/<x>/` |
| Domain calculation / state / types? | `logic/<x>/` |
| Game state root or its input boundary? | `logic/game/useGame.ts` |
| Otherwise (no domain knowledge — visual / animation primitive) | `components/ui/` |

A file may not span two buckets. If you're unsure, the file probably wants splitting.

**Locality consequence:** adding a `Hero` field touches only `logic/hero/{types.ts, panel.ts}` plus the consuming screen/panel. Adding a log entry kind touches only `logic/log/` + `components/log/LogItem.tsx`. There is no cross-feature `presenters/` or `types/domain.ts` hub.

## Conventions

- Env vars fail fast. `services/api/transport.ts` throws at import time when `EXPO_PUBLIC_API_URL` / `EXPO_PUBLIC_API_USER` / `EXPO_PUBLIC_API_PASS` are missing.
- Client types carry only fields the UI renders. Server-only fields are added during server work, not anticipated here.
- UI structure is fixed. When data shape varies, move it to a different panel slot — don't branch structure inside one slot.
- **No hand-rolled `bg-canvas-subtle border ... rounded-md` stacks.** Use `<Surface>` (paper or floating, optional `stripeColor`). Use `<Chip>` for clickable pills. New visual atoms go in `components/ui/`.
- UI consistency fixes are holistic — don't patch only the flagged instance; change the atom.
- `pendingConfirmation` blocks input with `ConfirmDialog`; `pendingRoll` blocks input with `RollPanel`. Graph action requests must use `/graph/confirm` or `/graph/roll` to resolve those states.
- **Locale-aware display text.** Client-owned labels live in `locale/` (`ko.<group>.<key>` or `compose.<fn>(...)` for the current Korean catalog); never inline player-visible prose in a component, panel, or screen. Server-composed strings render verbatim. Form/category labels may be uppercase English visual atoms when they are part of the design system. Stat keys from server render as-is for the active locale. Log markers are visual-only.
- `LogEntry` is a `kind: 'gm' | 'player' | 'act' | 'roll'` discriminated union — when extending the union, add the case to `components/log/LogItem.tsx`.

## Misc

- For Playwright / browser-MCP runs, use viewport **412×915** (Pixel 6/7 / Galaxy S25 tall). It stays under the desktop breakpoint, keeps full tab labels visible, and fits typical session content without scrolling.
- Prefer `npm start -- --host=tunnel` over `--tunnel` (`@expo/ngrok@4.x` flag bug).
