# QA

Guides and tools live here in git; recordings go to ignored `qa_test/runs/<run>/`, so deleting a recording never loses a tool. Use the root `.venv`; the scripts in `qa/` run from the repository root.

A check is worth running only if it fails when the game breaks.

## What to run after a change

Cheapest first. Run every row your change touches, and when you report a result, cite the recording and its turn numbers.

| You changed | Run | Models | Time |
|---|---|---|---|
| Any server code | `.venv/bin/python -m pytest -q` · `.venv/bin/python -m ruff check server/` | no | 1 s |
| A story in `scenarios/` | `cd server && ../.venv/bin/python -m src.story ../scenarios/<folder>` | no | 1 s |
| Screens in `client/` | `cd client && npm test -- --runInBand && npx tsc --noEmit && npm run lint` · the real UI check below | no | 20 s · by hand |

## Real UI check

After a screen change, play the affected flows of [docs/game/07-screen.md](../docs/game/07-screen.md) at 320×568, 412×915 and desktop width, and record numbered turns and screenshots in `qa_test/runs/<run>/turns.md`. End `turns.md` with the flows the run did not cover, so the next run knows what is still unchecked.

Passing tests do not show the game is fun. Fun is judged by a person who did not write the story playing a game.

## Layout

| Where | What |
|---|---|
| [findings.md](findings.md) | Open problems. Delete one when it is fixed; add new ones with their evidence (`qa_test/runs/<run>`, turn numbers) |
| [common.py](common.py) | Recording location, `--root`, `--story` and model settings, shared by the scripts |
