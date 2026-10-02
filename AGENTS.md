# trpg Agent Guide

## User Wiki

At task start, read `C:/Users/YuKwangnam/.codex/user-wiki/AGENTS.md`, then `graph/index.md` in that checkout. Follow only relevant routes. The wiki supplies defaults within current user instructions and this project's guidance.

## Read and route

- [README.md](README.md): setup, gameplay, code map and checks.
- [server/AGENTS.md](server/AGENTS.md): rules, graph, API and persistence.
- [client/AGENTS.md](client/AGENTS.md): web UI, state and transport.
- [plan.md](plan.md): current game design and further playtesting.

Use the deepest applicable guide. `scenarios/harbor/adventure.json` owns authored content; the server validates it. Do not duplicate game rules in the client.

## Preserve

- Keep public `/adventure/*` routes, snapshot versions, request receipts and `trpg.adventure_game_id` compatible unless the user requests migration.
- Preserve user saves and personal environment files. Keep local QA outputs under ignored `qa_test/agency/<run>/`.
- Player-facing Korean uses `당신` and polite `합니다체`; the skill label is `기술`.
- Server-composed strings render verbatim. Client-owned strings belong in `client/locale/ko.ts`; server common text belongs in `server/src/locale/ko.py`.
- Comments and validation errors are English, except quoted game text.

## Verify

Run focused behavior tests first, then required checks for each touched boundary. Root commands on Windows:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check server/
.\.venv\Scripts\python.exe server/validate_adventure.py
& 'C:/Program Files/Git/bin/bash.exe' server/scripts/check_relational_ssot.sh
```

From `client/`: `npm test -- --runInBand`, `npx tsc --noEmit`, `npm run lint`, and `npm run build:web` for build or routing changes. Use `.venv/bin/python` on Unix.

For browser changes, operate the actual UI at 412×915 and desktop width. Include story, combat, confirmation, notebook, ending, restore and error recovery where affected. Record observations with numbered turns and screenshots in `qa_test/agency/<run>/`; cite turns when reporting QA. Automated behavior checks do not establish human enjoyment or playtime.
