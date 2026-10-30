# Story format

The story files are the whole story; the engine code contains none of it. This document defines the file format of `scenarios/<folder>/` and the validation run at startup. The smallest story that follows this format is [scenarios/skeleton/story.yaml](../scenarios/skeleton/story.yaml).

```
scenarios/<folder>/   any folder name; the story id is the id in story.yaml
  story.yaml    the whole story: world, style, witnesses
  evals.yaml    interpretation eval sentences (test data, not part of the story)
```

## 1. Principles

The format has no field for anything a story must not write. Chapter transitions, endings, clocks and deadlines, threat appearances and latent entities are fields that story effects cannot touch, and the engine builds the triggers and effects from those fields. A story changes the world only through the effect operations in 2.4, and its only actions are solutions: a `try` with a name and a condition attached. So most of the structure the rules require holds by grammar, and what is left to checks is section 4. One story is one file in one format.

## 2. Common

### 2.1 Files

- Written in a subset of YAML 1.2. No anchors, aliases or tags, and scalars are read only as the type the schema specifies (`no` and `on` are strings). **Map order is part of the format**, and the loader keeps the document's order. The order of triggers, endings and complications comes from this. Comments are written in Korean.
- **An id is a map key.** Everything that has an id (places, characters, things, obstacles, threats, forks, solutions, complications, topics, beliefs, claims, latents, choices, triggers, endings, traits) is written as a map key, with no separate `id` field. Ids use lowercase letters, digits and `_`, and are unique across the whole story. The reserved ids are `player` (`p★`), `chat`, `favor`, `come`, `stay`, `pass`, `rest`, `chapter`, `ending`, `collapse` (only in the endings section), `promise`, `kindness`, `full`, and anything starting with `fired_`.
- Every place, character, thing, obstacle, threat and fork has a `name`; `aliases` is optional. The engine's frame tables use these names to write and read facts and changes (engine.md 1). Aliases never overlap anywhere in the story.
- All text except proposition sentences (2.5) is a **public parameter**: `premise`, `style`, names and aliases, `senses`, `look`, `voice`, `desire`, `fear`, `knows`, a trait's `text`, a topic's `title`, `label`, the `name` of complications, choices, default choices, promises, latents, clocks and deadlines, a claim's `text`, and an ending's `title` and `frame`. Anything to be hidden goes only in proposition sentences.

### 2.2 Engine vocabulary

