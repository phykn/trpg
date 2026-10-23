# QA

Guides and tools live here in git; recordings go to ignored `qa_test/runs/<run>/`, so deleting a recording never loses a tool. Use the root `.venv`. The scripts in `qa/` run from the repository root and use the models `run_api.py --local` would (`DECISION_MODEL`, `LLM_MODEL`; malkuth and gemma4 by default). Two checks choose their own models: the interpretation evals run from `server/` and take `--decision` and `--llm` (same defaults), and the decision bench names the model it tests.

A check is worth running only if it fails when the game breaks. The tests, the interpretation evals, the bench parity check and the mutation check exit 1 on a regression; the benches stop when their script or requests drift from the engine and print a verdict against noise; the mutation check shows that the tests catch the defects they claim to.

## What to run after a change

Cheapest first. Run every row your change touches, and when you report a result, cite the recording and its turn numbers.

| You changed | Run | Models | Time |
|---|---|---|---|
| Any server code | `.venv/bin/python -m pytest -q` · `.venv/bin/python -m ruff check server/` | no | 3 s |
| The API boundary: `api.py`, `run_api.py`, receipts, revisions or streams in `service.py` | The above · a short [play/](play/) game (`new`, a sentence that opens a card, `cancel`, the same sentence, `pick`) | yes | 1 min |
| A story in `scenarios/` | `cd server && ../.venv/bin/python -m src.story ../scenarios/<folder>` · the interpretation evals below | evals only | 1 s · 1.5 min |
| Interpretation: `interpret.py`, `models/decision.py`, question or option wording in `locale/ko.py` | Interpretation evals → `qa/decision/bench.py parity` → [decision/](decision/) bench → [misread/](misread/) if option wording changed | parity no, the rest yes | 1.5 min · 3 s · 2.5 min · 15–25 min |
| Narration: `narrate.py`, `jobs.py`, narration wording | [narration/](narration/) bench before and after → compare (a verdict per metric) → blind comparison when the numbers are within noise · for replies to typed lines, `narration/typed.py` (each line from its eval state) and `narration/loop.py` (scripted lines in one game, so each reply carries the turns before it) | yes | 10–15 min per side · 5–15 min |
| Screens in `client/` | `cd client && npm test -- --runInBand && npx tsc --noEmit && npm run lint` · the real UI check below | no | 10 s · by hand |
| Tests in `server/tests/` or `client/**/__tests__/`, or before trusting a green suite after a large change | The [mutation check](#mutation-check) for that side | no | 30 s per side |
| Fun and naturalness: people, a story's tone, balance, or after any large change | A [play/](play/) playtest round | yes | about 10 min per game |

To see why one sentence was read the way it was, run [misread/probe.py](misread/probe.py): it interprets that sentence at a chosen state and prints every model question and answer.

Both benches ask what the engine would ask: `decision/mirror.py` builds every request for a bench scene from `interpret.py` and `locale/ko.py`, and the gates are the engine's (`STEP_THETA`, `THETA`, `RELY_SHARE`, `narrate.THETA_N`). `decision/parity.py` writes the skeleton story's eval and witness states as bench scenes and fails when any request differs from the engine's; both benches run it before recording. Try another wording as a named entry in `EXPERIMENTS` (`bench.py run … --variants base,<name>`), not by editing the item files.

## Mutation check

[mutate/run.py](mutate/run.py) copies the working tree (uncommitted files included, ignored ones left out), plants one catalogued defect at a time from [mutate/server.py](mutate/server.py) or [mutate/client.py](mutate/client.py), runs that side's suite, and restores the file. Each mutant is one exact-string edit that a player or the docs would notice.

- **killed**: a test failed. The report names the first failing test; a kill by a hang or by an unrelated error is luck, not a guard.
- **survived**: no test catches that defect. Add a test of the intended behavior (from the docs, not from the mutant), or move the mutant to `EQUIVALENT` with the reason it changes nothing observable.
- **stale**: `old` no longer occurs exactly once, because the code moved. Rewrite the mutant.

The run exits 1 on any survivor or stale mutant. When you fix a bug, add a mutant that puts it back, so the test that guards it stays proven. A known bug that is not fixed yet is a `test.failing` (client) or `xfail` (server) test with the reason; it fails once the bug is fixed, so remove the mark in the same change.

## Interpretation evals

The evals are a gate. A case in `evals.yaml` that fails without a `known: "<why>"` mark is a **regression**. A case where a model gave no answer (an error, or a call past `--timeout`, 60 s by default) is **unanswered**. Either one exits 1. A `known` case that passes is printed as a **fix**: remove its mark in the same change. **Fragile** lines name cases whose deciding probability lies within 0.05 of its threshold, so a flip there may be noise; check them before calling a change a regression or an improvement. Mark a regression `known` only when the change accepts that miss, and say so in the report. Format: [docs/story.md](../docs/story.md) section 6.

## Narration bench

The script (`SCRIPT` in [narration/run.py](narration/run.py)) plays the skeleton story with fixed dice: chapter 1 ends at turn 14 with its recap, and turn 16 brings an ending and chapter 2's recap. Talks are sentences, since the person answers what the player said; everything else is a button, so a change in interpretation cannot change what is narrated. A refused line, a card without the scripted action, or any other action stops the run with exit 1 and names the turn: fix the script before comparing. A recording is never overwritten.

Narration is sampled, and the server does not replay a draft from its seed, so the spread across games is the noise. `--games N` (3 by default) sets the games per side. [narration/compare.py](narration/compare.py) prints each metric's per-game mean [min–max] per side and a verdict. A difference is "beyond noise" only when the ranges do not overlap and the means differ by more than either side's range. With 3 games a side, two identical sides get that by chance about 1 time in 20 per metric (1 in 100 with 4), so rerun before trusting a lone one. It refuses recordings of different scripts. Two runs of the same code (`narr-3/head-a`, `narr-3/head-b`) were within noise on every metric.

Besides quotes, weather words, length, attempts and dropped narrations, it counts per game:

- `phrase3`: a two-word phrase outside quotes in 3+ turns ("젖은 손을").
- `speaker`: one speaker's short cry ("컥!"), quote opening or phrase ("잘 모르겠어요") in 2+ of their turns.
- `ending`: a last word ("응시합니다") ending 3+ turns.
- `ahead_time`: the sky or weather worsening in a turn where no clock moved.
- `ahead_done`: outside quotes, an obstacle told as overcome or a clock as come to pass while it is short of full; a recap is judged on the state after the turn that closed its chapter.

These are heuristics, with word lists for the skeleton story in `compare.py`. Compare prints every counted item with its turns, so a count can be checked by eye. On the round 3–5 playtests they flag the cases in [findings.md](findings.md).

## Commands

```bash
# Mutation check: plant each catalogued defect in a copy of the tree (→ mutate-<side>/)
.venv/bin/python qa/mutate/run.py server -j 6
.venv/bin/python qa/mutate/run.py client -j 4
.venv/bin/python qa/mutate/run.py server T1 T6          # only these mutants

# Interpretation evals: the story's 74 sentences through the real engine; a regression gate (exit 1)
cd server && ../.venv/bin/python -m src.story.evals ../scenarios/skeleton --out ../qa_test/runs/<run>

# Decision-model bench: 216 genre sentences as the engine asks them (→ <run>/results/<model>/)
.venv/bin/python qa/decision/bench.py parity                # bench requests against the engine's, no models
.venv/bin/python qa/decision/bench.py run malkuth --run <run> [--variants base,plain_ask]
.venv/bin/python qa/decision/bench.py score --run <run> --against decision-2
.venv/bin/python qa/decision/analyze.py --run <run>         # detailed tables from the recordings only

# Misread bench: options that miss the sentence's answer (→ <run>/answers.jsonl)
.venv/bin/python qa/misread/bench.py record --run <run> && .venv/bin/python qa/misread/bench.py score --run <run> --against misread-2
.venv/bin/python qa/misread/variants.py record casual --run <run> && .venv/bin/python qa/misread/variants.py score --run <run>
.venv/bin/python qa/misread/probe.py CASES.yaml

# Narration bench: a 16-turn script through chapter 1's recap to an ending, × 3 games (→ narr-3/<name>.json)
.venv/bin/python qa/narration/run.py before --root ../trpg-base   # the checkout before the change; --games N
.venv/bin/python qa/narration/run.py after

# Typed-line benches (→ typed-1/<name>.json, loop-1/<name>.json); --root runs another checkout for a baseline
.venv/bin/python qa/narration/typed.py <name>
.venv/bin/python qa/narration/loop.py <name> --script long --repeat 2
.venv/bin/python qa/narration/compare.py qa_test/runs/narr-3/before.json qa_test/runs/narr-3/after.json
.venv/bin/python qa/narration/blind.py qa_test/runs/narr-3/before.json qa_test/runs/narr-3/after.json qa_test/runs/narr-3/blind.json

# Playtest: see qa/play/README.md
.venv/bin/python qa/play/play.py new play-1-explorer
```

`--root DIR` runs another checkout's server and stories (for example `git worktree add ../trpg-base HEAD`), so the baseline comes from the same place as the change (narration bench, probe).

## Layout

| Where | What |
|---|---|
| [findings.md](findings.md) | Open problems. Delete one when it is fixed; add new ones with their evidence (`qa_test/runs/<run>`, turn numbers) |
| [common.py](common.py) | Recording location, `--root`, `--story` and model settings, shared by the scripts |
| [mutate/](mutate/) | Mutation check: `run.py` and the server and client catalogs |
| [play/](play/) | Playtests: `play.py` plays one game from the shell through the same `/games/*` routes, Basic Auth, request ids, revisions and NDJSON streams as the web client, and prints what the web screen shows; personas, the categories of awkwardness, scores |
| [decision/](decision/) | Decision-model bench: 216 genre sentences (`data/`) and 120 held out (`heldout/plan.jsonl`, used by the misread bench); `mirror.py` builds the engine's requests for a scene and `parity.py` checks them against the engine. Item format in [GUIDE.md](decision/GUIDE.md) |
| [misread/](misread/) | Misread bench, option-wording comparison (`variants.py` over 150 casual sentences in `casual/`; v0 is the engine's wording), and `probe.py` for one sentence |
| [narration/](narration/) | Narration bench (`run.py`), per-metric noise verdicts (`compare.py`), blind comparison sets (`blind.py`) |

## Real UI check

After a screen change, play the flows in [docs/ui.md](../docs/ui.md) 6.2 at 320×568, 412×915 and desktop width, and record numbered turns and screenshots in `qa_test/runs/<run>/turns.md`. A change to `useGame.ts`, `services/` or a dialog also plays the Recovery flows. End `turns.md` with the 6.2 flows the run did not cover, so the next run knows what is still unchecked.

Passing tests and bench scores do not show the game is fun. Fun is judged by the metrics in [docs/fun.md](../docs/fun.md), by playtests, and finally by a person playing a game.
