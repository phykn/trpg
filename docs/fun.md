# Fun

Fun cannot be proven. This document breaks fun into elements, separates out which of each element's premises the rules guarantee, and handles whether those premises actually turn into fun through measurements on the logs and hypotheses. Measurements never feed into `R`, `K` or prompts.

## 1. Elements

| Element | Meaning | Mechanics it relies on |
|---|---|---|
| **Agency** | The player's sentence becomes an action as meant, and that action changes the world | Interpretation, improvisation, multiple solutions, choosing what to rely on |
| **Tension** | Outcomes are uncertain and the stakes are visible | 2d6, risk, risk clocks, threats, deadlines, roll cards |
| **Consequence** | Failures and choices change the situation, and those changes come back into play later | Costs, complications, forks, scars, history patterns |
| **Relationships** | People treat the player differently depending on what the player has done | Trust and fear, favors, promises, bonds |
| **Growth** | The protagonist and the player get better with each chapter | Growth, what was relied on, declarations |
| **Rhythm** | Tension and release alternate, and the story ends without dragging | Beats and scenes, deadlines, rest |

## 2. Premises the rules guarantee

These hold as properties, so play does not measure them again. What play measures is whether they feel like fun.

| Element | Premise | Basis |
|---|---|---|
| Agency | What runs is always a candidate, and when the model is unsure, the player picks or nothing changes | engine.md model substitution, conservatism under uncertainty |
| Agency | No sentence gains more than a small advantage, so judging the situation, not eloquence, decides the outcome | rule.md bounded advantage, engine.md bounded misreading |
| Tension | A roll card's risk, target number and modifiers match execution, and hidden things never change the risk | rule.md risk independence, preview = execution |
| Consequence | A roll always changes something visible, and a failure changes a risk clock | rule.md rolls move forward |
| Relationships | A favor's promise ends as kept or broken by the next chapter change at the latest | rule.md 5.2 |
| Rhythm | Time passes with every action that has a check, and a threat whose `fill` the story never lowers arrives or retreats within `n · B` steps | rule.md time moves forward |
| Rhythm | The ending is reachable from wherever the player is | rule.md guaranteed ending |

## 3. Roll and time math

### 3.1 Outcome distribution

The modifier sum `z = stat(player, approach) + help − hinder` ranges from −1 to 4 (approaches are limited to `0…3`). Success is `2d6 + z ≥ DC`, where `DC` is 7, 8 or 9 depending on risk (rule.md 3.2). The table gives the success chance `chance(z, DC)`; the rest is failure.

| `z` | Low (7) | Normal (8) | High (9) |
|---|---|---|---|
| −1 | 41.7% | 27.8% | 16.7% |
| 0 | 58.3% | 41.7% | 27.8% |
| 1 | 72.2% | 58.3% | 41.7% |
| 2 | 83.3% | 72.2% | 58.3% |
| 3 | 91.7% | 83.3% | 72.2% |
| 4 | 97.2% | 91.7% | 83.3% |

- At normal risk with `z = 1`, success is 58%, and relying on one thing (+1) raises it to 72%. A failure always brings a cost the engine applies at once (a clock, plus a complication at normal and high risk), and this is the main source of consequence and tension.
- Even a strong approach (`z = 3, 4`) fails 17–28% of the time at high risk, so tension remains after growth.
- Relying on one thing (+1) raises success by 6–17 percentage points (14–17 at normal risk with `0 ≤ z ≤ 2`), so reading the situation and finding something to rely on pays off.

### 3.2 Risk clock rhythm

The expected amount one roll adds to a risk clock is `ρ = c · P(fail)`, where `c` is 1 at low or normal risk and 2 at high risk (rule.md 3.3). A clock with `n` boxes fills after about `n / ρ` rolls on average (a lower bound at high risk, which can overflow; the +1 from declarations is left out).

| `z` | `ρ` (low) | `ρ` (normal) | `ρ` (high) | Rolls at `n = 4` (normal) |
|---|---|---|---|---|
| 0 | 0.42 | 0.58 | 1.44 | ~6.9 |
| 1 | 0.28 | 0.42 | 1.17 | ~9.6 |
| 2 | 0.17 | 0.28 | 0.83 | ~14.4 |

The story sets `n` from this table. For one or two crises per chapter, `n · (1~2) ≈ ρ ×` the number of rolls expected in that chapter.

### 3.3 Chapter length