| Value kind | id (Korean) |
|---|---|
| Approach | `force` 완력, `finesse` 솜씨, `wits` 재치, `charm` 매력 |
| Risk | `low` 낮음, `normal` 보통 (an obstacle's default risk; `high` comes only from the rules, rule.md 3.2) |
| Tone | `polite` 정중, `threaten` 위협, `deceive` 속임 |
| Strain | `natural` 자연스러움, `forced` 무리 |
| Axis | `trust` 신뢰, `fear` 두려움 |
| Tag | `edge` 유리, `snag` 불리 |
| Lifetime | `scene` 장면, `chapter` 장 (the permanent `scar` is for the engine's scars only) |
| Weight | `light` 가벼움, `heavy` 무거움 |
| Result | `success` 성공, `fail` 실패, `none` 굴림 없이 이룸 (done without a roll), `blocked` 막힘. `mixed` is not a result |

### 2.3 Conditions

A condition is a sentence with no variables, written as a single-key map.

| Form | Meaning |
|---|---|
| `{at: [x, y]}` | `at(x, y)` |
| `{link: [p, q]}` | `link(p, q)` |
| `{believes: [g, p]}` | `believes(g, p)`. `p` is a proposition id (2.5) |
| `{fill: [o, cmp, n]}` | `fill(o, m)` and `m cmp n`. `full` (the box count) may stand in for `n` |
| `{regards: [g, h, axis, cmp, n]}` | `regards(g, h, axis, m)` and `m cmp n` |
| `{mark: [x, tag]}` | `x` has a `mark` of that tag |
| `{owes: [g, h, k]}` | `owes(g, h, k)`. `k` is `promise` (a favor's promise) or `kindness` (a kindness done) |
| `{flag: [name, value]}` | `flag(name, value)`. The name is one declared in `flags` (3.1), or `chapter` (the chapter number) |
| `{did: [action id prefix]}`, `{did: [action id prefix, result]}` | History pattern |
| `{all: [...]}`, `{any: [...]}`, `{not: c}` | Grouping. `{all: []}` is true, `{any: []}` is false |

The comparisons are `=`, `>=`, `<=`, `>` and `<`. Where a condition sits decides what it is evaluated against (the "Evaluated" column in the section 3 tables). **Visible** means `(F, hᵥ)` plus story constants; **world** means `(S, h)` (ontology.md 3.3).

`did` is a history pattern. It matches an event when the event's action id starts with the prefix, compared piece by piece on the intent arguments split by `:`; every judgment argument (`;key=value`) written in the prefix is equal; and, if a result is given, the result is equal. All the `did`s in a story make up its pattern set.

### 2.4 Effects

An effect is a sequence of operations, composed in order, each one reading the state the earlier ones left (ontology.md 4). These are the only operations a story can use.

| Form | Operation | Target |
|---|---|---|
| `{move: [x, y]}` | `move(x, y)` | `x`: a thing, a character, or `player` (then `y` is a place) |
| `{set: [fill, o, v]}` | `set_(fill, o, v)` | Obstacle, threat, fork |
| `{set: [regards, g, h, axis, v]}` | `set_(regards, …)` | Character |
| `{set: [flag, name, v]}` | `set_(flag, …)` | A flag declared in `flags`, with a value among the declared ones |
| `{reveal: [g, p]}` | `reveal(g, p)` | Proposition |
| `{tag: [x, tag, lifetime, default name]}` | `tag(x, tag, lifetime)` | The lifetime is `scene` or `chapter`. The default name is used until narration names the tag. A snag's name says what goes wrong and an edge's what helps: a snag named "흔들리는 불꽃" read as the lamp catching (goal-6-odd 50) |
| `{link: [p, q]}`, `{unlink: [p, q]}` | `link`, `unlink` | Places |
| `{retire: o}` | `retire(o)` | Obstacle, threat, fork |

`v` is a value, or `"+n"` / `"-n"` for an integer value. A relative value is added to the value at the moment it applies and stops at the limit. This lets an effect lower a threat's `fill` without knowing its current value.

What this table leaves out is the format's safeguard. Story effects have no `stat` (beats, wounds and approaches change only through the rules and a complication's `wound`); risk clocks and deadlines have no story id, so nothing can point at them; threats and forks are not targets of `move`; and the flags `chapter` and `ending` and the fired flags are reserved and cannot be `set`.

### 2.5 Propositions

A story has no separate propositions section. A proposition comes into being as a single sentence where it is used, and the engine fills in `about`, `shows`, `against` and the meaning (ontology.md 3.1). The meaning of every story proposition is a narrative constant. A proposition whose meaning changes with the world is hard for an author to predict, and no current device uses one.

| Where | Proposition id | `about` | `shows` | Meaning | Who comes to believe it |
|---|---|---|---|---|---|
| An entity's `hidden` | `x.hidden` | `x` | `x` | true | Opening a topic that `reveals` it; a block coming to light |
| An entity's `clue` | `x.clue` | `x` | - | true | `look(x)` |
| A topic's `text` | topic id | - | - | true | Opening that topic |
| A character's `beliefs` | belief id | - | - | true | That character (from the start) |
| A claim | claim id | - | - | false, with `against` set to the claim's `against` | Nobody (used to judge exposure) |
| A latent's `text` | latent id | the entities in `brings` | same | true | The player (on declaring it) |

## 3. Entries

### 3.1 Top level

| Key | Contents |
|---|---|
| `id`, `version`, `title`, `premise` | Story id (independent of the folder name, unique across stories), version (an integer recorded in saves; compatibility uses the file digest, ontology.md 6), title, public premise |
| `beats`, `wound_boxes` | Scene length `B ≥ 2`, number of wound boxes `≥ 1` |
| `flags` | Story flags `{name: [value, …]}`. The first value is the starting value; the values are a contiguous integer range or strings |
| `style` | The writing style, passed verbatim to the narration model (multi-line) |
| `impossible` | Phrases for things that do not exist in this world (engine.md 3.1) |
| `player` | 3.2 |
| `places`, `characters`, `things`, `obstacles` | 3.3–3.6 |
| `chapters`, `threats`, `forks` | 3.7–3.8 |
| `claims`, `latents`, `triggers`, `endings` | 3.9–3.11 |
| `witnesses` | Section 5 |

`S₀` holds `flag(chapter, 1)` and the starting values of the declared flags.

Every field is required except these:

- Top level: `flags`, `impossible`, `threats`, `forks`, `claims`, `latents`, `triggers` (empty when absent).
- Any entry: `aliases`, `clue`, `hidden`, `complications`.
- Protagonist: `traits` (none when absent). Place: `rest`. Character: `regards`, `beliefs`, `wants`, `topics`, `favor`, `avoids`. Topic: `free_when` (false when absent).
- Obstacle: `risk` (default `normal`), `fits`, `clashes`, `blocks`. Solution: `rely`, `when`.
- Chapter: `goal` (only in the last chapter, which has none), `goal_effects`; a deadline's `effects` and `ending` (3.7). Latent: `brings`, `effects`.
- The file `evals.yaml`.

### 3.2 Protagonist

| Field | Meaning |
|---|---|
| `start` | Starting place |
| `approaches` | Four values, e.g. `[2, 1, 1, 0]`, each `0…3`. The player distributes their sum over the four approaches, and no approach may exceed the largest value |
| `traits` | `{pick: n ≥ 1, options: {id: {name, text}}}`, with more options than `pick`. Write traits as the protagonist's background (job, ties, knowledge) so they do not overlap the stats (approaches) |

Starting possessions are the `things` with `at: player`. Beats, wounds and growth start at 0.

### 3.3 Places

| Field | Meaning |
|---|---|
| `name`, `aliases`, `senses` | Name, aliases, 3–5 sensory cues |
| `exits` | Places reachable from here, one `link(this place, q)` each |
| `rest` | A place to rest (`cut:rest`) |
| `clue`, `hidden` | 2.5 |
| `complications` | 3.6 |

### 3.4 Characters

| Field | Meaning | Evaluated |
|---|---|---|
| `name`, `aliases`, `pronoun`, `desire`, `fear` | Public parameters | |
| `voice` | One line on how they talk. End it with one line of dialogue typical of the character, written as `예: "…"` (`예` = "e.g."), and the narration model matches their speech to that example. Never put hidden facts in the sample line | |
| `persona` | Personality type: one of the 16 MBTI types the engine defines (`ISTJ` … `ENTJ`). That type's personality description goes into the narration context with it. Required | |
| `at` | Starting place. A character who starts offstage is brought in by a latent (3.10) | |
| `avoids` | Places they will not enter even while traveling with the player (rule.md 5.1, companions). Matching these to their `fear` brings the character to life. When absent, they follow anywhere. The story never puts them in such a place, at the start or by a `move` (V3): 윤슬, brought to the lamp room she avoided, was shown agreeing to come along "but not into the lamp room" while she stood in it (goal-4-talker 46, goal-5-odd 37, goal-5-explorer 43) | |
| `regards` | Starting values toward the player, `{trust, fear}`, `−3…3`. 0 when absent | |
| `beliefs` | `{id: sentence}` or `{id: {title, text}}`. Propositions they believe from the start. Private: they ground exposure and are never told. A belief the player can come to share should have a `title`, the short name chips and the journal use; without one its sentence served as a label ("…꺼져 있다.에 기대어", goal-6-bold 16) | |
| `knows` | Up to 4 sentences of everyday knowledge they tell anyone who asks (ontology.md 3.4). Public, so never a hidden fact, and it names no other person, since the narrator moves anyone its context names (V4); knowledge that should cost trust or a roll is a topic. Without it a person asked about their own life made it up | |
| `wants` | Things they welcome when handed them (rule.md 5.1 `give`). Shown on screen and in prompts only while the thing is not hidden from the player | |
| `topics` | `{id: {title, text or reveals, free_when}}`. `reveals: x` reveals `x.hidden` | `free_when`: visible |
| `favor` | `{label, effects, promise: {name, keep, break}}`. At most one per character; once granted, it cannot be chosen again | `keep`, `break`: world |
| `clue`, `hidden`, `complications` | 2.5, 3.6 | |

Both the roll decision and the screen evaluate `free_when` on visible state (V3 makes the visible and world values equal). An absent `break` is false. A promise that is neither kept nor broken stays owed: chapter changes and the ending do not settle it (rule.md 5.2). A due date goes into the promise's `name` and `break`.

### 3.5 Things

`{name, aliases, look, at, clue, hidden}`. `at` is a place, a character or `player`.

### 3.6 Obstacles, solutions, complications

| Field | Meaning | Evaluated |
|---|---|---|
| `name`, `aliases`, `look`, `at` | Public name, appearance (including any writing on it), the place where it sits | |
| `boxes` | Number of boxes, `1…6`. 1 when absent: one success gets past it | |
| `risk` | `low` or `normal`. The base value in the risk formula (rule.md 3.2) | |
| `fits`, `clashes` | Approaches that suit it (`fill` +1 more) and approaches that clash with it (risk +1) | |
| `blocks` | The places, things, characters and obstacles it blocks | |
| `solutions` | `{id: {label, approach, rely, when}}`, two or more, each with a different approach | `when`: visible |
| `clue`, `hidden`, `complications` | 2.5, below | |

- A **solution** is an instance of `try(this obstacle, approach)` with a `label` and a condition `when` attached. `rely` names what it leans on (a thing or a proposition id), and holding or believing that is implicitly added to `when`. Result, risk and cost are the same as for `try`, and a `try(this obstacle, approach)` that is not a solution is a candidate too. Solutions add no candidates; they only give them names.
- The effect of filling up is written as a trigger `{when: {fill: [o, "=", full]}}`.
- **Blocking**: `blocks` applies while the obstacle is in place and not full (ontology.md 1.2). It blocks `go` for a place, `take` for a thing, `talk` for a character and `try` for an obstacle. An action blocked by a visible obstacle is not a candidate. When a hidden obstacle is blocking, attempting the action makes the player believe `o.hidden`, which reveals it; that attempt advances the beat and has no roll.
- A **complication** `{id: {name, weight, when, effects, wound}}` attaches to a place, a character or an obstacle, and what it attaches to is an implicit condition (place: being there; character: being face to face; obstacle: being the target of the roll). `wound: n` adds n wounds, and it is the only story effect that raises wounds. `when` is evaluated against the world on a failed roll (rule.md 3.3).

### 3.7 Chapters

`chapters` is a list, and its order gives the chapter numbers (starting at 1). A chapter transition always goes to the next chapter.

| Field | Meaning | Evaluated |
|---|---|---|
| `title` | Public title | |
| `aim` | A one-sentence goal always shown on screen: the `goal` in the player's words | |
| `goal` | Chapter goal. Required except in the last chapter, which has none | world |
| `goal_effects` | Effects added to the chapter transition when the goal is met | |
| `clock` | Required. Risk clock `{name, boxes ≥ 3, crisis}`. `crisis` is the effects applied each time the clock fills (one or more) | |
| `deadline` | Required. Deadline `{name, boxes 1…6}`, optionally `effects` and `ending`. `ending` is required in the last chapter: an ending id other than `collapse`, possibly one that has a `when` | |

What the engine builds:
- Chapter `k`'s goal trigger `(flag(chapter, k) ∧ goal, [chapter_to(k+1)] ++ goal_effects)`
- The deadline's arrival effect: `effects ++ [end(e)]` with `ending: e`, otherwise `effects ++ [chapter_to(k+1)]`, which starts the next deadline a box closer (rule.md 4.3)
- Engine ids for risk clocks and deadlines (`clock.k`, `deadline.k`) and their placement in `S₀`: the first chapter's at `at(·, player)`, the others with no `at`, all with `fill` 0

### 3.8 Threats and forks

| Field | Threat `threats` | Fork `forks` | Evaluated |
|---|---|---|---|
| `name`, `boxes` (1…6) | Public name, number of boxes | Same | |
| `appears_when` | Appearance condition | Same | world |
| `arrival` | Arrival effect | - | |
| `choices` | - | `{id: {name, effects}}`, two or more | |
| `default` | - | `{name, effects}`: what happens if the boxes fill before a choice; it cannot be chosen | |

A threat that belongs to a place the next chapter leaves behind is retired by a trigger on that chapter's flag (`when: {flag: [chapter, k]}`, `effects: [{retire: <id>}]`). One that followed the player indoors kept filling with nothing to do there and fell off screen, and it took a row the next chapter needed (goal-1-odd 11, goal-1-bold 25, goal-1-talker 43; at 320×568 chapter 2's rows took 37% of the screen, goal-1-ui 8, goal-2-ui 9).

A fork is asked by a person. Someone the player can meet before it wants the choice that costs the chapter goal (their `desire` names it). A trigger brings them to the fork's place and reveals one of their `beliefs` that says what for, and `appears_when` includes `{at: [<person>, <place>]}`, so the choice arrives with someone asking for it and a line saying why. A fork that no one had mentioned, in a room both people avoided, was never taken: every game ended the same way, chapter 2 was one card again and again, and the endings named no one (F9 0 in 10 of 10 games; goal-1-explorer 50, goal-1-talker 47, goal-2-explorer 37, goal-3-odd 27, 30, goal-3-bold 25).

Threats and forks have no `at` and `fill` 0 in `S₀`. The engine wires `appears_when` into a one-shot trigger `appear.<id>` (effects `[move(<id>, player)]`); to tie one to a chapter, include `{flag: [chapter, k]}` in it. A threat is driven off by a `retire` in some other effect, and a `set` that lowers its `fill` delays its arrival. `retire` also sets the appearance trigger's fired flag, so a threat or fork retired before it appears never appears. Once in, it stays across chapter changes: its boxes fill at every scene end (rule.md 4.1), and when they are full `τ_arrive` applies `arrival` or `default` and retires it (rule.md 8).

### 3.9 Claims

`claims: {id: {text, against}}`. `text` is the public sentence the player says, and `against` is the id of the belief that exposes it. If the listener holds that belief, the claim is exposed (rule.md 5.1).

### 3.10 Latents

`latents: {id: {name, when, text, brings, effects}}`.

| Field | Meaning | Evaluated |
|---|---|---|
| `name` | "분류: 짧은 말" ("category: short phrase") | |
| `when` | The condition under which it can be declared | visible |
| `text` | The proposition the player comes to believe by declaring it (2.5) | |
| `brings` | Entities that belong to this latent alone. Written like `characters` and `things`, but without `at` | |
| `effects` | The effects of the declaration. They bring the `brings` entities on stage | |

**Scope rule**: a latent's id and the ids inside its `brings` cannot be used outside that latent's entry, and a latent's `effects` target only its `brings` entities (`move`, `tag`, and those entities' `regards`). A latent that is never declared leaves no trace in the world.

