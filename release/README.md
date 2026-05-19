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
- `run_llm.bat` - starts llama.cpp, waits for readiness, opens the Render URL updater.
- `run_llama_cpp.bat` - starts the local llama.cpp Docker server through WSL.
- `update_render_llm_url.ps1` - opens a Cloudflare quick tunnel and updates Render LLM env.
- `README.md` - this guide.

Required local setup:

- Git remote `origin` is configured.
- `client/.env.shared` and `client/.env.release` exist.
- Wrangler is authenticated or `CLOUDFLARE_API_TOKEN` is available to `npm run deploy`.
- `RENDER_API_KEY` and `RENDER_SERVICE_ID` are set.
- WSL, Docker, `cloudflared`, and the llama.cpp model path in `run_llama_cpp.bat` are available.
- Render backend auto-deploy is enabled for the pushed branch, or Render is otherwise configured to deploy after push.
