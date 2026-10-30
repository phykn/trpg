# Rules

The rules fill in the candidates `K` and the transition `R`. A roll uses two six-sided dice, a target number set by risk, and the costs and complications of failure (section 3). Beats, scenes and threats move time forward (section 4). Conversation leaves relationships and promises behind (section 5). The protagonist has declarations, scars and growth (section 6). State and operations belong to [ontology.md](ontology.md); story parameters belong to [story.md](story.md).

```
server/src/rules/
  acts.py        action ids: parse, format, SCHEMAS
  candidates.py  K: candidates, space, admits
  roll.py        roll(H), risk, DC, modifiers, outcome, chance, preview
  costs.py       cost table, pool, settle
  schemas.py     Δ₀ per schema, scene_end
  triggers.py    scan, engine triggers, chapter_to, end
  resolve.py     R = Δ₀ → triggers → Step
  recommend.py   recommended buttons
```

`rules/` holds only pure functions. They never read the clock time, random numbers, files, models or the presentation layer.

## 1. Actions

Actions travel as the ids of story.md 3.12. Inside the server they are `Action`.

```python
@dataclass(frozen=True)
class Action:
    schema: str                     # go, look, take, give, show, talk, try, declare, cut, choose, grow
    intent: tuple[str, ...]         # intent arguments in schema order
    judge: tuple[tuple[str, str], ...]  # non-neutral judgment arguments, sorted by key
```

**Canonical form**: judgment arguments are written in key order, and those at their default `ν₀` are left out. `parse(format(a)) = a`, and `format(parse(s))` is canonical. Receipts, logs, patterns and buttons all use only the canonical form.

| Schema | What it does | Intent arguments | Judgment arguments (`ν₀`) |
|---|---|---|---|
| `go` | Moves to a connected place | destination | - |
| `look` | Examines something to learn propositions | target | - |
| `take` | Picks up a thing in the place | thing | - |
| `give` | Hands over a carried thing | thing, recipient | - |
| `show` | Shows a carried thing and keeps it (5.1) | thing, person | - |
| `talk` | Conversation (section 5) | other party, topic | `tone`(`polite`), `claim`(none), `rely`(none) |
| `try` | Improvised attempt (section 3) | target, approach | `strain`(`natural`), `rely`(none). `try(player, ·)` takes only `ν₀` |
| `declare` | Declares a latent (section 6) | latent | - |
| `cut` | Skips ahead past the scene (section 4) | `pass` or `rest` | - |
| `choose` | Picks one option at a fork (section 4) | fork, option | - |
| `grow` | Growth (section 6) | `grow:<approach>`, `grow:trait:<drop>:<gain>`, `grow:scar:<slot>` | - |

The old schema `pay` survives only in the action-id grammar (`acts.py`) so that saves from before this rule still load. It has no candidates and no `Δ₀`.

**Intent arguments** say what the player means to do; **judgment arguments** say how the action is carried out. `ν₀` creates no help, no added risk and no `spent`. Every argument ranges over a finite kind, so the set of actions is finite. The schema table `SCHEMAS` holds, for each schema, the kinds of its intent arguments, the keys of its judgment arguments, the function that decides whether it rolls, and the key of its action-name template.

## 2. Candidates `K`

`candidates(U, O) → list[Action]` reads only the observation `O = (E, F, B, hᵥ)` and story constants. Candidates come in schema-table order, and within a schema in the story's declaration order.

**Visible blocks**: `x` is visibly blocked when an obstacle `o ∈ E` lists `x` in its story `blocks`, `F` has `at(o, ·)`, and `fill(o) < boxes(o)`. `go`, `take`, `give`, `talk` and `try` that take a visibly blocked `x` as an argument are not candidates: a guard that keeps you from talking to someone also keeps you from handing them things (play: `refuse-1-play`). Hidden blocks do not shrink the candidates.