### 3.11 Triggers and endings

- `triggers: {id: {when, effects, repeat}}`. `when` is evaluated against the world, and without `repeat: true` a trigger fires once per game.
- `endings: {id: {title, when, frame}}`. `collapse` is required. With `when`, the engine wires the ending into a trigger `end.<id>` (effects `[end(id)]`); without it, some chapter's deadline must point to it with `ending`. `frame` is the public sentence handed to the ending's narration. The engine's `collapse` ending (the protagonist collapses, rule.md 6) has only `title` and `frame`, with no `when`.

The engine wires story triggers in this order: threat and fork appearances, `triggers`, chapter goals, endings with `when`. Within one kind, the order is declaration order. The five engine triggers come after them (rule.md 8).

### 3.12 Action ids

The action ids used by witnesses, receipts, buttons and patterns are `schema:intent arguments`, with judgment arguments appended as `;key=value`. An omitted judgment argument takes its default `ν₀`. A `rely` value is prefixed with the kind of thing it points to: `thing:<id>`, `prop:<id>`, `trait:<id>`, `bond:<id>`, `with:<id>`, `tag:<entity>:<slot>` (rule.md 2). A solution's `rely` field holds only the id; the story determines the kind.

```
go:village   look:door   take:oil   give:letter:dohae   declare:l_baek   cut:pass   cut:rest
talk:dohae:t_oil;tone=threaten   talk:dohae:favor   talk:dohae:chat;tone=deceive;claim=c_keeper
try:door:finesse;rely=thing:key   try:door:force;strain=forced   choose:g_oil:beacon   grow:finesse
```

