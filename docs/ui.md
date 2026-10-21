# Screens

This doc turns one turn of play, above all **the fun of rolling dice**, into a web UI. The client talks to the server only through [api.md](api.md).

```
client/
  app/index.tsx              entry; reopens the saved game_id if there is one
  screens/Title.tsx          title: resume, story shelf
  screens/Start.tsx          hero creation
  screens/Play.tsx           play screen layout
  logic/useGame.ts           server state, command lifecycle, recovery (section 3)
  logic/reveal.ts            reveal timeline (pure function)
  logic/useLog.ts            chat history (stored per game on this device)
  logic/useViewportHeight.ts the visible window height
  services/api.ts            the only HTTP and NDJSON boundary
  services/types.ts          response types (api.md)
  services/storage.ts        the saved trpg.game_id
  components/ui/             parts shared by every screen
    Icon.tsx(line icons)  Button.tsx(Button, IconButton)  Sheet.tsx(bottom sheet and Choice)
    motion.ts(enter motion)  useDialog.ts(Escape, focus trap and return)
  components/game/
    Row.tsx(icon row, Item, Pill)  Header.tsx  Clocks.tsx  Self.tsx  Scene.tsx  Boxes.tsx
    Narration.tsx(chat)  CommandBar.tsx
    RollCard.tsx  Dice.tsx
    ClarifyCard.tsx  ConfirmCard.tsx  MoveCard.tsx  GrowthCard.tsx  Menu.tsx  Ending.tsx
  design/tokens.js           tokens for color, spacing, type and motion timing
  locale/ko.ts               sentences the client composes
```

## 1. Principles

| Principle | Meaning |
|---|---|
| Everything visible without a tap | Everything needed for the current decision is always on one screen. No pages, tabs, expanders, tap-to-reveal names, horizontal scrolling or stacked panels. The only thing you scroll up to see is past history in the chat log |
| The UI does not know the rules | Target number, total, result, decisive modifiers, costs and candidates come from the server. The UI draws the values it receives and computes only motion |
| The server's response is the state | The response's `view` is adopted as is. The only optimistic motion is the dice tumble (4.4), and it decides no value |
| No illustrations | Dice, boxes and rings are UI elements drawn with shapes and text |
| Server sentences verbatim | Korean composed by the server is never edited or truncated. Client sentences live in `locale/ko.ts` |
| Icons and nudges over text | Things read through icons, color, boxes and dots instead of explanatory copy and labels. What you can do is not taught in sentences; it shows as names that start a sentence when tapped |
| One set of parts | Buttons, icon buttons, bottom sheets and rows each come from one component in `components/ui` and `Row.tsx`, with the same shape (corner radius, height, pressed state) |

The only taps are decisions (commands, helps, rolls). Nothing is tapped just to see information. There is a tap that skips the animation (4.5), but without it you reach the same end state.

The fun of dice is twofold. **The feel of rolling**: the player personally triggers the moment the outcome is decided, and tension gathers in that moment. **The feel that my decisions count**: you can see that the sentence you wrote, the approach you chose and the trait you saved changed the numbers and the result on screen. The server sets dice values with `roll(seed, t)`, and the animation neither hides nor proves that the value was fixed in advance. Fairness comes not from the fixed value but from the rules being applied exactly as shown (preview = execution, rule.md 3.4).

## 2. Layout

### 2.1 Play screen

Height is fixed to the visible window height, and regions stack from top to bottom. Only the chat log takes the remaining height; everything else is as tall as its content.

```
┌──────────────────────────────┐
│ 1장 등대에 오르다         ●● 👤 ≡│ Header: chapter number (gold) and title, health dots and hero
│ ⚑ 해가 지기 전에 등불실에 오르세요.  │ Aim: `chapter.aim`
│ ⚠ 몰려오는 폭풍 ■■□□ 해가 진다 ■□□ │ Danger: risk clocks, deadlines, threats, forks
│ ⌖ 등대 앞 (→ 마을) (→ 부두) (🔒 등불실)│ Place and exits (blocked ones with a lock, dimmed)
│ ◉ (도해) (기름통) (녹슨 문) ■□     │ Scene: people, things, obstacles, scene tags (no row if empty)
│                              │
│ premise / narration          │ Chat log: all remaining height,
│            [your sentence]   │   stacks top to bottom; scroll up
│ ⚂⚅ 완력 성공 10/8            │   to see past history
│ · · ·                        │
│ (녹슨 등대 문을 어떻게 할까요?  ↑) │ Input bar (example prompt about the scene's first target)
└──────────────────────────────┘
```

