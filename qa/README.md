# QA

Guides and tools live here in git; recordings go to ignored `qa_test/runs/<run>/`, so deleting a recording never loses a tool. Use the root `.venv`; the scripts in `qa/` run from the repository root.

A check is worth running only if it fails when the game breaks.

## What to run after a change

Cheapest first. Run every row your change touches, and when you report a result, cite the recording and its turn numbers.

| You changed | Run | Models | Time |
|---|---|---|---|
| Any server code | `.venv/bin/python -m pytest -q` · `.venv/bin/python -m ruff check server/` | no | 1 s |
| A story in `scenarios/` | `cd server && ../.venv/bin/python -m src.story ../scenarios/<folder>` | no | 1 s |
| `interpret.py` or a story's topics, `묻는 말` or `evals.yaml` | `cd server && ../.venv/bin/python -m src.story.evals ../scenarios/<folder> --out ../qa_test/runs/<run>` | Kanana | 30 s |
| `narrate.py`, its prompts or thresholds, or a story's lines | `cd server && ../.venv/bin/python -m src.story.evals ../scenarios/<folder> --text --out ../qa_test/runs/<run>` | gemma4, Kanana | 5 min |
| Screens in `client/` | `cd client && npm test -- --runInBand && npx tsc --noEmit && npm run lint` · the real UI check below | no | 20 s · by hand |
| The API boundary: `api.py`, `service.py`, `view.py`, or a story's flow | The above · a short [shell game](#shell-game) through the changed flow | gemma4, Kanana | 2 min |

## Real UI check

After a screen change, play the affected flows of [docs/game/07-screen.md](../docs/game/07-screen.md) at 320×568, 412×915 and desktop width, and record numbered turns and screenshots in `qa_test/runs/<run>/turns.md`. End `turns.md` with the flows the run did not cover, so the next run knows what is still unchecked.

Passing tests do not show the game is fun. Fun is judged by a person who did not write the story playing a game.

## AI testers

Game QA by agents that do not know the answer. [tester/PROMPT.md](tester/PROMPT.md) holds the personas, the charters and the prompt; each tester plays through the shell player against a QA server of its own, so the app's server and `saves/game` stay untouched:

```bash
qa/tester/api.sh                                                  # the QA server on 127.0.0.1:8001, saves in qa_test/saves
PLAY_API=http://127.0.0.1:8001 .venv/bin/python qa/play/play.py look <run>
```

Each tester returns its report and the lead saves it to `qa_test/runs/<run>/report.md`, then checks every reported bug against the transcript before fixing it, and moves what is not fixed into [findings.md](findings.md).

## Shell game

`qa/play/play.py` plays a game through the API of a running `.venv/bin/python server/run_api.py --local`, the way the web client does, and prints what the screen shows. Everything goes to `qa_test/runs/<run>/`: `transcript.md` (each command and its output) and `play.json` (the game id, the view, a command or text still owed).

```bash
.venv/bin/python qa/play/play.py new play-1 --plus2 charm --plus1 wit   # a new dawn game (--story for another)
.venv/bin/python qa/play/play.py say play-1 "징수관을 마지막으로 본 게 언제입니까?"
.venv/bin/python qa/play/play.py read play-1 "들은 말"                 # a notebook group, or one line by id, with its acts
.venv/bin/python qa/play/play.py do play-1 a6 "솔직히 말씀해 주십시오"     # an act id from the screen or a line
.venv/bin/python qa/play/play.py conclude play-1 --who 2 --how 1      # line ids; a question left out stays blank
.venv/bin/python qa/play/play.py retry play-1                         # after 응답을 받지 못했습니다 or 서술을 받지 못했습니다
.venv/bin/python qa/play/play.py look play-1
```

`[턴 N]` is the game's turn; a notebook read is a turn of its own, as on the web. Act ids hold only until the next turn, so take them from the latest output.

## Layout

| Where | What |
|---|---|
| [findings.md](findings.md) | Open problems. Delete one when it is fixed; add new ones with their evidence (`qa_test/runs/<run>`, turn numbers) |
| [play/play.py](play/play.py) | The shell game |
