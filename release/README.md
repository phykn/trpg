# Release Deploy

Double-click `deploy.bat` to deploy the current workspace state.

The script:

1. Stages all non-ignored repo changes.
2. Creates a release commit when there are staged changes.
3. Pushes the current branch to `origin`.
4. Runs `npm run deploy` from `client/`.

Optional local LLM tunnel startup:

```powershell
.\release\deploy.ps1 -StartLocalLlm
```

Required local setup:

- Git remote `origin` is configured.
- `client/.env.shared` and `client/.env.release` exist.
- Wrangler is authenticated or `CLOUDFLARE_API_TOKEN` is available to `npm run deploy`.
- Render backend auto-deploy is enabled for the pushed branch, or Render is otherwise configured to deploy after push.