| Schema | Candidates |
|---|---|
| `go(q)` | `link(here, q) ∈ F`, `q ∈ E` |
| `look(x)` | `x ∈ E`, `x ≠ player` |
| `take(x)` | `x` is a thing and `at(x, here) ∈ F` |
| `give(x, h)` | a thing `x` with `at(x, player) ∈ F`, and a character `h` with `at(h, here) ∈ F` |
| `show(x, h)` | as `give` |
| `talk(h, topic)` | a character `h` with `at(h, here) ∈ F`. Topics are `h`'s topics, `favor` (`h` has a favor, `favor:h ∉ hᵥ`, and there is no `owes(player, h, ·)`), `come` (`follows(h, player) ∉ F`), `stay` (`follows(h, player) ∈ F`), and `chat` |
| `try(x, approach)` | `x = player` (all judgment arguments `ν₀`); or a `plain` obstacle `x ∈ E` with `fill < boxes` (clocks, deadlines, threats and forks are not targets); or any other `x ∈ E` with an empty tag slot or a `snag` |
| `declare(ℓ)` | `believes(player, ℓ) ∉ F` and `ℓ.when` is true in the view |
| `cut(pass)` | always |
| `cut(rest)` | `here` is a resting place |
| `choose(g, c)` | an option `c` of a fork `g` with `at(g, player) ∈ F` |
| `grow(item)` | `growth ≥ 1`. Approaches below 3; for a trait, one trait the player has now paired with one other trait candidate from the story; for a scar, its slot |

Judgment arguments multiply onto the actions above.

| Judgment argument | Applies to | Values |
|---|---|---|
| `tone` | `talk` | `polite`, `threaten`, `deceive`. Friendliness and pleading are polite; the narration reads them from the sentence |
| `claim` | `talk`, only when `tone = deceive` | The story's claims. A claim is a false proposition, so it cannot be made in an honest tone |
| `strain` | `try(x ≠ player)` | `natural`, `forced` |
| `rely` | a rolling `talk`, `try(x ≠ player)` | See the table below. The rules never ask whether it is relevant: a free value helps and a spent one guards (3.2). The roll card shows only the ones relevant to this roll (engine.md 4.2) |

| `rely` value | Condition | Help atom | Consumed |
|---|---|---|---|
| `tag:<x>:<slot>` | `x` is in reach (3.2), and `mark(x, edge, ·, slot) ∈ F` | that `mark` | `untag` after the roll |
| `trait:<id>` | a trait the player has, with `spent(player, id) ∉ F` | `stat(player, id, 1)` | `insert(spent(player, id))` after the roll, whatever the result |
| `thing:<id>` | `at(id, player) ∈ F`, with `spent(player, id) ∉ F` | that `at` | `insert(spent(player, id))` after the roll, whatever the result |
| `prop:<id>` | `id ∈ B`, with `spent(player, id) ∉ F` | `believes(player, id)` | `insert(spent(player, id))` after the roll, whatever the result |
| `bond:<h>` | `regards(h, player, trust, 3) ∈ F` (a bond) | that `regards` | nothing (free) |
| `with:<h>` | `follows(h, player) ∈ F` (a companion), and `h` is not the target | that `follows` | nothing (free) |

What the player has (a trait, a thing, a belief) is spent until the chapter changes once leaned on; who stands with the player (a bond, a companion) is not, and an edge tag is removed instead. Things and beliefs used to cost nothing: one letter gave +1 to any roll, the relying share (fun.md F13) was 0.67–1.0, and four games leaned on the letter 13 times, the oil 5 and a trait never, because a trait used up for the chapter lost to a free letter every time (play-5-bold 9, play-5-odd 25).

**Free help, spent guard.** A free value (`bond`, `with`) adds help 1 to the roll. A spent one (`tag`, `trait`, `thing`, `prop`) adds nothing; it **guards**: a fail costs what a `low` fail costs (3.3). When both added 1, the companion was free and dominated every spent reliance, and "lean on the letter" and "bring 윤슬" were one decision under two names.

**Once an ending is set**, the candidates are empty and the game is over. `try(player, ·)` is always a candidate, so `K ≠ ∅` before the ending (progress).

Because judgment arguments multiply, `K` gets large, so the engine never expands it in full. `space(U, O)` returns, per schema, a list with only the intent arguments expanded, plus the allowed values of each judgment argument. `admits(U, O, a)` decides `a ∈ K(O)`. Both use the same condition functions. Interpretation questions and the roll card (engine.md 3–4) use `space`; the admission check right before execution uses `admits`.

