# Release Deploy

Double-click `deploy.bat` to deploy the current workspace state.

The script:

1. Starts local llama.cpp and updates Render's LLM URL through a Cloudflare tunnel.
2. Stages all non-ignored repo changes.
3. Creates a release commit when there are staged changes.
4. Pushes the current branch to `origin`.
5. Builds the Expo web bundle and deploys it to Cloudflare Workers.

Files in this folder:

- `deploy.bat` - double-click entrypoint.
- `deploy.ps1` - release orchestration.
- `lib.ps1` - shared PowerShell helpers for env loading, preflight checks, and native command execution.
- `llm.bat` - starts llama.cpp, waits for readiness, opens the Render tunnel updater.
- `llama.bat` - starts the local llama.cpp Docker server through WSL.
- `render_tunnel.ps1` - opens a Cloudflare quick tunnel and updates Render LLM env.
- `README.md` - this guide.

Required local setup:

- Git remote `origin` is configured.
- `client/.env.shared` and `client/.env.release` exist.
- Wrangler is authenticated or `CLOUDFLARE_API_TOKEN` is available to `npm run deploy`.
- `RENDER_API_KEY`, `RENDER_SERVICE_ID`, and `LLAMA_CPP_SUDO_PASSWORD` are set in `server/.env.release`.
- WSL, Docker, `cloudflared`, and the llama.cpp model path in `llama.bat` are available.
- Render backend auto-deploy is enabled for the pushed branch, or Render is otherwise configured to deploy after push.

Optional LLM overrides can also live in `server/.env.release` before running `deploy.bat`:

- `LLM_SERVER`, `MODEL_ID`, `PORT`
- `LLAMA_CPP_IMAGE`, `LLAMA_CPP_MODEL_PATH`, `LLAMA_CPP_MODEL_VOLUME`, `LLAMA_CPP_CTX`
- `LLM_TEMP`, `TOPK`, `TOPP`, `MINP`, `PRESENCE`, `REPEAT`
