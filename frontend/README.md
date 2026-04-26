# trpg-frontend

Client for a Korean-language TRPG. Single-screen Expo (React Native) app. The backend lives at `../backend/`; the Claude Code guide is in [CLAUDE.md](./CLAUDE.md).

## Stack

- Expo SDK 54 / React Native 0.81 / React 19 (New Architecture + React Compiler)
- expo-router (file-based routing, `typedRoutes`)
- NativeWind v4 (Tailwind for RN), with `design/tokens.js` as the single token source
- TypeScript strict
- Backend calls: `expo/fetch` for SSE streaming (`services/llm.ts`)

## Setup

```bash
npm install
```

Write `frontend/.env`:

```
EXPO_PUBLIC_API_URL=<backend URL>
EXPO_PUBLIC_API_USER=<basic auth user>
EXPO_PUBLIC_API_PASS=<basic auth pass>
```

`<backend URL>` is either a LAN address (`http://<windows-lan-ip>:8001`) or a Tailscale Funnel domain (`https://<machine>.<tailnet>.ts.net`), depending on the test mode below.

## Phone testing

Install **Expo Go** on the phone (Play Store / App Store).

### LAN (same Wi-Fi)

1. Backend bound to `0.0.0.0:8001`, with the Windows firewall allowing 8001 inbound.
2. Phone on the same Wi-Fi as the laptop.
3. From `frontend/`:
   ```bash
   npx expo start
   ```
4. Android: Expo Go → "Scan QR code". iOS: scan the QR with the Camera app, then tap the "Open in Expo Go" notification.

### Off-LAN (Tailscale Funnel)

1. Backend bound to `127.0.0.1:8001`.
2. Confirm the funnel is proxying 8001:
   ```bash
   tailscale funnel status
   ```
   If it's off:
   ```bash
   sudo tailscale funnel --bg 8001
   ```
3. Make sure `EXPO_PUBLIC_API_URL` matches the funnel domain.
4. From `frontend/`:
   ```bash
   npx expo start --host=tunnel -c
   ```
5. Scan the QR with Expo Go (same as step 4 of the LAN flow).

## Other commands

```bash
npx expo start -c   # clear Metro cache (after editing tokens / tailwind / babel / metro config)
npm run lint
```

## Layout

```
frontend/
  app/                # expo-router route shell (single screen — index.tsx mounts Shell)
  components/         # screen pieces (header / log / hero / composer / ui + Shell + NewGame)
  hooks/use-game.ts   # game-state hook (server calls + applying SSE events)
  services/           # backend boundary (llm.ts: REST + SSE client)
  transformers/       # domain → UI projection (panels.ts)
  types/              # domain (backend models), ui (render contracts), wire (SSE/REST payloads)
  design/tokens.js    # single design tokens source (imported by both Tailwind config and code)
```