**Solutions** add no candidates. A solution is a single action id, `try(o, approach)` with `rely` filled in, plus a `label` and a condition `when`. When `when` (and the conditions `rely` implicitly adds) is true in the view, that action is named `label`. The same action id goes through the same `R` whether or not a solution exists.

## 3. Rolls

### 3.1 Dice

```python
def roll(seed: int, t: int) -> tuple[int, int, int]:
    b = hashlib.sha256(f"{seed}:{t}".encode()).digest()
    n = lambda i: int.from_bytes(b[i:i + 8], "big")
    return n(0) % 6 + 1, n(8) % 6 + 1, n(16) % 60
```

`r = (d₁, d₂, u)`. `seed` is set with `secrets.randbits(63)` when the game is created. The modulo bias is on the order of `10⁻¹⁷` and is ignored. `R` takes `r` as an argument, so witnesses and tests supply the dice directly.

```
total = d₁ + d₂ + stat(player, approach) + help − hinder        talk's approach: force to threaten, wits to deceive, else charm
result = success (total ≥ DC(risk)) | fail (total < DC(risk))
```

### 3.2 Risk, modifiers and results

```python
DC = {low: 7, normal: 8, high: 9}       # the total to reach, by risk
def risk(U, a) -> Risk                   # reads only U and a
def modifiers(U, facts, a) -> Mods       # stat, help, hinder and the atoms behind them
def band(total, dc) -> Result            # success if total >= dc, else fail
def outcome(r, mods, risk) -> Result     # band(d1 + d2 + z, DC[risk])
def chance(z, dc) -> float               # P(2d6 + z >= dc)
```

**Risk** reads only story parameters and the arguments of `a`. So it is the same in two states that differ only in hidden atoms, and the same for every `rely` option. Hidden parts of `S`, such as a hidden guard, never enter the risk; the player runs into them by acting. Judgment arguments can only raise risk.

```
risk(try(player, ·))            = low
risk(try(o, approach, strain))  = min(high, base(o) + [approach ∈ clashes(o)] + [strain = forced])
risk(talk(h, ·, tone))          = min(high, normal + [tone ∈ {threaten, deceive}])
risk(choose(·))                 = high          (irreversible; it does not roll, so this only puts up the confirm card, engine.md 4.3)
risk(anything else)             = low
```

`base(o)` is the obstacle's `risk` (`low` or `normal`), or `normal` when the target is not an obstacle.

The atoms of the **modifiers** become the event's `mods`, in this order.

| Modifier | Value | Atoms |
|---|---|---|
| `stat` | the value of `stat(player, approach)` | that `stat` atom |
| help | 1 with a free `rely` (`bond`, `with`), otherwise 0 | one atom from the table in section 2 |
| guard | 0; a fail costs the `low` row (3.3) | the atom of a spent `rely`. The event also records the happening `("guard",)`, since saves from before this rule counted the same atom as help |
| hinder | 1 if any atom below exists, otherwise 0 | every `snag` `mark` in reach. In `talk`, a `regards` in which the other party's relevant axis toward the player (`fear` for `threaten`, otherwise `trust`) is negative |

With charm alone for every talk, the creation screen decided how every person could be met; a threat pressed with force and a lie told with wits give each build a social lever, priced in regard (5.1).

Help and hinder are each 0 or 1 however many atoms there are, so a roll's `help − hinder` is −1, 0 or +1 (bounded advantage). The client shows them as chips (api.md 3).

Tags count when they are **in reach**: on the target, `here`, the player, or a thing the player carries. A carried thing used to be out of reach, so an edge won by readying the oil helped only a roll on the oil itself and expired unused through three rolls on the lamp (play-5-explorer 34, 38, 40).

`modifiers` reads only the atoms passed in `facts`. `R` passes `S`; the preview passes `F`. Every atom the modifiers read is either a `mark`, `stat` or `regards` about an entity in `E` (the target, `here`, the player, a carried thing, the other party present) or an atom of `F` or `B` that `rely` points to. So for a rolling action `a ∈ K(O)`, `modifiers(U, S, a) = modifiers(U, F, a)`.

