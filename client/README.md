# Web client

A mobile web app where you read the scene and act in sentences on one fixed-height screen (Expo, React Native Web, NativeWind). It uses no illustrations, scrolls nothing outside the chat area, and keeps the same width (412px) on desktop. The screen design is in [docs/ui.md](../docs/ui.md); setup and play are in the [root README](../README.md).

## Screens and code

`app/index.tsx` → `screens/` → `logic/useGame.ts` → `services/api.ts`

- `screens/Title.tsx`: story shelf, continue, new game. `screens/Start.tsx`: name, stats, traits. `screens/Play.tsx`: the play screen layout.
- `components/ui/`: parts shared by every screen. `Icon` (line icons), `Button` and `IconButton`, `Sheet` (a bottom sheet and `Choice`), `motion.ts` (entrance motion), `useDialog` (Escape, focus trap and return).
- `components/game/`: icon rows (`Row`, `Item`, `Pill`), the header and hero panel, risk clocks, the scene, boxes, chat, the input line, the roll card and dice, clarify, confirm and growth cards, the menu, the ending.
- `logic/useGame.ts`: start, restore, the command lifecycle, the narration stream, failure recovery. It adopts only server responses as game state and never repeats the rules. `logic/reveal.ts` is a pure function that turns step records into a reveal schedule; `logic/useLog.ts` is the chat history kept on this device.
- `services/api.ts`: the only boundary for authenticated requests and the NDJSON narration stream. `types.ts` holds the response shapes; `storage.ts` stores the continue ID (`trpg.game_id`) and the chat history.
- `design/tokens.js`: colors, spacing, fonts, motion timings. `locale/ko.ts`: sentences the client composes. All story text comes from server responses.

Once a command is saved, the screen updates first and then receives that turn's narration as a stream. The next command stays locked until the narration finishes or fails. If there is no response within 30 seconds, only the same command (same `request_id`) can be sent again. The `view` in a 409 response is adopted as is.

## Commands

Run from `client/`.

```bash
npm run web              # connect to the local API (--local), localhost:8090
npm run web -- --clear   # clear the cache after token, Tailwind, Babel or Metro changes
npm run build:web        # web build against the local API → dist/ (after routing or config changes)
npm run dev              # web + API, reachable from a phone on the same network
npm run dev:public       # web + API + a public HTTPS address
npm test -- --runInBand  # single: npx jest path/to/file.test.ts
npx tsc --noEmit
npm run lint
node --test scripts/dev-proxy.test.cjs
```

## Public serving (workers.dev)

```bash
npm run deploy           # build the web client and deploy it to the Cloudflare Worker (trpg); serve also does this on client changes
npm run serve            # start the API and a tunnel on the Mac and write the tunnel URL to Worker KV; run each time you play
```

The Worker serves the static client and forwards `/api/*` to the current tunnel URL in KV. If the tunnel drops, `serve` opens a new one and rewrites KV. While it runs, `serve` keeps both sides current: when `.py` files in `server/` or `.yaml` files in `scenarios/` change, it restarts only the API, so the address keeps working; when client files change, it rebuilds and redeploys the web client (about a minute), and a page reload picks it up. KV updates take about a minute to take effect. The first time, run `npx wrangler login`; both models must be running. With `serve` stopped, the page still opens but the API returns 502.

`dev` forwards `/api` requests to the local API, so a phone also uses the same address for the web client and the API. It reuses an already-running local API. The `dev:public` address changes on every run; on Windows, a verified official `cloudflared` binary is kept in `node_modules/.cache/`.

## Connect to another server

The local web commands always use a fixed local configuration. To connect to another server, set three environment variables and run Expo directly. Also add the browser's address to the server's `CORS_ORIGINS`. Keep the port at 8090 (Expo's default 8081 is used by the decision model).

```bash
EXPO_NO_DOTENV=1 EXPO_PUBLIC_API_URL=http://127.0.0.1:8000 EXPO_PUBLIC_API_USER=local EXPO_PUBLIC_API_PASS=local npx expo start --web --host localhost --port 8090
```

These values are public connection settings, visible in the web bundle. Running `npx expo export --platform web` with the same settings produces a static build that connects to that server. `npm start`, `npm run android` and `npm run ios` are Expo development commands that read `.env.shared` and `.env.dev`; the web is what gets verified.
