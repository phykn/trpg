# Client

The mobile web client (Expo, React Native Web, NativeWind). Its screens, state machine and module map are in [docs/ui.md](../docs/ui.md); it talks to the server only through [docs/api.md](../docs/api.md).

## Commands

Run from `client/`.

```bash
npm run web              # against the local API (--local), on localhost:8090
npm run web -- --clear   # after token, Tailwind, Babel or Metro changes
npm run build:web        # static build against the local API → dist/ (after routing or config changes)
npm run dev              # web + API, reachable from a phone on the same network
npm run dev:public       # web + API + a temporary public HTTPS address
npm test -- --runInBand  # one file: npx jest path/to/file.test.ts
npx tsc --noEmit
npm run lint
node --test scripts/dev-proxy.test.cjs
```

The port is 8090 because the decision model uses 8081, Expo's default. `dev` and `dev:public` start the local API unless one is already running, and forward `/api` to it, so a phone uses one address for both. The `dev:public` address changes on every run; on Windows it keeps a verified `cloudflared` binary in `node_modules/.cache/`.

## Public serving (workers.dev)

A fixed public address, with the API and models on this Mac:

```bash
npm run deploy           # build the client and deploy it to the Cloudflare Worker `trpg`
npm run serve            # run the API and a quick tunnel, and write the tunnel URL to the Worker's KV
```

Deploy once; after that `serve` redeploys whenever client files change. When it is ready it prints the Worker's address, looked up from the Cloudflare account at run time. The Worker serves the static client and forwards `/api/*` to the tunnel URL in KV. While `serve` runs:

- A dropped tunnel is reopened and its new URL written to KV, which takes about a minute to take effect.
- A change to a `.py` file in `server/` or a `.yaml` file in `scenarios/` restarts only the API; the address keeps working. If the API fails to start (a story that fails validation, say), `/api` returns 502 until a later change fixes it. Changing a story makes its saved games incompatible: they open on a blocked screen, and the player starts a new game.
- A change to client files rebuilds and redeploys the client (about a minute); reloading the page picks it up.

Run `npx wrangler login` once before the first use; on another Cloudflare account, also create the KV namespace (`npx wrangler kv namespace create TUNNEL`) and put its id in `wrangler.jsonc`. Both models must be running. With `serve` stopped the page still opens, but `/api` returns 502.

The bundle carries the local credentials `local/local`, so anyone with the address can play: share it only with people you trust.

## Connect to another server

The scripts above always use local settings. To use another server, set the three public variables and run Expo directly, keeping port 8090. Add the browser's address to that server's `CORS_ORIGINS`.

```bash
EXPO_NO_DOTENV=1 EXPO_PUBLIC_API_URL=http://127.0.0.1:8000 EXPO_PUBLIC_API_USER=local EXPO_PUBLIC_API_PASS=local npx expo start --web --host localhost --port 8090
```

These values end up in the web bundle, so treat them as public. `npx expo export --platform web` with the same variables makes a static build for that server. `npm start`, `npm run android` and `npm run ios` read `.env.shared` and `.env.dev`; only the web build is verified.
