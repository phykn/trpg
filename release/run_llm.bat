@echo off
setlocal

set "SERVER=run_llama_cpp.bat"
set "PORT=8000"
set "MODEL_ID=gemma4"
set "TBODY={\"model\":\"%MODEL_ID%\",\"messages\":[{\"role\":\"user\",\"content\":\"ping\"}],\"max_tokens\":4}"

start "LLM Server" cmd /c "%~dp0%SERVER%"

echo Loading LLM...
wsl -- bash -c "until curl -sf http://localhost:%PORT%/health >/dev/null 2>&1; do sleep 1; done; curl -s -o /dev/null http://localhost:%PORT%/v1/chat/completions -H 'Content-Type: application/json' -d '%TBODY%'"

echo Opening Cloudflare tunnel and updating Render release env...
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0update_render_llm_url.ps1" -Port %PORT% -ModelId "%MODEL_ID%"

endlocal