`outcome`, `chance` and the step record's `dc` (api.md 3) all come from the one `DC`.

### 3.3 Costs and complications

A **complication** is `(condition, effect, weight)`. The story declares them on places, characters and obstacles (story.md 3.6), and the engine keeps two unconditional ones per weight.

| Weight | Engine complication | Name (`locale/ko.py`) | Effect |
|---|---|---|---|
| `light` | `engine.snag` | 꼬임 (snag) | `snag` scene tag on the player |
| | `engine.beat` | 지체 (delay) | `beats +1` |
| `heavy` | `engine.wound` | 다침 (injury) | `wounds +1` |
| | `engine.end` | 끊긴 장면 (scene cut short) | scene end (4.1) |

A story complication's effect is its `effects`, plus `wounds +n` when it has `wound: n`. **Costs apply only on `fail`**. Risk sets them, and the engine applies them at once. The player does not choose.

| Risk | Cost of `fail` |
|---|---|
| `low` | clock +1 |
| `normal` | clock +1, light |
| `high` | clock +2, heavy |

A **guarded** roll (3.2) that fails pays the `low` row whatever its risk: clock +1 and no complication.

**The pool** `pool(weight, target)`: the two engine complications (in the order of the table above), then the story's, in this order: the place (`here`), characters (those at `here`, in story order), the obstacle (the roll's target). Story complications must pass the implicit condition of what they are attached to and their `when`. The engine's have no condition, so the pool always holds at least two.

**Applying**: when there is a weight, evaluate `when` in the world `(S, h)` and put the effect of entry `u mod count` of the resulting list into `Δ₀`. A complication is discovered by suffering it, so hidden ones may be picked; that is why the preview states only the weight.

`settle(U, work, result, risk, u, target, h)` on `fail` puts one row of the cost table (the increase on the held clock) into `work` and returns the chosen complication, whose effect the caller applies. On `success` it does nothing.

### 3.4 Preview

```python
def preview(U, O, a) -> Preview
```

For a rolling action `a ∈ K(O)`, this computes from the observation alone what the player sees before rolling. The roll card (engine.md 4.2) uses it.

| Field | Value |
|---|---|
| `risk` | `risk(U, a)` |
| `mods` | `modifiers(U, O.facts, a)` as the chip list of api.md 3 (`kind`, `label`, `value`). Same shape and order as the step record's `mods` |
| `z` | `stat + help − hinder` |
| `dc` | `DC[risk]` |
| `stakes` | The cost of failure: `clock` is the boxes the held clock would fill (`min(n, remaining boxes)`, 0 with no clock); `weight` is the complication weight (null if none). A guarded roll states the `low` row |
| `clock` | the held risk clock's id, name, box count and `fill` |
| `gain` | What happens to the target on success: for an obstacle, `min(1 + [approach ∈ fits] + [strain = forced], remaining boxes)` boxes, and how many of them the fit and the forcing buy; for any other `try`, removing the lowest-slot `snag` (its name) or an `edge` scene tag; for `talk`, the topic's reveal or the favor's effects (names) |

**The preview matches execution.** Risk is a function of the story and `a`, and the modifiers are the same on `S` and `F` (end of 3.2), so when the roll happens, its `z`, `mods` and risk equal the preview's. Only two things differ: a hidden block stops the roll (`blocked`, and nothing relied on is consumed), and the failure complication may be a hidden one (3.3).

## 4. Time

### 4.1 Beats and scenes

**Beats** `stat(player, beats, n)`, `0 ≤ n ≤ B`. A beat is a move or a roll: `go`, a `try(x ≠ player)`, a `talk` that rolls, and any step a hidden block stopped add `beats +1` in `Δ₀`, before the step's effects, so a scene the step ends starts at zero. Looking, taking, giving, showing, declaring, choosing, small talk, `try(player, ·)`, `grow` and `cut` cost none, and `B` reads as "B attempts a scene". When looking and taking cost a beat, a player who walked the map and looked at each thing once had spent 10 of the chapter's 18 before a roll. **Small talk** is `talk(h, chat)` whose tone is neither `threaten` nor `deceive`: it changes nothing in the world, and when every greeting cost a beat, players stopped speaking to people (play-5-talker 1–2). Growth is picked on a card, not done in the scene; when it spent a beat, levelling up read as a penalty for pressing the button (play-5-bold 7).

