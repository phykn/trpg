@echo off
setlocal
title Local LLM

set "NAME=qwen35-9b"
set "MODEL_ID=qwen35-9b"
set "PORT=8000"
set "CTX=16384"
set "IMG=ghcr.io/ggml-org/llama.cpp:server-cuda"
set "MODELPATH=/models/gemma-4-E4B-it-Q4_K_M.gguf"
set "PASS=0706"

set "TEMP=1.0"
set "TOPK=20"
set "TOPP=0.9"
set "MINP=0.0"
set "PRESENCE=1.2"
set "REPEAT=1.1"

set "ARGS=-m %MODELPATH% --alias %MODEL_ID% --host 0.0.0.0 --port %PORT%"
set "ARGS=%ARGS% -c %CTX% -np 1 -ngl 99"
set "ARGS=%ARGS% --flash-attn on"
set "ARGS=%ARGS% --cache-type-k q4_0 --cache-type-v q4_0"
set "ARGS=%ARGS% -b 128 -ub 128"
set "ARGS=%ARGS% -t 12 -tb 12"
set "ARGS=%ARGS% --temp %TEMP% --top-k %TOPK% --top-p %TOPP% --min-p %MINP%"
set "ARGS=%ARGS% --presence-penalty %PRESENCE% --repeat-penalty %REPEAT%"
set "ARGS=%ARGS% --jinja"

set "DRUN=sudo docker run --rm --name %NAME% --gpus all"
set "DRUN=%DRUN% -v /home/kn/models:/models"
set "DRUN=%DRUN% -p %PORT%:%PORT%"
set "DRUN=%DRUN% %IMG% %ARGS%"

set "SH=echo %PASS% | sudo -S -v 2>/dev/null"
set "SH=%SH% && sudo service docker start >/dev/null 2>&1"
set "SH=%SH% && (sudo docker rm -f %NAME% >/dev/null 2>&1 || true)"
set "SH=%SH% && cleanup() { echo %PASS% | sudo -S docker rm -f %NAME% >/dev/null 2>&1 || true; exit 0; }"
set "SH=%SH% && trap cleanup EXIT HUP INT TERM"
set "SH=%SH% && %DRUN%"

wsl -- bash -lc "%SH%"

wsl -- bash -lc "echo %PASS% | sudo -S docker rm -f %NAME% >/dev/null 2>&1 || true"

if errorlevel 1 pause
endlocal
