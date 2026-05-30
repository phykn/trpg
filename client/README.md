# trpg-client

Client for a locale-aware TRPG. Single-screen Expo (React Native) app. The server lives at `../server/`; the agent guide is in [AGENTS.md](./AGENTS.md).

## Stack

- Expo SDK 54 / React Native 0.81 / React 19 (New Architecture + React Compiler)
- expo-router (file-based routing, `typedRoutes`)
- NativeWind v4 (Tailwind for RN), with `design/tokens.js` as the single token source
- TypeScript strict
- Server calls: `expo/fetch` for graph REST (`services/api.ts`)

## Setup

```bash
npm install
```

Write `client/.env.shared` for common values:

```
EXPO_PUBLIC_API_USER=<basic auth user>
EXPO_PUBLIC_API_PASS=<basic auth pass>
```

Write `client/.env.dev` for the local server URL:

```
EXPO_PUBLIC_API_URL=<server URL>
```

`<server URL>` is either a LAN address (`http://<windows-lan-ip>:8001`) or a Tailscale Funnel domain (`https://<machine>.<tailnet>.ts.net`), depending on the test mode below.

`npm start`, `npm run web`, `npm run android`, and `npm run ios` load `client/.env.shared` then `client/.env.dev`. `npm run deploy` delegates to `../release/deploy.ps1 -ClientOnly`, which loads `client/.env.shared` then `client/.env.release`.

## Phone testing

Install **Expo Go** on the phone (Play Store / App Store).

### LAN (same Wi-Fi)

1. Server bound to `0.0.0.0:8001`, with the Windows firewall allowing 8001 inbound.
2. Phone on the same Wi-Fi as the laptop.
3. From `client/`:
   ```bash
   npm start
   ```
4. Android: Expo Go → "Scan QR code". iOS: scan the QR with the Camera app, then tap the "Open in Expo Go" notification.

### Off-LAN (Tailscale Funnel)

1. Server bound to `127.0.0.1:8001`.
2. Confirm the funnel is proxying 8001:
   ```bash
   tailscale funnel status
   ```
   If it's off:
   ```bash
   sudo tailscale funnel --bg 8001
   ```
3. Make sure `EXPO_PUBLIC_API_URL` matches the funnel domain.
4. From `client/`:
   ```bash
   npm start -- --host=tunnel -c
   ```
5. Scan the QR with Expo Go (same as step 4 of the LAN flow).

## Public web deploy

Static export to Cloudflare Workers (project: `trpg`). Anyone with the URL can open the app in a browser without running a dev server, provided `EXPO_PUBLIC_API_URL` points to the release API and the deploy URL is listed in server `CORS_ORIGINS`.

First time only:

```bash
npm install -g wrangler
wrangler login
```

Each deploy:

```bash
npm run deploy
```

This wipes `dist/`, runs `expo export -p web`, then `wrangler deploy` — chained so you can't ship a stale bundle by running export without deploy (or vice versa).

`EXPO_PUBLIC_API_USER` / `EXPO_PUBLIC_API_PASS` are baked into the static bundle and visible to anyone who opens devtools on the public site. Use demo credentials and rotate after the demo.

## Other commands

```bash
npm start -- -c   # clear Metro cache (after editing tokens / tailwind / babel / metro config)
npm run lint
```

## Troubleshooting

### `--host=tunnel` fails with `Cannot read properties of undefined (reading 'body')`

The bundled `@expo/ngrok` cache gets into a bad state intermittently. Wipe it and reinstall:

```bash
rm -rf ~/.expo node_modules/@expo/ngrok
npx expo install @expo/ngrok
npm start -- --host=tunnel -c
```

## Layout

```
client/
  app/         # expo-router routes (single screen — (tabs)/index.tsx mounts Shell)
  screens/     # screen composition: Shell, new-game/, play/
  components/  # domain views (hero, composer, log, combat, info-panel, story-graph) + ui/ primitives
  logic/       # domain calculation, state, hooks (game/useGame.ts is the state root)
  services/    # server boundary — api.ts (graph REST), wire.ts (types), storage.ts (localStorage)
  locale/      # client-owned locale labels (ko.ts today)
  design/      # design tokens (tokens.js) shared by Tailwind config and TS
  scripts/     # deploy helpers
```

Architecture rules (bucket boundaries, import conventions, layer responsibilities) live in [AGENTS.md](./AGENTS.md).
