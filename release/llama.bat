@echo off
setlocal
title Local LLM

if not defined MODEL_ID set "MODEL_ID=gemma4"
if not defined NAME set "NAME=%MODEL_ID%"
if not defined PORT set "PORT=8000"
if not defined LLAMA_CPP_CTX set "LLAMA_CPP_CTX=16384"
if not defined LLAMA_CPP_IMAGE set "LLAMA_CPP_IMAGE=ghcr.io/ggml-org/llama.cpp:server-cuda"
if not defined LLAMA_CPP_MODEL_PATH set "LLAMA_CPP_MODEL_PATH=/models/gemma-4-E4B-it-Q4_K_M.gguf"
if not defined LLAMA_CPP_MODEL_VOLUME set "LLAMA_CPP_MODEL_VOLUME=/home/kn/models:/models"

if not defined LLAMA_CPP_SUDO_PASSWORD (
  echo LLAMA_CPP_SUDO_PASSWORD is not set. Add it to server\.env.release before running release deploy.
  exit /b 1
)

if not defined LLM_TEMP set "LLM_TEMP=1.0"
if not defined TOPK set "TOPK=20"
if not defined TOPP set "TOPP=0.9"
if not defined MINP set "MINP=0.0"
if not defined PRESENCE set "PRESENCE=1.2"
if not defined REPEAT set "REPEAT=1.1"

set "ARGS=-m %LLAMA_CPP_MODEL_PATH% --alias %MODEL_ID% --host 0.0.0.0 --port %PORT%"
set "ARGS=%ARGS% -c %LLAMA_CPP_CTX% -np 1 -ngl 99"
set "ARGS=%ARGS% --flash-attn on"
set "ARGS=%ARGS% --cache-type-k q4_0 --cache-type-v q4_0"
set "ARGS=%ARGS% -b 128 -ub 128"
set "ARGS=%ARGS% -t 12 -tb 12"
set "ARGS=%ARGS% --temp %LLM_TEMP% --top-k %TOPK% --top-p %TOPP% --min-p %MINP%"
set "ARGS=%ARGS% --presence-penalty %PRESENCE% --repeat-penalty %REPEAT%"
set "ARGS=%ARGS% --jinja"

set "DRUN=sudo docker run --rm --name %NAME% --gpus all"
set "DRUN=%DRUN% -v %LLAMA_CPP_MODEL_VOLUME%"
set "DRUN=%DRUN% -p %PORT%:%PORT%"
set "DRUN=%DRUN% %LLAMA_CPP_IMAGE% %ARGS%"

set "SH=echo %LLAMA_CPP_SUDO_PASSWORD% | sudo -S -v 2>/dev/null"
set "SH=%SH% && sudo service docker start >/dev/null 2>&1"
set "SH=%SH% && (sudo docker rm -f %NAME% >/dev/null 2>&1 || true)"
set "SH=%SH% && cleanup() { echo %LLAMA_CPP_SUDO_PASSWORD% | sudo -S docker rm -f %NAME% >/dev/null 2>&1 || true; exit 0; }"
set "SH=%SH% && trap cleanup EXIT HUP INT TERM"
set "SH=%SH% && %DRUN%"

wsl -- bash -lc "%SH%"

wsl -- bash -lc "echo %LLAMA_CPP_SUDO_PASSWORD% | sudo -S docker rm -f %NAME% >/dev/null 2>&1 || true"

if errorlevel 1 pause
endlocal
