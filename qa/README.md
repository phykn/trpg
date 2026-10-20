# QA

Guides and tools live here in git; recordings go to ignored `qa_test/runs/<run>/`, so deleting a recording never loses a tool. Use the root `.venv`. The scripts in `qa/` run from the repository root and use the models `run_api.py --local` would (`DECISION_MODEL`, `LLM_MODEL`; malkuth and gemma4 by default). Two checks choose their own models: the interpretation evals run from `server/` and take `--decision` and `--llm` (same defaults), and the decision bench names the model it tests.

## What to run after a change

Cheapest first. Run every row your change touches, and when you report a result, cite the recording and its turn numbers.

| You changed | Run | Models | Time |
|---|---|---|---|
| Any server code | `.venv/bin/python -m pytest -q` · `.venv/bin/python -m ruff check server/` | no | 3 s |
| A story in `scenarios/` | `cd server && ../.venv/bin/python -m src.story ../scenarios/<folder>` · the interpretation evals below | evals only | 1 s · 30 s |
| Interpretation: `interpret.py`, `models/decision.py`, question or option wording in `locale/ko.py` | Interpretation evals → [decision/](decision/) bench → [misread/](misread/) if option wording changed | yes | 30 s · 2 min · 15 min |
| Narration: `narrate.py`, narration wording | [narration/](narration/) bench before and after → compare → blind comparison if the numbers are close | yes | 5 min per side |
| Screens in `client/` | `cd client && npm test -- --runInBand && npx tsc --noEmit && npm run lint` · the real UI check below | no | 10 s · by hand |
| Fun and naturalness: people, a story's tone, balance, or after any large change | A [play/](play/) playtest round | yes | 3–5 min per game |

To see why one sentence was read the way it was, run [misread/probe.py](misread/probe.py): it interprets that sentence at a chosen state and prints every model question and answer.

## Commands

```bash
# Interpretation evals: the story's 48 sentences through the real engine
cd server && ../.venv/bin/python -m src.story.evals ../scenarios/skeleton --out ../qa_test/runs/<run>

# Decision-model bench: 216 genre sentences (→ decision-1/results/<model>/)
.venv/bin/python qa/decision/bench.py run malkuth --variants base
.venv/bin/python qa/decision/bench.py score
.venv/bin/python qa/decision/analyze.py                     # detailed tables from the recordings only

# Misread bench: options that miss the sentence's answer (→ misread-1/)
.venv/bin/python qa/misread/bench.py record && .venv/bin/python qa/misread/bench.py score
.venv/bin/python qa/misread/variants.py record casual && .venv/bin/python qa/misread/variants.py score
.venv/bin/python qa/misread/probe.py CASES.yaml

# Narration bench: a 12-turn script × 3 games (→ narr-2/<name>.json)
.venv/bin/python qa/narration/run.py before --root ../trpg-base   # the checkout before the change
.venv/bin/python qa/narration/run.py after
.venv/bin/python qa/narration/compare.py qa_test/runs/narr-2/before.json qa_test/runs/narr-2/after.json
.venv/bin/python qa/narration/blind.py qa_test/runs/narr-2/before.json qa_test/runs/narr-2/after.json qa_test/runs/narr-2/blind.json

# Playtest: see qa/play/README.md
.venv/bin/python qa/play/play.py new play-1-explorer
```

`--root DIR` runs another checkout's server and stories (for example `git worktree add ../trpg-base HEAD`), so the baseline comes from the same place as the change (narration bench, probe).

## Layout

| Where | What |
|---|---|
| [findings.md](findings.md) | Open problems. Delete one when it is fixed; add new ones with their evidence (`qa_test/runs/<run>`, turn numbers) |
| [common.py](common.py) | Recording location, `--root`, `--story` and model settings, shared by the scripts |
| [play/](play/) | Playtests: `play.py` plays one game from the shell; personas, the categories of awkwardness, scores |
| [decision/](decision/) | Decision-model bench: 216 genre sentences (`data/`) and 120 held out (`heldout/plan.jsonl`, used by the misread bench). Item format in [GUIDE.md](decision/GUIDE.md) |
| [misread/](misread/) | Misread bench, option-wording comparison (`variants.py` over 150 casual sentences in `casual/`), and `probe.py` for one sentence |
| [narration/](narration/) | Narration bench, metric comparison, blind comparison sets |

## Real UI check

After a screen change, play the flows in [docs/ui.md](../docs/ui.md) 6.2 at 320×568, 412×915 and desktop width, and record numbered turns and screenshots in `qa_test/runs/<run>/turns.md`.

Passing tests and bench scores do not show the game is fun. Fun is judged by the metrics in [docs/fun.md](../docs/fun.md), by playtests, and finally by a person playing a game.