**Scene end** `scene_end`: `expire(scene)`, `beats = 0`, and `fill +1` on each active threat (a threat, fork or deadline with `at(w, player)`). Risk clocks are not included. `go` does not expire scene tags.

`cut(pass)` ends the scene at once ("밤이 될 때까지 기다린다", "I wait until nightfall"). `cut(rest)` is a candidate only when `here` is a resting place; on top of the scene end it does `wounds −1` and one more `fill +1` on active threats.

### 4.2 Risk clocks and threats

In each chapter the player holds one risk clock `clock.k`. Only roll costs and declarations raise a clock's `fill`; only `τ_risk` lowers it; only a chapter change moves it.

A **threat** is an obstacle with an arrival effect. When the player holds it (`at(w, player)`) it is **active**: it is visible and draws closer at every scene end. An appearance trigger's `move(w, player)` brings it in, and story effects can lower its `fill` or `retire` it. A **fork** is a threat with options and a default option. `choose(g, c)` applies `c`'s effects and retires `g`; holding out without choosing lets it arrive, and the default option happens. Ending conditions read which choice was made through history patterns.

A **deadline** `deadline.k` is a threat, one per chapter, whose arrival effect unconditionally brings a chapter change or an ending. The first chapter's deadline is active from the start; later ones become active at a chapter change.

### 4.3 Chapter changes and endings

`chapter_to(k)` is a single sequence of operations.

1. `set(flag, chapter, k)`, `expire(chapter)`, `expire(scene)`, `beats = 0`: a new chapter starts a new scene, without a scene end's threat ticks
2. `clear_spent(player)`
3. `retire(clock.k−1)`, `retire(deadline.k−1)`, `move(clock.k, player)`, `move(deadline.k, player)`
4. `growth +1`, and when the change comes from reaching the goal, the story's `goal_effects`

A chapter used to begin inside the scene that ended the last one: the spray of the yard, shown as lasting "이번 장면", followed the player into the lamp room and the next chapter and still hindered a roll there, and the new chapter's clocks began with half a box spent (play-5-bold 6, 8).

When the change comes from the deadline's arrival instead (the goal was missed), step 3 also does `fill +1` on `deadline.k` if it has more than one box: being late costs time in the next chapter, and that is its one cost. A missed goal once opened the same growth as a reached one with a cost nothing named (play-2-explorer 33, play-2-talker 27, play-2-odd 33; play-4-explorer 29, 41); withholding growth as well then punished a losing player twice, and a lost chapter is where a protagonist learns.

`end(e)` does `set(flag, ending, e)` and stops that step's trigger scan. Neither a chapter change nor an ending settles promises (5.2). When the chapter goal becomes true in `Δ₀`, story triggers are scanned before engine triggers, so even if the previous clock filled up in the same step, that clock retires without `τ_risk`.

## 5. People

### 5.1 Talking and giving

The axes of `regards(g, h, axis, n)` are `trust` and `fear`. The **relationship** in a talk roll is the other party's value toward the player: `fear` for `threaten`, `trust` otherwise. It counts as hinder only when negative; a positive one is relied on as a bond (`trust` 3).

`Δ₀` of `talk(h, topic, tone, claim, rely)` is built in this order.

