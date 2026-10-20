# Playtest

Does the world feel natural, and does it feel like a game? A tester plays one game to an ending with the real models and the real service, and writes down each awkward moment with its turn number. It runs from the shell without a browser, so it is separate from the real UI check in [../README.md](../README.md).

## Playing a game

```bash
.venv/bin/python qa/play/play.py new play-3-explorer --seed 11      # a new game; prints the opening screen
.venv/bin/python qa/play/play.py say play-3-explorer "주위를 둘러본다"
.venv/bin/python qa/play/play.py pick play-3-explorer 1              # when a card opens, pick an option
.venv/bin/python qa/play/play.py cancel play-3-explorer              # or close it
.venv/bin/python qa/play/play.py press play-3-explorer 2             # a suggested button (growth: g1, g2, …)
.venv/bin/python qa/play/play.py look play-3-explorer                # the screen again
.venv/bin/python qa/play/play.py report play-3-explorer              # docs/fun.md metrics, at the end
```

- Every `say`, `pick`, `cancel` and `press` is one command, numbered in the transcript; turn N in notes means command N. A sentence that opens a card and the pick that answers it are two commands.
- Each command prints what the player sees: the action it was read as, the roll (`→ 성공`, `→ 실패`, or `→ 막힘` when something hidden blocked it), what changed, the narration, the scene, the suggested buttons and any open card. Scene lines marked `+` are new since the last command and `-` lines are gone, so a clock or companion that disappears shows up. A clock that draws closer at scene ends shows the scene's time spent (`다음 칸 3/6`); when it reaches the end, those clocks each fill a box.
- The indented lines under an action summarize what changed. The real screen shows them as icons and boxes, so their wording is not judged; the narration, dialogue and the screen's labels are.
- A card asks before acting:
  - `roll`: the target number two dice and the modifiers must reach (`⚠` when failing costs something that cannot be undone), the fixed modifiers, and what to lean on, each with its help. `기대지 않음` leans on nothing; `1번 남음` means leaning on it uses it up, and `이번 장 1번` means it is spent until the chapter changes (shown as `(씀)` in the state line). This is what the web roll card shows; it states no chance and no cost, which the result then shows.
  - `move`: where to go and who comes along.
  - `confirm` or `clarify`: asks you to confirm the action, or which of several meanings you meant.

  `*` marks the option your sentence chose. `→ 다음:` lists the rest of your sentence, done after this step. Growth (`g1`, …) is offered only once no card is open, as on the web screen.
- When a card shows the wrong action, note a misread, `cancel`, and rephrase once; if it is still wrong, press a button or pick the nearest option.
- An ending prints `=== 결말: … ===`; after it, commands are refused and only `report` runs.
- `new` takes `--approaches force=2,finesse=1,wits=1,charm=0` and `--traits a,b` (ids are printed at the start); without them it takes the story's values in order and its first traits.
- Everything goes to `qa_test/runs/<RUN>/`: `transcript.md` (as seen), `log.jsonl` (raw responses), `saves/` (the game), `notes.md` (written by the tester).
- Name runs `play-<round>-<persona>`. One round means one version of the code.
- The models take about 4 s per command (interpretation up to 2 s, narration 3–12 s), so a game of 40–50 commands takes about 10 minutes with the tester's own time.

## The tester

The tester is a first-time player. They do not read the story, the code or the docs (`scenarios/`, `server/`, `client/`, `docs/`, or `qa/` beyond this file). They know only what the screen showed and write what they want to do in their own Korean. They press buttons only when stuck.

| Persona | Plays by | Mostly shows |
|---|---|---|
| `explorer` | Going everywhere, looking, picking things up, finding another way when blocked | Place descriptions, moving, things, getting stuck |
| `talker` | Talking to everyone, asking favors, bringing people along, keeping promises | Voices and memory of people, relationships, companions |
| `bold` | Heading straight for the goal, breaking doors, taking risks | Rolls, costs, crises, pacing to the ending |
| `odd` | Casual speech, abbreviations, typos, two actions in one sentence, odd or impossible things | Interpretation, refusals, confirmation cards |

### During the game

Add one line to `notes.md` for each awkward moment: `- turn N [category] what was awkward and why`. Skip turns that were fine.

| Category | Meaning | Example |
|---|---|---|
| misread | The sentence became a different action | "여기서 기다려" skipped the scene |
| stuck | No idea what to do, or why something fails | The same refusal again with no reason |
| contradiction | The narration disagrees with the screen or earlier narration | A person shown as 경계 greets you like an old friend |
| forgot | A person does not know what you did or said | Still asks about a letter you handed over |
| repeat | The same description, line or reaction again | Grey clouds every turn |
| wording | Awkward Korean in narration or dialogue, translationese, wrong particles | A fishing-village child says "오, 친애하는 이여" |
| weightless | A choice or result seemed to change nothing | A failure with nothing different afterwards |
| good | A moment that felt like a game | Someone brings up an earlier promise |

### After the game

Stop at an ending or after 50 commands, run `report`, and end `notes.md` with the block below. Scores are 1–5; give the turn numbers behind any score of 3 or less.

```
## Scores
- My choices changed the story: N (turns …)     # fun.md F12
- I want to play again: N
- The people remembered me: N
- The world was consistent: N
- The narration read as natural Korean: N
- I wanted to know what came next: N
## One line
The moment that felt most like a game, and the moment that broke it most.
```

## Running a round and collecting it

When Claude runs a round, it starts one subagent per persona and gives each only this file and the brief below. Games do not wait for each other.

> You are a first-time player of a Korean text TRPG, persona `<persona>`. Follow "The tester", "During the game" and "After the game" in `qa/play/README.md`. Your run is `<RUN>` and your seed is `<N>`. Play only through `.venv/bin/python qa/play/play.py …` from the repository root. Do not read the story, code or docs, and write nothing but `qa_test/runs/<RUN>/notes.md`. When done, reply with your scores and the three worst awkward moments with their turn numbers.

Then whoever collects the round:

1. Checks each note in `notes.md` against that turn in `transcript.md`. Drop tester mistakes (something the screen did show).
2. Adds to [../findings.md](../findings.md), with evidence (`play-<round>-<persona>` turn N), whatever showed up in two or more games or blocked a game.
3. Writes the scores and metrics per game to `qa_test/runs/play-<round>-summary.md`, to compare with the next round.

An AI tester's scores do not stand in for a person's feelings. Use them to find awkwardness; F12 itself is judged from scores a person gives after playing.
