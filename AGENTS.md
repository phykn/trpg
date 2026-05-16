# trpg Agent Guide

This repository is a Korean-language TRPG split into a FastAPI server, an Expo client, local QA/story tooling, scenario seeds, and design docs. General coding behavior lives in the global `C:\Users\KN\.codex\AGENTS.md`; this file covers repo-specific routing and verification.

## Read First

- Root overview and dev/deploy commands: `README.md`.
- Product and runtime contracts: `docs/README.md`, `docs/plan.md`.
- Backend work: `server/AGENTS.md`.
- Client work: `client/AGENTS.md`.
- QA and scenario authoring: `agency/AGENTS.md`.

Use the deepest applicable `AGENTS.md` as the source of truth. If instructions conflict, prefer the file closest to the code being edited, then this file, then the global file.

## Boundaries

- `server/` owns graph runtime, persistence, LLM calls, API routes, and server-composed Korean game text.
- `client/` owns the Expo UI, client state, local storage pointer, and client-owned Korean labels.
- `agency/` owns local QA runs and story/scenario build tooling.
- `scenarios/` is seed content. Validate seed edits instead of treating JSON changes as harmless text edits.
- `docs/` records design contracts. Update it only when behavior or public contracts change.

Do not duplicate rules across layers. When a change crosses server/client/agency, verify each touched boundary with the narrowest useful command.

## Commands

From the repo root:

```bash
.venv/bin/python -m pytest -q
.venv/bin/python -m pytest server/tests/path/to/test_file.py::test_name -q
.venv/bin/ruff check server/ agency/
.venv/bin/python agency/run_qa.py --agent socialite --turns 25
```

From `server/`:

```bash
../.venv/bin/python run_api.py
```

From `client/`:

```bash
npm run lint
npx tsc --noEmit
npm test -- --runInBand
npm run web
```

Use Windows PowerShell path forms when running directly in this workspace if the Unix-style examples fail, e.g. `.\.venv\Scripts\python.exe -m pytest -q`.

## Language and Text

- Player-facing Korean uses 2nd-person polite `합니다체`: `당신`, `~합니다`, `~입니다`.
- The canonical player-facing term for skills is `기술`; keep `스킬` only where accepting player input synonyms.
- Client components render server-composed strings verbatim. Client-owned labels belong in `client/locale/`, not inline JSX.
- Code comments and validation errors stay English unless quoting in-game Korean text.

## Verification

For Python behavior, add or update focused pytest coverage before broad runs. For client behavior, run the relevant Jest test or type/lint command. For scenario edits, run the story tool checks or seed validation named in the local guide. For QA claims, read transcripts under `qa_test/agency/<agent>/` and cite turn numbers.