1. **Hidden block**: if a hidden obstacle blocks `h`, reveal it and stop.
2. **Whether to roll** (judged on the view; inside `R`, `fact_rule` builds `F` from `S` and makes the same judgment): no roll if the topic is a proposition the player already believes, `free_when` is true, the topic is `chat` or `stay`, it is a favor with `owes(h, player, kindness)`, or it is `come` with `regards(h, player, trust) ≥ 1`. Other topics, favors and `come` roll.
3. **Result**: an unrolled topic is revealed (`x.hidden` for `reveals: x`, otherwise the topic id); a favor granted out of kindness applies the favor's effects and `retract(owes(h, player, kindness))`. When rolled, `success` reveals the topic, or applies the favor's effects and, unless the tone was `threaten` or `deceive`, `insert(owes(player, h, promise))`: fear pays instead of trust, and a lie owes nothing. `come` does `insert(follows(h, player))` when unrolled or on `success`; `stay` does `retract(follows(h, player))`. Costs follow 3.3. A rolled talk that fails also reveals what would move `h`: `reveal(player, h.desire)`, the engine proposition "{name}은 {desire}" from the story's `desire`, so the next attempt is informed instead of repeated.
4. **Trust and tone**: a rolled talk that succeeds gives `regards(h, player, trust) +1`, unless its tone is `threaten` or its lie is caught. `threaten` gives `regards(h, player, fear) +1` and `trust −1` whatever the result. With `deceive`, if `h` believes the `claim`'s `against`, the lie is caught: `trust −2`, and a `snag` chapter tag on the player (default name "의심", "suspicion"). A claim that matches no story proposition remains only as text. Before, only gifts, kept promises and forks moved trust, so a person the player had won over in a roll stayed as they were: in four games no one's regard moved and no ending named a person (play-6, F8 = 0 in 4 of 4; play-6-explorer 5, 17).
5. **Favor count**: for each character the engine adds a pattern `favor:h` (action `talk:h:favor`, results `success` or `none`) to `Pat`. A step that grants the favor matches this pattern, and candidates offer no favor once `favor:h ∈ hᵥ`. Candidates read only `F` and `hᵥ`, so they use visible history instead of a story flag.

**Companions**: a character with `follows(h, player)` moves along when the player moves (ontology.md 4, `move`). They do not follow into places in the story's `avoids` (story.md 3.4). If the player does `go` there, `h` stays behind and `follows` is removed. The player can bring someone along without a favor, but someone who does not yet trust the player has to be won over with charm. A companion helps every roll not aimed at them (`with:<h>`, section 2). Before, a companion only walked along: pushing the door together gave the same odds as alone, and testers who had talked someone into coming found it changed nothing (play-4-talker 17, 33; play-2-talker 29–36).

`give(x, h)` is `move(x, h)`; if `x ∈ wants(h)`, it also does `regards(h, player, trust) +1` and `insert(owes(h, player, kindness))`.

`show(x, h)` moves nothing and never rolls. A hidden block on `h` is revealed first. If `x ∈ wants(h)` and the engine pattern `show:x:h` is not in `h` (it is shown once), `regards(h, player, trust) +1`. Players who only wanted to show the letter gave it away, and the confirm card asked again in every round (play-3-talker 3, play-4-talker 7).

### 5.2 Promises

`owes(g, h, k)`: `g` owes `h` a `k`. `k` is `promise` (a promise tied to `h`'s favor, whose `keep` and `break` conditions are read from `h`'s `favor.promise`) or `kindness` (a good turn). Each character has one favor, so `owes(player, h, promise)` pins down the promise. The player makes promises only through favors.

- **Kept**: `retract(owes)`, `regards(h, player, trust) +1`.
- **Broken**: `retract(owes)`, `trust −2`, and a `snag` chapter tag on the player (default name "약속을 어김", "broke a promise"). A promise broken in a step that also changes the chapter is settled after the change, so its tag carries into the next chapter.

`τ_promise` (section 8) settles a promise when its `keep` or `break` becomes true, and nothing else does. An open promise carries across chapter changes; at the ending it is still owed and becomes a legacy line (engine.md 5.5). A story that wants a promise due by some point writes that point into the promise's `name` and `break`, where the player can see it.

Earlier, every chapter change and the ending settled open promises by `keep`. The due was on no screen, and the step that reached the goal was the one that changed the chapter, so a promise was broken in the very step the player succeeded: the key borrowed to light the lamp was "broken" when the lamp lit, after the bridge had cut the way back (play-4-talker 31, 40, 47). The player had promised to return it after the lamp was lit.

## 6. The protagonist

