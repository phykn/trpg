# Client Agent Guide

Read [README.md](README.md) for the screen/state flow and commands. Stack: Expo SDK 54, React Native 0.81, React 19, Expo Router, NativeWind v4, strict TypeScript. `@/*` resolves to `client/`.

## Responsibilities

- `app/`: route entry and font/theme setup.
- `screens/`: screen composition.
- `components/game/`: game visuals; `components/ui/`: reusable controls.
- `logic/useGame.ts`: server state, command lifecycle and recovery.
- `services/api.ts`: the only `expo/fetch` import and HTTP boundary.
- `services/storage.ts`: browser save pointer; `services/types.ts`: public wire types.
- `locale/ko.ts`: client-owned Korean; `design/tokens.js` and `.d.ts`: shared design tokens.

Use direct imports and keep the normal play path visible. Do not add forwarding barrels or client copies of server rules. Server strings render verbatim. Use `당신`, polite `합니다체`, and `기술` in local prose. English category markers may use the mono typeface.

## UI and state

Use NativeWind classes and shared tokens for color, spacing and typography. Keep the mobile frame at viewport height with no scrolling or scene illustrations; desktop uses the same narrow frame. Use Reader and PagedList for long content, and show full action details before committing. Reading, paging and opening notes must never send a game command. Add required spacing tokens before using new width utilities. Clear Metro with `npm run web -- --clear` after token, Tailwind, Babel or Metro changes.

Only `trpg.adventure_game_id` is stored in the browser. A missing response freezes further choices until the identical command is retried or a fresh server snapshot is accepted. Do not clear the saved pointer on a failed restore. Keep immediate request guards as well as rendered disabled states.

## Verify

Run relevant Jest tests plus `npx tsc --noEmit` and `npm run lint`. Build with `npm run build:web` after routing/config changes. Inspect actual 320×568, 412×915 and desktop-width screens for overflow, readable text, complete pagination, touch targets and keyboard focus. Dialogs must close with Escape, contain focus, and return it to the opener. Use the root QA recording convention.
