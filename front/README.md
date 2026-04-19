# trpg-front

Korean-language TRPG prototype — single-screen Expo (React Native) app.

## Stack

- Expo SDK 54 / React Native 0.81 / React 19 (New Architecture + React Compiler)
- expo-router (file-based routing, `typedRoutes`)
- NativeWind v4 (Tailwind for RN) with `design/tokens.js` as the single token source
- TypeScript strict

## Run

```bash
npm install
npx expo start                          # start Metro, pick a platform
npx expo start -c                       # clear cache (after editing tokens / tailwind / babel / metro config)
npx expo start --clear --host=tunnel    # phone testing via ngrok tunnel (WSL2 path; requires ngrok authtoken)
npm run ios                             # iOS simulator
npm run android                         # Android emulator
npm run web                             # web
npm run lint
```

## Structure

See [CLAUDE.md](./CLAUDE.md) for layering, data boundary, and coding conventions.
