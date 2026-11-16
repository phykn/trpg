#!/bin/sh
# The QA server: the API of `run_api.py --local` on 127.0.0.1:8001 with its saves in qa_test/saves, so AI testers never
# touch the app's server or saves/game. Run from the repository root.
cd "$(dirname "$0")/../../server" || exit 1
exec env APP_ENV=qa HOST=127.0.0.1 PORT=8001 BASIC_AUTH_USER=local BASIC_AUTH_PASS=local \
  CORS_ORIGINS=http://localhost:8091 SCENARIO_DIR=../scenarios SAVE_DIR=../qa_test/saves \
  DECISION_MODEL=kanana DECISION_BASE_URL=http://127.0.0.1:8081 \
  LLM_MODEL=gemma4 LLM_BASE_URL=http://127.0.0.1:8082/v1 ../.venv/bin/python run_api.py