- **Every row has an icon.** The icon in the 20px left column is the row's category (aim ⚑, danger ⚠, place ⌖, around ◉), and categories never overlap. There are no text labels on screen; they go only to screen readers (`accessibilityLabel`). Empty rows are not drawn. The icon column stays in the same place from below the header down to the hero panel, and rows run on without dividers.
- **Names start sentences.** Exits, people, things and obstacles are round pills. Tapping one fills the start of a sentence into the input bar and moves focus there: an exit gives "등대 앞으로 간다" ("go to the lighthouse front"), a person "도해에게 " ("to Dohae …"), a thing or obstacle "녹슨 등대 문을 " ("the rusty lighthouse door …" as object). An exit can be sent as is; for the rest the player keeps writing. Pills cannot be tapped unless commands are open. Tapping a blocked exit starts the sentence with the obstacle blocking that way ("녹슨 등대 문을 "), pointing at what must be overcome. If the blocker is not yet visible, the exit cannot be tapped. It is a nudge: without explanation, the player learns by doing that "tapping a name makes a sentence".
- **Box color says whose side it is on.** Obstacle boxes are gold (something I am achieving); boxes and names in the danger row are all red (something bad approaching, whether risk clock, deadline or threat). An obstacle with only one box draws no boxes (one success opens it). An overcome obstacle stays in the scene, shown with ✓ and dimmed, and cannot be tapped. Beats have no row of their own, since two layers of time would not read. Instead, the next empty box of each deadline, threat and fork fills from the bottom by `beats / beats_max` (half opacity), so every step visibly spends time; risk clocks show none. Without it, testers lost a chapter to time they could not see (qa_test/runs/play-1-explorer 28, play-1-talker 23). A blocked exit shows a lock icon and dimming instead of an arrow.
- **The input bar is the model sentence.** Actions are always typed; the UI does not use the server's `view.buttons`. The empty input bar asks about the scene's first target: if there is an obstacle not yet full, "녹슨 등대 문을 어떻게 할까요?" ("What will you do with the rusty lighthouse door?"); otherwise the first person, "도해에게 무엇을 할까요?" ("What will you do to Dohae?"); then the first thing; and with nothing at all, "무엇을 할까요?" ("What will you do?").
- **Narration stacks like a chat.** The first line is `story.premise`; sent sentences are right-hand bubbles and narration is left-hand text, running top to bottom. Each rolled step puts a roll line directly above its narration: small dice pips, the approach, the result word (success in gold, failure in the danger color), a dimmed total and the target number in a small ring ("⚂⚅ 완력 성공 10 ⑧", "force success 10 ⑧"). The ring has the same shape as the roll card's target ring, so it does not read as a fraction. New items float up from 8px below (220ms); when new text arrives the log follows to the bottom, and scrolling up shows past history. The top edge of the chat log is not cut off but fades into the background over 20px. While waiting, three dots light up and dim in turn, with no text. Korean lines break only between words across the whole app (`word-break: keep-all` in `global.css`).
- **One color, one meaning.** The nine meanings below have hues that do not overlap (even the closest two are more than 30° apart on the color wheel), so they can be told apart by color alone without looking at shape. All have a contrast ratio of at least 8:1 on the background (`canvas.default`).

  | Meaning | Token | Color |
  |---|---|---|
  | Things being achieved (obstacle boxes, success, good tags, chapter number) | `gold` | gold `#e5bd76` |
  | Bad things approaching (danger row, failure, bad tags, high risk) | `danger` | red `#f19a8d` |
  | Health (♡ and dots) | `health` | green `#9fd69a` |
  | People | `kind.person` | sky `#80c1e8` |
  | Things (in the scene and carried) | `kind.thing` | teal `#86d0c4` |
  | Obstacles | `kind.obstacle` | purple `#d2a9ec` |
  | Stat modifier (and stat values in the hero panel) | `chip.stat` | indigo `#aaacf2` |
  | Help modifier (and the roll card's radios) | `chip.help` | lime `#bfd884` |
  | Hinder modifier | `chip.hinder` | pink `#eb9ccd` |

- **Kinds are told apart by color** (the table above). Pills show only names, not attitudes; a person traveling with you (`with`) gets a person icon before the pill.
- **Always visible versus opened.** What changes every turn or feeds straight into the next sentence (aim, health, danger, scene) is always visible. Health is drawn as dots, not boxes, so it is not confused with danger-clock boxes. Tapping the hero icon (one button with ♡ and the health dots) drops a panel down below the header (covering the rows below rather than pushing them). In order of how often they are used, it holds icon rows for name, health (dots only on the ♡ row), state (tags; no row if none), abilities (⚡), traits (☆), carried items, and journal (promises and beliefs). The panel opens only in `idle`, closes with Escape or a tap outside, and closes when the menu opens. When growth is available, the icon gets a gold dot and the right end of the panel's name row has a gold growth pill (✲ 1).
- **Rows wrap and grow.** If chips overflow a row they wrap to the next line and the chat log shrinks by that much. Names are never shortened or truncated.
- **Journal** (the last row of the hero panel) shows the parts of `journal` that matter now: every unkept promise and debt, plus beliefs about entities in the current scene. Fork choices are gathered on the ending panel (5.4).
- **Cards** (clarify, confirm, growth) are a `Sheet`: they rise floating up 24px from the bottom, cover only as much as their content needs, and have an icon and title in the head with close (✕) on the right. The aim and scene above stay visible. Only the roll card is a panel covering the whole play screen (4.2). Inside a card the same principle holds: everything is visible at once.
- **The menu** opens from the icon (≡) at the right of the header. It can be tapped only while commands are open (`idle`, `card`), and a small dropdown comes down below the icon, leaving the rest of the screen visible. Its only item is to-title, and it closes with Escape or a tap outside. Opened over a card, Escape closes only the menu. Going to the title keeps `trpg.game_id` and the received `view`, so resume on the title returns to the same game's destination. Nothing is sent to the server.
- On desktop, the same width frame (412px) is centered.

### 2.2 Size budget

Even at 320×568, one turn of narration (200 characters) must show in the chat log without scrolling (values in px).

| Region | 320×568 and 412×915 |
|---|---|
| Header | 40 |
| Aim, danger, place, around | per row: 28 for one line, 54 for two |
| Input bar | 62 (pill 44) |
| Chat | the rest, at least 232 |

Row text is already 12px and does not shrink. If a story produces a scene over budget, the overflowing narration is read by scrolling inside the chat log. In the skeleton story's busiest scene (three dangers, exits on two lines), the chat log is 296 at 320×568 (qa_test/runs/ui-2). QA checks the skeleton story's scene with the most chips at this size (6.2).

## 3. State machine

`useGame.ts` owns all server state on screen and the lifecycle of commands. Screens draw from this machine's state alone.

```
loading ─► start (no game_id) ─► creating ─► destination
creating ─ error status ─► start                      (its reason, or "서버 오류로 처리하지 못했습니다." ("The server could not handle it."), above the start button)
loading ─► restoring ─► destination | narrating | blocked

idle ─ command ─► sending ─┬─► destination             (refused: show reason above the input bar)
                           ├─► destination             (no steps: card)
                           └─► revealing ─► narrating ─► destination   (with steps)
card(roll) ─ release ─► rolling ─┬─► revealing ─► narrating ─► destination
                                 └─► destination       (refused: dice vanish with no value, reason shown)
card ─ answer / cancel ─► sending
sending | rolling ─ no response (30s) ─► stuck ─ same command again ─► sending | rolling
sending | rolling ─ 409(view) ─► destination          409(incompatible) ─► blocked
sending | rolling ─ 404 ─► start                      422 ─► destination (same as refused; a client bug)
sending | rolling ─ other error status ─► destination (its reason, or the same server-error line, above the input bar)
narrating ─ stream error ─► narration_error ─ retry ─► narrating
idle | card ─ menu: to title ─► start ─ resume ─► destination   (when there is a view and it is not an ending)
```

The **destination** is always decided from the adopted `view` in the same order: `ending` if there is an `ending`, `card` if there is a `card`, `card(growth)` if there is a `growth`, otherwise `idle`. The same holds for a 409's `view` and for reopening.

| State | Commands | Screen |
|---|---|---|
| `idle` | open | default |
| `sending` | locked | the sent sentence in the input bar, a small progress indicator |
| `card` | the card's answers and cancel, or a new sentence (discards the card) | card |
| `rolling` | locked | dice tumbling |
| `revealing` | locked; a tap jumps to the end state | reveal (4.5) |
| `narrating` | locked | three dots, received text appears in turn |
| `stuck` | only the resend-same-command button | "응답을 받지 못했습니다." ("No response received.") and resend (↻) in place of the input bar. After a roll they sit on the roll card instead, whose dice stop on the tray with no value (4.4) |
| `narration_error` | only the retry button | "서술을 받지 못했습니다." ("Narration not received.") The reveal's end state stays |
| `blocked` | to-title only | centered "이 판은 더 이어할 수 없습니다." ("This game can no longer continue.") and a to-title button. No input bar. `trpg.game_id` is not cleared |
| `ending` | new game only | ending panel (5.4) |

- **Steps before a card**: a response that ran the plan's earlier steps and stopped at a card has `steps` and `turn` as well as `view.card`. The UI reveals those steps, fetches their narration, then opens the card.
- **Command lifecycle**: each command gets one `request_id`, remembered together with its body. With no response within 30 seconds the state is `stuck`, and the command is resent only with the same `request_id` and body. The server's receipt returns the same result, so nothing runs twice. On resend the dice tumble again and the 600ms and 30-second timers restart; if the earlier request's response arrives late it is the same response, so whichever comes first is used. Game creation works the same way, with the stuck line and resend in place of the start button.
- **revision**: the response's `view.revision` goes on the next command. If a 409 carries a `view`, it is adopted, tumbling dice vanish with no value, and one line, "게임 상태가 바뀌어 새로 불러왔습니다" ("The game state changed and was reloaded"), appears above the input bar. `incompatible` without a `view` means `blocked`.
- **What is stored**: the browser keeps only `trpg.game_id` and chat history. `useLog` keeps the latest 300 items of the current game in `trpg.log.<game_id>` (deleting other games' history), with item ids that include the turn so reopening does not duplicate them; a device without history rebuilds it from the premise. A failed reopen clears nothing; only a 404 clears them and goes to the start screen.
- **Reopening**: the step records in `view.last` are drawn in their end state without motion; cached narration is fetched and shown at once, otherwise it is fetched in `narrating`. If that turn is already in the chat history, it is not written again and finishes as soon as it arrives. If there is a `view.card`, the card opens. The reveal is not replayed.

## 4. Roll

### 4.1 Five moments

For each step with a roll (`try(x ≠ player)` and a rolled `talk`), the player goes through five moments. Narration then writes this result into the story. Narration does not repeat the numbers; it writes the situation the numbers created.

| Moment | What the player sees | What the player does | Target fun (fun.md) |
|---|---|---|---|
| 1. Stakes | What they are attempting (action name `λ`, and the target's boxes if it has two or more), the target number to reach | reads | tension |
| 2. Decision | Modifiers with their sources (`솜씨 +2` "finesse +2", `젖은 발 −1` "Wet feet −1"), helps (`열쇠 +1` "Key +1") | taps a help, or taps again to remove it | agency |
| 3. Roll | Two dice shaking in the hand | holds, then releases | tension |
| 4. Reveal | The dice stop one by one, modifiers add in turn, the total reaches or falls short of the target and "성공" (success) or "실패" (failure) is stamped, and the decisive chip gets a label | watches | outcome, agency |
| 5. Cost | Obstacles and clocks whose boxes fill, crises, complications on failure | watches | outcome |

Every value comes from the card's `preview` and the step records. The approach and target are not changed on the card. If the sentence names no approach, the engine picks the highest stat without asking (engine.md 3.4). That was decided by the sentence; to change it, close the card and say it again. Accepting the roll card also confirms a high-risk roll (engine.md 4.2).

### 4.2 Roll card

Borrowed from Baldur's Gate 3's check screen. The stakes read as a single target number, and whether the roll reaches it is the whole of the tension.

```
┌──────────────────────────────┐
│     녹슨 등대 문을 솜씨로 다룬다    ✕ │ Attempt: action name (its label for a solution), close
│            ( 8 )⚠              │ Target number in a ring. ⚠ mark for high risk
│            ▢  ▢                │ Dice: blank faces, gold outline, swelling and shrinking like breath
│     솜씨 +2  물보라 −1           │ Fixed modifiers (stat, hinder; zero chips not drawn). Borderless text
│     ○ 뱃사람 +1 · 이번 장 1번     │ Helps: one per line, single-choice circles
│     ◉ 등대 열쇠 +1 · 이번 장 1번  │ Tap to choose, tap the chosen one to remove
└──────────────────────────────┘
```

- The card covers the whole play screen with a dimmed scrim and sits as a panel in its center. It appears briefly while growing (0.96 → 1, 220ms). Cancel is not a text button but close (✕) in the head and Escape, and it disappears after the roll.
- All card values come from the `preview` of the chosen entry in `card.options`. The initial choice is `card.selected`. The target number is `preview.dc`; if risk is high, the ring and number are in the danger color and a ⚠ mark sits at the ring's upper right ("되돌릴 수 없는 대가" ("an irreversible cost") goes to screen readers only). Otherwise the ring is a dim line. When the result lands, on success the ring fills gold and one gold ring spreads softly and fades (800ms); on failure the ring turns the danger color. The target's boxes are drawn only when it has two or more (one box for a target cleared by a single success is clutter). The risk tier is not written out.
- Helps sit one per line as a small circle (a radio, since only one can be chosen) and a name (the circles align in one column, sized to the longest line). Tapping one chooses it; tapping the chosen one again removes it. The server's "기대지 않음" (rely on nothing) option is not drawn; it is what is chosen when no circle is. The chosen one shows only as a dot inside the circle, with no gold outline. When the choice changes, the card redraws from that `preview`.
- When the card opens, focus goes to the panel itself. Sending it to the first control would draw a focus ring on that control because of the Enter that sent the sentence. Tab cycles from the first control.
- No probability, outcome line or cost line (4.6): `preview.stakes` and `preview.gain` are not drawn. No echo of the sentence either; it is already in the chat.
- Things that are used up carry the option's `note` as text, not a symbol, because they must read without a tap: a tag "1번 남음" ("1 use left"), a trait, thing or belief "이번 장 1번" ("once this chapter"). In the hero panel a trait, thing or belief already leaned on this chapter is dimmed.
- Even at 320×568 the panel fits on screen. With many helps, text shrinks to 12px.

### 4.3 Chips

The roll card draws the same modifier row on the card and in the reveal. A modifier is borderless text, one `mods` entry (name and signed value), colored per kind (`stat`, `help`, `hinder`) from `colors.chip` (the table in 2.1). The card's `preview.mods` and the step record's `mods` are the same list (api.md 3), so each modifier carries over unchanged from the card to the reveal. Name pills in the scene row are `Pill` from `Row.tsx`.

### 4.4 Dice

- `Dice.tsx` is two dice drawn as rounded squares with pips. `react-native-reanimated` animates tilt, spin and bounce.
- **Waiting**: while a roll is possible, the dice are blank faces with no pips and a gold outline, slowly swelling and shrinking like breath (1.05×, 900ms). Pips would read as a result already rolled, so the faces stay blank; this shows they are to be pressed without text like "tap to roll".
- **Hold**: while held, they shake slightly, and the longer the hold the bigger the shake (capped at 1.5 seconds). Where supported, a short vibration (`navigator.vibrate(10)`). A short tap also rolls.
- **Release**: sends the roll request `{card, pick}`, and the dice spin (one turn per 420ms) with faces changing randomly every 70ms. This is the only optimistic motion and it decides no value. After the roll, the card's decision area locks.
- **Stop**: once the response has arrived and 600ms have passed since release (whichever is later), `d1` and `d2` settle in turn on the server's values (standing upright, 1.12× to 1×). The values are the `roll` of `steps[0]` (the accepted step).
- **Blocked**: if `steps[0].result` is `blocked`, moments 1–5 do not happen. The dice do not stop but fade out over 300ms, and the name of what was revealed (the `reveal` in `changes`) appears in their place. Then the card fades out (200ms) and that obstacle appears in the scene row (150ms). No roll line remains in the chat. Narration follows. The player lives the rule that hidden things are found only by trying.
- **No response**: the dice stop on the tray with no value (blank faces, upright) and the state becomes `stuck`. The card stays as it was rolled, locked, with the stuck line and resend under the helps; the input bar under the scrim shows no second one. Resending the same roll returns the same result.
- **Notice**: when a roll comes back with the card still open (refused, an error status), its notice shows on the card under the helps, not above the input bar the card covers.

### 4.5 Reveal

The reveal does not show the result all at once; it splits it up so you can see **how your decisions changed the result**. `timeline(steps, motion, reduced) → Beat[]` in `logic/reveal.ts` is a pure function that turns step records into a timeline, and the UI draws the timeline in order. Timing values are the motion tokens in `design/`.

| # | Beat | What is shown | Time |
|---|---|---|---|
| 0 | | tumble from release until the response | at least 600ms |
| 1 | `die` | `d1`, `d2` stop in turn | 250ms each; `d2` starts 120ms after `d1` starts |
| 2 | `line` | the running total appears below the ring, starting at `d1 + d2` | 200ms |
| 3 | `chip` | each chip flies from its place into the total and the total changes by its value, in `mods` order | 180ms per chip |
| 4 | `settle` | the total stops at the server's `total`, and `result` shows: "성공" (success, gold) or "실패" (failure, danger color) quietly floats up beside the total over 400ms. No growing, glowing or shaking. Leaves time to read the result | 2200ms |
| 5 | `decisive` | the `decisive` modifier turns bold and gets a tag: "덕분에" ("thanks to") for `stat` and `help`, "때문에" ("because of") for `hinder` | 150ms |
| 6 | `box` | from `changes`, `fill` in the target's boxes in the card head, `clock`·`crisis`·`arrival` in the danger row (on a crisis the clock empties and "위기" ("crisis") appears beside the clock's name). Filling boxes briefly grow and settle back | 150ms per box |
| 7 | `fold` | the card fades out and a roll line (2.1) remains in the chat | 200ms |
| 8 | `change` | the remaining `changes` (tags, wounds, scars, reveals, moves, relationships, promises, chapter changes, endings) change in place in turn | 150ms per item |

- Beats never overlap; they run in order (only `d1` and `d2` overlap). With several step records, they go in `steps` order; only rolled steps do 1–8, and unrolled steps do only 6 and 8. A `choose` turn also does only 6 and 8.
- The response's `view` becomes the state as soon as it arrives, but rows that 6 and 8 animate show their `from` values until that beat. Past turns' narration stays in the chat history.
- Result names are the words in `locale/ko.ts` (성공, 실패).
- With two modifier chips it takes about 2 seconds. A tap anywhere skips the remaining animation and goes to the end state (the `view` as is).
- Under `prefers-reduced-motion`, there is no tumble, flight or box-filling motion; each beat's end state shows in turn for 100ms.
- The server decides the decisive chip, so the UI never computes "what if it had been absent".

### 4.6 What it does not do

Moving, looking around, picking up, handing over, small talk, free topics, choices and moving on from a scene show no dice. Showing dice for an action whose outcome is settled would strip the dice of meaning.

| Not done | Reason |
|---|---|
| Rerolls, buying rolls | The dice feel cheap and failure cannot change the situation |
| Showing probabilities and outcome lines | The target number and modifiers already say everything at stake, and tension gathers at the moment the total reaches that number |
| Narration stating numbers | The reveal already showed the numbers |
| Changing approach and target on the card | 4.1 |
| Devices that prove dice values in advance | Fairness comes from the rules applied as shown (1) |

## 5. Other screens

### 5.1 Narration

- The narration request starts as soon as the command's response arrives, and holds the received text until the reveal ends. The model writes while the reveal plays.
- Until text arrives, only three dots show at the end of the chat. The stream's `stage` and `attempt` are not used.
- When `text` arrives, characters appear in turn (60 per second; a tap shows it all at once). When all the text is shown and `done` has arrived, `narrating` ends.
- `error` shows after the reveal ends, with the server's `message` in small type under the fixed copy. A dropped stream or a non-2xx status counts as an `error` without `message`. The client has no timeout (the limit is the server's, engine.md 8).
- A chapter-change or ending turn continues with a recap (`/chapters/{k}/recap`, `k` from api.md 4) below the narration. It is requested after the narration's `done` (still in `narrating`), and a failure is the same `narration_error` as for narration. The typing carries on into the recap from where it was, and `narrating` ends only once the recap is typed too.
- Tag names in `done` rename the hero row and the chips.

### 5.2 Clarify, confirm, move

All three are a `Sheet` with no dice, and cancel is close (✕). `MoveCard` has a → head. With one option it asks "{place}으로 갈까요?" ("Go to {place}?") and has one "간다" ("Go") button. With more, under "어디로 갈까요?" ("Where to?"), it has one `Choice` row per exit; the place the sentence chose is the gold (`primary`) row at the top. Small text under a row says whether companions come along or stay ("윤슬과 함께", "with Yunseul"). One tap leaves. `ClarifyCard` shows options (at most three) as rows with a right arrow (`Choice`); `ConfirmCard` puts a bulleted list of the choice's effects under a ⚠ head and has one "고른다" ("Choose") button. Clarify does not repeat the sent sentence (it is already in the chat).

### 5.3 Growth

If there is a `view.growth`, `GrowthCard` (✲ growth) opens after narration ends. Growth is grouped by kind (`kind`) under the same icons as the hero panel: raising a stat (⚡) as tiles two per row like "완력 1→2" ("force 1→2"), and changing a trait (☆) and erasing a scar one per row ("뱃사람 → 토박이", "sailor → islander"). There is no group title text. Close (✕) means "later"; while closed, it reopens from the gold dot on the hero icon and the growth pill in the panel. Growth is a decision, so it takes a tap.

### 5.4 Ending

Once `view.ending` is set, after the ending narration and recap, everything below the header becomes the ending panel. It holds the ending's title under ☆ (serif, gold) and a gold rule, a recap per chapter (one per chapter in `view.recaps`, at most 100 characters, floating up in turn), and the list of fork choices (`journal`; forks with →, others with the tag icon), with a "새로 시작" ("start over") button at the bottom. The ending panel takes over the chat log's space, so with many chapters you scroll within it (the button stays fixed). The button opens Creation for the same story, skipping the title; creating there makes a new game and replaces `trpg.game_id`.

### 5.5 Start

Starting takes two screens.

**Title** (`Title.tsx`), top to bottom:

- Two dice (shapes), the title and a gold rule, floating up into view.
- One story card (title and premise; ‹ › flips through several). The saved game's story is shown first.
- Resume, if the saved game is this story and not at an ending (name, chapter, place; primary button), and start new (primary when there is no resume), which goes to Creation.
- One line with the version.

**Creation** (`Start.tsx`), top to bottom; every row is 40 high and the whole fits at 320×568 without scrolling. The premise is not repeated.

- Header: a round back button and a name pill (👤, up to 10 characters, placeholder "주인공" ("hero"), gold outline while typing).
- Stats (⚡): dots on the right fill as points are spent. One approach per row with its name and a short description, starting at 0 and set with − value +; + turns off at the total or the story's maximum.
- Traits (☆): dots fill as traits are chosen. One per row with name and text; choosing one tints the row gold and checks the square box on the right.
- Start: available once all points are spent and `pick` traits are chosen. It sends `POST /games` and opens the play screen.

## 6. Checks

### 6.1 Automated tests

| Subject | Tests |
|---|---|
| `useGame` | transitions: card, steps before a card, roll, 409 (with view, incompatible), same `request_id` after no response, `trpg.game_id` kept on reopen |
| `reveal.ts` | step records → timeline: chip order, success and failure, decisive tag, blocked, unrolled steps, reduced motion |
| `useLog` | a new game starts with the premise, the same id is kept only once, saved history is restored |
| `api.ts` | the same events even when NDJSON chunks split across line boundaries |
| Cards | tapping a help chooses it and tapping again removes it, its preview is drawn, `selected` is the initial choice, high risk gives a danger-colored target |

UI tests run against a fake `api`. Since the rules are not in the UI, no test computes results or target numbers in the UI.

### 6.2 Real UI

With a server running both models, play through the following at 412×915, desktop width and 320×568, and keep numbered turns and screenshots in `qa_test/runs/<run>/`.

| Flow | What to check |
|---|---|
| One screen | No scrolling outside the chat log, clipped text or overlap in any turn's screenshot. The chat follows to the bottom when new text arrives. The scene with the most chips and the card with the most helps |
| Free sentence | The roll card's approach and target match the sentence |
| Roll | Choosing and removing helps, hold and release, reveal order, success and failure marks, decisive chip, the roll line in the chat |
| Chain | A roll card after the reveal and narration of unrolled steps |
| Blocked | A hidden blocker revealed instead of dice (with a story that has a hidden obstacle) |
| Crisis and arrival | A clock fills and empties, a threat arrives |
| Clarify, confirm, move | A confirm card on a fork choice or a give by sentence, a move card at a place reached by sentence (companion note, choosing another place) |
| Growth, ending | Chapter-change recap, growth card, ending panel |
| Recovery | Refresh during a roll, resend after a lost response, refresh during narration |

Whether rolling is fun is measured separately ([fun.md](fun.md)).