A scene ends within `B` beat-raising steps, and a deadline with `n_deadline` boxes arrives within `n_deadline` scenes. So a chapter never runs longer than `n_deadline · B` beat-raising steps. A deadline has at most 6 boxes, so the story sets the maximum chapter length through `B`. For a chapter to be able to last `l` steps or more, `B ≥ l / n_deadline` must hold (F10's 40 steps need `B ≥ 7` when `n_deadline = 6`).

## 4. Measurement

Every metric is computed offline from the saved log `L` (each event's `a`, `r`, `Δ`, `mods`) and the presentation layer's turn records; only the survey asks the player. Survey answers are kept separately, outside `S`, `L` and `P`. A game with no requests for 7 days after its last request counts as **abandoned**. The target ranges are first hypotheses, revised by the procedure in section 5.

| | Metric | Definition | First hypothesis | Where to fix if it misses |
|---|---|---|---|---|
| F1 | Interpretation acceptance (해석 수용) | Share of free sentences that do not end in a clarification, a refusal or `try(player)` | 85% or more | Interpretation rules, the story's names and synonyms |
| F2 | Free sentences (자유 문장) | Share of steps chosen by a sentence rather than a button | 50% or more | Suggested buttons are too good, or sentences are refused too often |
| F3 | Solution variety (해법의 다양성) | Number of distinct solutions and approaches used on each obstacle across plays | 2 or more | The story's solutions and fits |
| F4 | Roll outcomes (굴림의 결과) | Share of rolls that fail | 25–50% | Approach values, the story's base risk |
| F5 | Crisis spacing (위기의 간격) | Rolls between `τ_risk` (risk clock crises) | 4–8 | Risk clock boxes (3.2) |
| F6 | Threat response (위협 반응) | Share of threats that appeared whose `fill` the player lowered, or that the player drove back, before they arrived | 30–70% | Threat boxes, number of solutions |
| F7 | Consequence reuse (결과의 재사용) | Share of scars, declarations and fork choices that fall in a history pattern (extracted statically from the story) read by a condition evaluated later (ending, complication, topic) | 50% or more | The story's patterns and ending conditions |
| F8 | Relationship change (관계의 변화) | Per play, the number of people whose `regards` differ from the start, and the share of favor promises that end kept | 2 or more people, 40–80% | People's desires and favors |
| F9 | Ending spread (결말의 분산) | Entropy of the ending distribution over several plays of the same story, divided by its maximum | 0.5 or more | Forks and ending conditions |
| F10 | Chapter length (장의 길이) | Beat-raising steps per chapter, and the share of chapters ended by a deadline | 20–40 steps, 50% or less | `B`, deadline boxes |
| F11 | Dropout (이탈) | Share of games abandoned before an ending, and the chapter they were in | 20% or less in chapter 1 | Length of the first chapter and the steps before the first roll |
| F12 | Survey | 5-point scale after the ending: "내 선택이 이야기를 바꿨다" (my choices changed the story), "다시 하고 싶다" (I want to play again), "인물이 나를 기억했다" (the people remembered me) | Mean of 4 or more | The element (section 1) of the lowest-rated item |
| F13 | Relying (기대기) | Among rolls with something to rely on, the share where the player relied on it, and the share where the decisive chip was the relied-on thing | 30–70%, recorded | Low: things to rely on are not visible or feel too precious to spend; high: relying is free |
| F14 | Card abandonment (카드 이탈) | Share of roll cards closed in favor of a different command | 20% or less | The card shows something other than what the sentence meant → interpretation (engine.md section 3) |

| Element | Metrics |
|---|---|
| Agency | F1, F2, F3, F12, F13 |
| Tension | F4, F5, F6, F14 |
| Consequence | F7, F9 |
| Relationships | F8, F12 |
| Growth | F4 (trend by chapter), F12 |
| Rhythm | F5, F10, F11 |

## 5. Hypotheses and decisions

- **H1**: Failure and the cost the engine applies at once (F4) are the main source of consequence and tension. If F4 is out of range, F7 and the consequence item of F12 drop too.
- **H2**: If a sentence can freely set the approach, target, attitude and claim (engine.md 4.2) and is accepted reliably (F1), players write sentences (F2), and players who write sentences rate agency higher (F12).
- **H3**: If players can see deadlines and threats approaching, they respond (F6), and more chapters ending by deadline (F10) means more dropout (F11).
- **H4**: Promises and relationship change (F8) best explain "인물이 나를 기억했다" (the people remembered me, F12).

Decision procedure:

1. Measure metrics on newly collected plays before changing the story or the rules. Never measure a change on the plays used to make it.
2. Change one thing at a time, compare before and after on the same metrics, and report both.
3. If fitting one metric pushes another element's metric out of range, do not make the change.
4. If the metrics repeatedly refute a hypothesis, revise the hypothesis, not the target range.

Passing tests and on-target metrics only show the premises of fun. Fun itself is judged only by F12 and the logs of real play.