- **Declaration** `declare(ℓ)`: `reveal(player, ℓ)`, `ℓ.effects`, held clock `+1`. When the player says "옛 친구가 이 마을에 산다" ("an old friend lives in this town"), it looks as if a fact is added to the world, but all that happens is that a latent the story placed from the start comes to light (the scope rule of story.md 3.10).
- **Scar** `τ_fall`: `wounds = 0`, `tag(player, snag, scar)`, scene end. When picking a slot to overwrite, `tag` skips `scar` slots, and adds nothing if only those remain. If all the player's slots are `scar` at the end of that trigger's effects, `end(collapse)`. The story supplies the name and narration template of `collapse`.
- **Growth** `grow(item)`: a candidate only when `growth ≥ 1`, and does `growth −1`. The item is one of: `+1` to one approach, a trait swap (remove one `stat` atom and add another), or `untag` of one scar. Reaching a chapter's goal opens growth (4.3).

## 7. Schema results `Δ₀`

`schemas.py` produces `Δ₀` for each schema as a sequence of operations on the working copy. A rolling step decides its result first, then applies the effects.

| Schema | `Δ₀` |
|---|---|
| (all) | a move or a roll, and any step a hidden block stopped (4.1), does `beats +1` |
| `go(q)` | If a hidden obstacle blocks `q`, `reveal(player, o.hidden)` (`blocked`). Otherwise `retract(follows(h, player))` for each companion `h` with `q ∈ avoids(h)`, then `move(player, q)` (the remaining companions move along) |
| `look(x)` | `reveal` each story proposition `p` with `x ∈ about(p)`, in story order |
| `take(x)` | A hidden block is revealed. Otherwise `move(x, player)` |
| `give(x, h)` | 5.1 |
| `show(x, h)` | 5.1 |
| `talk(h, topic)` | 5.1 |
| `try(player, ·)` | Nothing. Triggers are not scanned either |
| `try(o, approach)` | A hidden block is revealed (no roll). Otherwise roll. On `success`, an obstacle gets `fill +(1 + [approach ∈ fits(o)] + [strain = forced])`, capped by what is left: forcing keeps its risk step and heavy fail, so it must buy something; any other target has its lowest-slot `snag` `untag`ged, or, if there is none, gets `tag(o, edge, scene)`. Costs follow 3.3 |
| `declare(ℓ)` | section 6 |
| `cut(pass)` | scene end |
| `cut(rest)` | scene end, `wounds −1`, active threats `fill +1` |
| `choose(g, c)` | `c.effects`, `retire(g)` |
| `grow(item)` | section 6 |

After the roll, **what was relied on is consumed** as in the table in section 2. A rolling step always raises `beats`, `success` changes the target and `fail` changes the clock, so no roll ever ends in "아무 일도 없었습니다" ("nothing happened").

## 8. Triggers and `R`

A trigger is an ordered `(condition, effect)`. Story triggers (in the order of ontology.md 5.3) are **edge-fired**: each fires at most once per step and, unless it is `repeat`, once per game through its fired flag. After them come five engine triggers, in this order, which are **level-fired**.

| Trigger | Condition | Effect |
|---|---|---|
| `τ_risk` | the held clock is full | that chapter's `crisis`, clock `fill = 0` |
| `τ_fall` | `wounds = wound_boxes` | scar (section 6) |
| `τ_scene` | `beats = B` | scene end |
| `τ_arrive` | some active threat is full | for each such threat, in story order, its arrival effect (`arrival` for a threat, `default` for a fork, `chapter_to` or `end` for a deadline), then `retire` |
| `τ_promise` | some `owes(player, ·, promise)` has `keep` or `break` true | settled as in 5.2. If both are true, the promise is kept |

```python
def resolve(U, S, h, a, r) -> Step:
    # Step(delta, mods, rolled, result, risk); never mutates S
```

1. `work = Work(S)`. For each story trigger, `start_true[i] = holds(τᵢ.when, S, h)`.
2. Apply the schema's `Δ₀` to `work` (section 7). This decides the roll's `result`.
3. `h* = h ∪ { π | matches(π, a, result) }`. `a` and `result` do not change within a step, so this is computed once.
4. **Scan** `scan`: walk the list in order, apply the effect of the first trigger that fires to `work`, and go back to the top of the list. Stop when nothing fires, and stop at once when `flag ending` is set. A story trigger `τᵢ` fires when it has not fired this step, `start_true[i]` is false and `holds(τᵢ.when, work, h*)` is true. An engine trigger fires when its condition is true in `work`.
5. `delta = diff(S, work)`. `mods` are the atoms of 3.2.

