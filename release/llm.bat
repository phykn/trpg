@echo off
setlocal

if exist "%~dp0..\server\.env.release" (
  for /f "usebackq eol=# tokens=1,* delims==" %%A in ("%~dp0..\server\.env.release") do (
    if not defined %%A set "%%A=%%B"
  )
)
if not defined LLM_SERVER set "LLM_SERVER=llama.bat"
if not defined PORT set "PORT=8000"
if not defined MODEL_ID set "MODEL_ID=gemma4"
if not defined NAME set "NAME=%MODEL_ID%"

if not defined LLAMA_CPP_SUDO_PASSWORD (
  echo LLAMA_CPP_SUDO_PASSWORD is not set. Add it to server\.env.release before running release deploy.
  exit /b 1
)

set "TBODY={\"model\":\"%MODEL_ID%\",\"messages\":[{\"role\":\"user\",\"content\":\"ping\"}],\"max_tokens\":4}"

echo Stopping any existing LLM container...
wsl -- bash -lc "if command -v docker >/dev/null 2>&1; then echo %LLAMA_CPP_SUDO_PASSWORD% | sudo -S docker rm -f %NAME% >/dev/null 2>&1 || true; fi"

start "LLM Server" cmd /c "%~dp0%LLM_SERVER%"

echo Loading LLM...
wsl -- bash -c "until curl -sf http://localhost:%PORT%/health >/dev/null 2>&1; do sleep 1; done; until curl -sf -o /dev/null http://localhost:%PORT%/v1/chat/completions -H 'Content-Type: application/json' -d '%TBODY%'; do sleep 2; done"

echo Opening Cloudflare tunnel and updating Render release env...
if defined TRPG_LLM_READY_FILE (
  powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0render_tunnel.ps1" -Port %PORT% -ModelId "%MODEL_ID%" -ReadyFile "%TRPG_LLM_READY_FILE%" -ErrorFile "%TRPG_LLM_ERROR_FILE%"
) else (
  powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0render_tunnel.ps1" -Port %PORT% -ModelId "%MODEL_ID%"
)

endlocal
