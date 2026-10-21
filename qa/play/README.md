# Playtest

Does the world feel natural, and does it feel like a game? A tester plays one game to an ending with the real models and the real server, and writes down each awkward moment with its turn number. It runs from the shell without a browser, so it is separate from the real UI check in [../README.md](../README.md), but it goes through the same API as the web client and shows what the web screen shows (see "Shell and web" below).

## Playing a game

```bash
.venv/bin/python qa/play/play.py new play-3-explorer --seed 11      # a new game; prints the opening screen
.venv/bin/python qa/play/play.py say play-3-explorer "주위를 둘러본다"
.venv/bin/python qa/play/play.py pick play-3-explorer 1              # when a card opens, pick an option
.venv/bin/python qa/play/play.py cancel play-3-explorer              # or close it
.venv/bin/python qa/play/play.py press play-3-explorer g1            # growth, when it is offered
.venv/bin/python qa/play/play.py retry play-3-explorer               # after "응답을 받지 못했습니다" or "서술을 받지 못했습니다"
.venv/bin/python qa/play/play.py look play-3-explorer                # the screen again
.venv/bin/python qa/play/play.py report play-3-explorer              # docs/fun.md metrics, at the end
```

- Every `say`, `pick`, `cancel` and `press` is one command, numbered in the transcript; turn N in notes means command N. A sentence that opens a card and the pick that answers it are two commands. `retry` finishes the command before it and keeps its number.
- Each command prints what the player sees: the action it was read as, the roll, what changed, the narration, the scene and any open card. A roll reads as the roll card's reveal: the dice, the modifiers (`덕분에` or `때문에` on the one that decided it), the total against the target, and `→ 성공`, `→ 실패`, or `→ 막힘` when something hidden blocked it (no dice then). Scene lines marked `+` are new since the last command and `-` lines are gone, so a clock or companion that disappears shows up. A clock that draws closer at scene ends shows the scene's time spent (`다음 칸 3/6`); when it reaches the end, those clocks each fill a box. `위기` beside a clock means the last turn brought its crisis.
- The indented lines under an action summarize what changed. The real screen shows them as icons and boxes, so their wording is not judged; the narration, dialogue and the screen's labels are.
- `거절:` is the reason a command was refused, and `알림:` a notice the web shows in the same place, such as `게임 상태가 바뀌어 새로 불러왔습니다.` when the game changed elsewhere. `서술 오류:` means the narration did not arrive: commands stay locked, as on the web, until `retry` gets it.
- The last line, `입력창:`, is the empty input bar's prompt. There are no suggested buttons; actions are typed.
- A card asks before acting:
  - `roll`: what you attempt (with the target's boxes when it has two or more), the target number two dice and the modifiers must reach (`⚠` when failing costs something that cannot be undone), the fixed modifiers, and what to lean on, each with its help. `1번 남음` means leaning on it uses it up, and `이번 장 1번` means it is spent until the chapter changes (shown as `(씀)` in the state line). `*` marks what is chosen when the card opens; `기대지 않음` rolls leaning on nothing. It states no chance and no cost, which the result then shows.
  - `move`: `…으로 갈까요?` with `1) 간다` when your sentence named one place; otherwise `어디로 갈까요?` with each way and who comes along, your sentence's pick marked `*`.
  - `confirm`: a choice that cannot be taken back, with its effects and `1) 고른다`.
  - `clarify`: which of several meanings you meant.
- Growth (`성장:`, `g1`, …) is offered once no card is open. Typing a sentence instead leaves it for later.
- When a card shows the wrong action, note a misread, `cancel`, and rephrase once; if it is still wrong, pick the nearest option.
- An ending prints `=== 결말: … ===` with each chapter's recap and the choices made; after it, commands are refused and only `report` runs.
- `new` takes `--approaches force=2,finesse=1,wits=1,charm=0`, `--traits a,b` (ids are printed at the start) and `--name 이름`; without them it takes the story's values in order, its first traits and the name `주인공`, as the web start screen does.
- Everything goes to `qa_test/runs/<RUN>/`: `transcript.md` (as seen), `log.jsonl` (each command's request, status and response, with the narration and recap events), `saves/` (the game), `play.json` (the shell's state: the view on screen, a command awaiting its answer, a narration to retry), `notes.md` (written by the tester).
- Name runs `play-<round>-<persona>`. One round means one version of the code.
- The models take about 4 s per command (interpretation up to 2 s, narration 3–12 s), so a game of 40–50 commands takes about 10 minutes with the tester's own time.

### Shell and web

`play.py` builds the server the way `run_api.py --local` does (the same stories, models, model check at startup, and Basic Auth), runs it in the same process, and changes only where the game is saved (`saves/` of the run) and its dice seed (`--seed`), so a game can be replayed. Every command goes through `/games/*` as `client/services/api.ts` sends it, and `client/logic/useGame.ts` decides what follows:

- Each command gets a fresh `request_id` and the `revision` of the view last shown. A 409 with a view adopts that view and shows the conflict notice; one without a view shows `이 판은 더 이어할 수 없습니다.`. A 422 shows its reason; a 500 shows only `(HTTP 500)`, since the web shows nothing, with the traceback on stderr.
- A command that gets no answer (the process died, or the connection dropped) locks commands until `retry` resends it with the same `request_id`; the server's receipt answers, so nothing runs twice.
- Narration and recap are read as the NDJSON streams the client reads. An `error` event, a failed request, a line that is not JSON, or a stream that ends without `done` is a narration error. The recap of a closed chapter is asked for after the narration's `done`. Tag names in `done` rename the tags on screen.

The screen is drawn from the same fields the web screen draws. What the shell used to show and the web does not, now gone: the rest of a plan (`→ 다음:`), the suggested buttons and `press N` (ui.md 2.1: the web does not use `view.buttons`), place senses, people's attitudes, what an obstacle blocks (the web marks the blocked way instead), `0/1` on a one-box obstacle, wounds and the growth count (the web shows health left, `체력 2/2`), and beliefs about what is not in the scene. What the web shows and the shell did not, now added: the player's name, the input bar's prompt, `위기` on a clock, the decisive modifier and `±0` stat chips in a roll, the roll card's target boxes and its target number from the option chosen when it opens, the move and confirm cards' own titles and buttons, growth by its short name with the new trait's text, and the ending panel. Still different: icons and colours are words; changes are listed, not animated; the hero panel, which the web opens with a tap, is always the `나:` line; the web draws no row for `기대지 않음` (it is the roll with no help chosen); a card covers the web's input bar, while here a sentence can follow any card; and `look` reloads the game as reopening the page does, but does not ask for narration again.

## The tester

The tester is a first-time player. They do not read the story, the code or the docs (`scenarios/`, `server/`, `client/`, `docs/`, or `qa/` beyond this file). They know only what the screen showed and write what they want to do in their own Korean.

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
| contradiction | The narration disagrees with the screen or earlier narration | A door the screen shows as open (✓) is still shut in the narration |
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