The scan ends after at most `m + 3 + w + q` firings and is deterministic: `m` story triggers, one firing each of `τ_risk`, `τ_fall` and `τ_scene`, `w` arrivals (threats, forks, deadlines) and `q` promise settlements. Effects after `Δ₀` raise no clock, beats or wounds, arrivals retire their threats, and settling a promise removes its `owes`, so none fires twice. The code raises an exception past that bound; it is a bug that fuzzing (story.md V6) should catch. At the end every engine trigger condition is false, so every step starts with no clock full.

`Step.result` is one of `success`, `fail` (rolled), `none` (done without a roll) or `blocked` (a hidden block was revealed), and it is stored in the event. `risk` is recomputed from `a`, so it is not stored.

## 9. Recommended buttons

`recommend(U, O) → list[Action]`, at most three. It picks them one at a time, in this order.

- **Tag**: a `try` that relies on an `edge` tag on the player or `here`, if there is one. The target is the first active obstacle in story order; the approach is the solution's approach if there is a solution, otherwise the player's highest approach
- **Talk**: the first topic, in story order, of the character present that the player does not yet believe
- **Forward**: if a fork is active, `choose` its first option. Otherwise the first solution whose `when` is true in the view, or failing that, the first `go` toward a place named in the chapter goal's condition. A chapter with no goal ends in an ending, so its places are those of the obstacles the endings' conditions fill

The same list feeds the hint a muse reply ends on (engine.md 5.2).

Every judgment argument on a button is `ν₀`, except the `rely` that defines the button (the solution's `rely`, or the tag). Anyone can pick what to rely on in the roll card (engine.md 4.2), so a typed sentence differs from a button only in freely setting the approach, target, tone and claim (fun.md H2 measures this).

## 10. Properties and checks

| Property | What and why | Enforced by | Check |
|---|---|---|---|
| Admission check | `a ∈ K(Vₜ)` before it touches the state. Includes buttons, cards and the API | the service runs `admits` then `resolve` on every step (engine.md 7) | ids outside the candidates, ids from stale cards → rejected |
| Progress | `try(player, ·)` is always a candidate before the ending | `candidates` | `space` is non-empty at every fuzzed step (before the ending) |
| Neutral value | `ν₀` creates no help, added risk or `spent`, and `try(player)` has `Δ = ∅` | sections 1 and 7 | results of actions with every judgment argument at `ν₀` |
| Bounded advantage | help and hinder rest on atoms of `F` or `B` and are each 0 or 1. A `try` success changes only `fill` and `mark`; things, propositions and paths move only through story effects and `take`, `give`, `look` and `talk` | `modifiers`, section 7 | a target with several tags → hinder 1 |
| Risk independence | `risk` reads only `(U, a)` | the signature of `risk` | two states that differ only in hidden atoms → same risk |
| Preview = execution | 3.4 | `preview`, `modifiers` | at every rolled step under fuzzing, `preview`'s `z`, `mods`, `risk` = the `Step`'s, and `result = band(total, dc)`; `chance(z, dc)` matches the enumerated 2d6 distribution (boundary unit tests per risk) |
| Argument kinds | the arguments of `take`, `give` and `rely=thing:` are things. Clocks are never arguments | `candidates` | ids that give or rely on a clock → rejected |
| Trigger termination | the bound in section 8 | `scan` | no exception under fuzzing |
| Rolls move forward | a rolled step changes something visible, and `fail` changes the clock (section 7) | `schemas.py` | at every rolled step under fuzzing, the player's visible atoms change |
| Time moves forward | a scene ends within `B` steps other than `try(player)`, and an active threat with `n` boxes arrives or retires within `n·B` such steps unless an effect lowers its `fill` | section 4 | fuzzing |
| Guaranteed ending | in any configuration, `cut(pass)` alone reaches an ending within `1 + Σₖ nₖ` steps (the box counts of the remaining chapters' deadlines). No dice involved | the structure of story.md (a deadline in every chapter, and the last one leads to an ending) | startup validation checks only the structure |
| Story properties | the grammar of clocks and triggers, isolation of latents, witnesses | story.md 4 | startup validation |
