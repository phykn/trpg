# Release Deploy

Double-click `deploy.bat` to deploy the current workspace state.

CLI options:

```powershell
.\release\deploy.ps1 [-ClientOnly] [-CommitMessage "message"] [-LlmReadyTimeoutSeconds 900]
```

Use `-ClientOnly` when the backend is already deployed and only the Expo web bundle should be rebuilt and pushed to Cloudflare. In that mode the script skips the local LLM tunnel, git commit, and git push.

Default full deploy:

1. Starts local llama.cpp and updates Render's LLM URL through a Cloudflare tunnel.
2. Waits until the LLM tunnel has updated Render and is reachable.
3. Stages all non-ignored repo changes.
4. Creates a release commit when there are staged changes.
5. Pushes the current branch to `origin`.
6. Builds the Expo web bundle and deploys it to Cloudflare Workers.

Files in this folder:

- `deploy.bat` - double-click entrypoint.
- `deploy.ps1` - release orchestration.
- `lib.ps1` - shared PowerShell helpers for env loading, preflight checks, and native command execution.
- `llm.bat` - starts llama.cpp, waits for readiness, opens the Render tunnel updater.
- `llama.bat` - starts the local llama.cpp Docker server through WSL.
- `render_tunnel.ps1` - opens a Cloudflare quick tunnel and updates Render LLM env.
- `README.md` - this guide.

The LLM window must stay open after it prints `Leave this window open while Render uses the local LLM.`
If a quick tunnel URL does not resolve through DNS, the tunnel updater retries with a new URL before failing the deploy.

Required local setup for client deploy:

- `client/.env.shared` and `client/.env.release` exist.
- Wrangler is authenticated or `CLOUDFLARE_API_TOKEN` is available to `npm run deploy`.

Additional setup for full deploy:

- Git remote `origin` is configured.
- `RENDER_API_KEY`, `RENDER_SERVICE_ID`, and `LLAMA_CPP_SUDO_PASSWORD` are set in `server/.env.release`.
- WSL, Docker, `cloudflared`, and the llama.cpp model path in `llama.bat` are available.
- Render backend auto-deploy is enabled for the pushed branch, or Render is otherwise configured to deploy after push.

Optional LLM overrides can also live in `server/.env.release` before running `deploy.bat`:

- `LLM_SERVER`, `MODEL_ID`, `PORT`
- `LLAMA_CPP_IMAGE`, `LLAMA_CPP_MODEL_PATH`, `LLAMA_CPP_MODEL_VOLUME`, `LLAMA_CPP_CTX`
- `LLM_TEMP`, `TOPK`, `TOPP`, `MINP`, `PRESENCE`, `REPEAT`