## 4. Validation

The properties the rules require of a story, and where each one is upheld.

| Property | Holds by structure | Left to checks |
|---|---|---|
| Valid start and effects | Effects are only the operations in 2.4; `move(player, ·)` goes to a place | V1, V2 |
| Grammar of clocks and triggers (rule.md 4.2, 8) | Clocks and deadlines cannot be pointed at; story effects have no `stat`; wounds come only from `wound`; a threat appears once, through `appears_when`; the engine builds chapter transitions and endings from the chapter and ending fields; every chapter has a clock and a deadline | V3: no trigger condition is true in `S₀` |
| Latent isolation | A latent's entities and propositions come into being inside its entry | V1: the scope rule (3.10) |
| Finite values | Flags take only declared values | V1 |
| Visible evaluation = world evaluation | - | V3: the atoms of visibly evaluated conditions |
| Blocking | Each hidden entity has exactly one `x.hidden` | V3: where blockers sit |
| No leaks | The place for hidden content (proposition sentences) is separate from public text | V4: name leaks only. Leaking meaning is the author's responsibility |
| Reachability | - | V5 |
| Preservation and progress | - | V6 |

At startup the server runs these on every story in this order, and does not start if any of them fails. Errors are in English and include the entry id and field.

| | Stage | What it checks |
|---|---|---|
| V1 | Format | Schema (fields, value types, value ranges); id uniqueness and references; `brings` scope; two or more solutions, each with a different approach; `clock` and `deadline` in every chapter; the last chapter has no goal and its deadline has an `ending`; every ending without `when` (except `collapse`) is pointed to by some deadline; a `collapse` ending exists; flag values are among the declared ones; at most 58 story complications per weight (`u` has 60 values and the engine adds two, rule.md 3.3) |
| V2 | Start state | Build `S₀`; `S₀ ⊨ C`; `player` is in exactly one place |
| V3 | Placement | No trigger condition is true in `S₀` (engine triggers included). Visibly evaluated conditions (the `when` of solutions and latents, the `when` of complications being chosen, a topic's `free_when`) use only atoms that are always in `F` when they are evaluated: the player's own atoms (`at: [player, place]`, `at: [thing, player]`, `believes: [player, p]`, `mark: [player, tag]`, and `regards` and `owes` that involve `player`), `did`, and the atoms of the entity the condition is attached to (`at: [that entity, ·]`, `mark: [that entity, ·]`, `fill: [that obstacle, ·]`). The `at` of a thing a character holds, entities elsewhere, and `flag` are not allowed. A blocking obstacle sits in the same place as the thing, character or obstacle it blocks; if it blocks a place, it sits in every place that has an `exits` entry or a `link` effect leading there; no character starts in, or is moved by a story effect into, a place it avoids |
| V4 | Names | The names and aliases of hidden entities (those with `hidden` or inside `brings`) do not appear in the public parameters of 2.1; aliases do not overlap; a character's `knows` names no other character; no `impossible` phrase is a substring of a name, an alias or a solution `label` (because layer 0 matches by substring, engine.md 3.1) |
| V5 | Witnesses | The replay in section 5 |
| V6 | Fuzzing | Random action sequences (picked from `K`, with random dice) run to an ending; at every step, `S ⊨ C` and `K ≠ ∅`; at every step with a roll, the preview's risk, modifier chip list and total equal the values from execution (rule.md 10, preview = execution) |

Validation also warns, without stopping, when a chapter's `B × deadline boxes` is below F10's floor of 20 steps (fun.md 3.3): the story then cannot hold a chapter that long.

V1–V4 make one pass over the story, and V5 computes `K` and `R` for as many steps as the witnesses have. That deadlines produce endings, and that there are "no dead ends", is guaranteed by structure (rule.md 10).

## 5. Witnesses

`witnesses.paths` holds a sequence of actions and dice from the start to each chapter goal, and to each ending with `when` and to `collapse`, one per target. The author writes them, and validation names the path and step where replay fails. Dice `[6, 6, 0]` make any roll succeed. Paths beyond the required ones are allowed, and all of them are replayed.

```yaml
witnesses:
  creation: {approaches: {force: 1, finesse: 2, wits: 1, charm: 0}, traits: [sailor, tinker]}
  paths:
    - reach: {goal: 1}
      steps:
        - go:village
        - {do: "try:door:finesse", roll: [6, 6, 0]}   # only actions with a roll get [d₁, d₂, u]
    - reach: {ending: two_lights}
      after: 0                                       # continues after the steps of path 0
      steps: [choose:g_oil:beacon]
```

Every path uses `creation`; a path's own `creation` takes precedence. `after: i` puts the steps of path `i` in front.

Replay starts from the `S₀` built from `creation`. At each step it checks `aᵢ ∈ K(Vᵢ)` and applies `R` with the given dice (with no dice when there is no roll). On the last step, the goal's trigger must fire or that ending must be set. A chapter change caused by a deadline's arrival does not count as reaching the goal, and reaching an ending before that is a failure. Cards and clarifying questions belong to interpretation, so replay has neither.

## 6. Interpretation evals

`evals.yaml` is test data that measures interpretation against the real models, and it is not part of startup validation. It is a list of cases:

| Field | Meaning |
|---|---|
| `at` | The state: after the first `step` steps of witness path `path`. For a state no witness passes through, `then` lists further actions to run, in the same shape as witness steps (`then: [{do: "talk:h:come", roll: [6, 6, 0]}]`) |
| `text` | The player's sentence |
| `expect` | One action id (the first step), a list of action ids (the leading steps), a schema name (any action of it first), `refused`, `clarify` (a clarify card, engine.md 4.1) or `idle` (the whole sentence became `try(player)`, engine.md 3.4). A reliance the sentence names is part of the action id |
| `relies` | Optional. The reliances the card of the sentence's first rolled step offers, in card order and without "rely on nothing": what the decision model's relevance question kept (engine.md 4.2) |
| `known` | Optional. The case is a known miss, and the value says why |

```yaml
- at: {path: 0, step: 2}
  text: 녹슨 자물쇠를 살살 따 본다
  expect: try:door:finesse
  relies: [trait:tinker]
- at: {path: 0, step: 0}
  text: 잠시 숨을 고르며 바다를 바라본다
  expect: look:dock
  known: 1층이 "숨을 고르며"를 시간 보내기(cut)로 확신합니다
```

The evals command (`python -m src.story.evals`) is a regression gate. A case passes when the sentence's outcome matches `expect` and, if given, the offered reliances match `relies`. The run fails (exit 1) on a **regression**, a case without `known` that fails, and on a case where a model gave no answer (an error or the time limit), since its result says nothing about interpretation. A **fix**, a `known` case that passes, does not fail the run; it is listed so that its `known` is removed. A case is listed as **fragile**, with the probability, when an answer that a threshold decides lies within 0.05 of it, since a small change in a prompt or model flips it: `θ₁` for the first step, `θ` for an intent slot, a judgment other than `ν₀` and a claim, and `θ_rely` for each reliance (engine.md 3.4, 4.2). The `try` target and approach are left out, as the narration model's pick decides them.
