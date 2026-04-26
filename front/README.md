# trpg-front

Korean-language TRPG prototype — single-screen Expo (React Native) app.

## Stack

- Expo SDK 54 / React Native 0.81 / React 19 (New Architecture + React Compiler)
- expo-router (file-based routing, `typedRoutes`)
- NativeWind v4 (Tailwind for RN) with `design/tokens.js` as the single token source
- TypeScript strict

## Setup

```bash
npm install
```

Create `front/.env`:

```
EXPO_PUBLIC_API_URL=<backend URL>
EXPO_PUBLIC_API_USER=<basic auth user>
EXPO_PUBLIC_API_PASS=<basic auth pass>
```

`<backend URL>` is either the LAN address (`http://<windows-lan-ip>:8001`) or the Tailscale Funnel domain (`https://<machine>.<tailnet>.ts.net`), matching the testing mode below.

## Phone testing

Install **Expo Go** on the phone (Play Store / App Store).

### LAN (same Wi-Fi)

1. Backend running, bound to `0.0.0.0:8001`. Windows firewall allows 8001 inbound.
2. Phone joined the same Wi-Fi as the laptop.
3. From `front/`:
   ```bash
   npx expo start
   ```
4. Android: open Expo Go → "Scan QR code". iOS: open the camera app, tap the "Open in Expo Go" notification.

### External network (Tailscale Funnel)

1. Backend running on `127.0.0.1:8001`.
2. Funnel proxying 8001 — verify:
   ```bash
   tailscale funnel status
   ```
   If down, start it:
   ```bash
   sudo tailscale funnel --bg 8001
   ```
3. `EXPO_PUBLIC_API_URL` in `.env` matches the funnel domain.
4. From `front/`:
   ```bash
   npx expo start --host=tunnel -c
   ```
5. Scan the QR with Expo Go (same as LAN step 4).

## Other commands

```bash
npx expo start -c   # clear Metro cache (after editing tokens / tailwind / babel / metro config)
npm run lint
```
