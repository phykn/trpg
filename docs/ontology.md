# Ontology

The world is a finite set of atoms. Only the rules `R` change it, and the player and the models receive only the observation `V`. This document defines the world, its invariants, vocabulary, observation and change operations, their implementation in `server/src/onto/`, and the save format. Actions and rolls are in [rule.md](rule.md), the story format in [story.md](story.md), and the models and protocol in [engine.md](engine.md).

```
server/src/onto/
  atoms.py    atoms, state State
  change.py   change Delta, effect operations, working copy Work
  universe.py universe Universe, initial state S₀, conformance check conforms
  cond.py     condition evaluation holds — shared by the world (S, h) and the observation (F, hᵥ)
  view.py     observation observe: E, F, B, M, hᵥ
  log.py      event Event, log L, patterns, history summary h
  save.py     snapshot writing, rebuilding from the log
```

This package knows neither the models nor the rules. Predicates the rules add (`owes`, `spent`) and their operations (`assert_`, `expire` and others) also live here.

## 1. World

### 1.1 Atoms and state

- Entity kinds `𝒯 = {agent, place, thing, obstacle, prop}`. The story fixes the finite set of entities `U`, and it does not change during play.
- Every value kind in `𝒱` is finite (1.3). The value kind sets the range of each number.
- Each predicate in `Σ` (1.2) has a kind for each position, and `Atom` is the set of all ground atoms whose positions match their kinds. It is finite.
- **State** `S ⊆ Atom`. An atom in `S` is true; one not in `S` is false (closed world).
- **Change** `Δ = (Δ⁺, Δ⁻)`, `Δ⁺ ∩ Δ⁻ = ∅`. `S ⊕ Δ = (S ∖ Δ⁻) ∪ Δ⁺`.

In code an atom is a tuple with the predicate name first; in JSON it is an array.

```python
Atom = tuple[str, ...]          # ("at", "key", "dohae"), ("fill", "door", 2)
```

`State` keeps one index per predicate, and `atoms()` returns the atom set. The two representations correspond one to one, and the indexes enforce most of conformance (1.4) by their structure.

| Predicate | Index | Enforced by structure |
|---|---|---|
| `at` | `dict[x, y]` | C1 |
| `link`, `believes`, `owes`, `follows`, `due`, `spent` | `set[tuple]` | |
| `mark` | `dict[(x, slot), (kind, life)]` | C2 |
| `regards` | `dict[(g, h, axis), n]` | C2 |
| `fill` | `dict[o, n]` | C2 |
| `stat` | `dict[(g, s), n]` | C2 |
| `flag` | `dict[f, v]` | C2 |

`State` is an immutable value. `apply(S, Δ) = (S ∖ Δ⁻) ∪ Δ⁺` returns a new state, and a step is computed on a copy-on-write working copy `Work(S)` (section 4).

**Defaults are atoms too.** `fill`, the player's `stat` (the four approaches, `beats`, `wounds`, `growth`) and each person's two `regards` axes toward the player enter `S₀` as atoms with value 0. This keeps a condition such as `{fill: [o, "=", 0]}` from depending on whether the atom exists. There is no `regards` from the player toward people, since nothing writes it.

### 1.2 Predicates

| Predicate | Atom | Meaning |
|---|---|---|
| `at(x, y)` | `("at", x, y)` | agent, thing or obstacle `x` is in place `y`. If `y` is an agent, `y` carries `x` |
| `link(p, q)` | `("link", p, q)` | one can go from place `p` to `q` |
| `mark(x, k, l, i)` | `("mark", x, kind, life, slot)` | one tag on `x`. kind `edge` (advantage) or `snag` (disadvantage), life `scene`, `chapter` or `scar` (permanent), slot `1…3` |
| `believes(g, p)` | `("believes", g, p)` | agent `g` believes proposition `p` |
| `regards(g, h, axis, n)` | `("regards", g, h, axis, n)` | how `g` sees `h`. axis `trust` or `fear`, `n ∈ −3…3` |
| `fill(o, n)` | `("fill", o, n)` | filled boxes of obstacle `o` |
| `stat(g, s, n)` | `("stat", g, s, n)` | a sheet entry. `s` is one of the four approaches (`force`, `finesse`, `wits`, `charm`), `beats`, `wounds`, `growth`, or a trait id (value 1) |
| `flag(f, v)` | `("flag", f, v)` | `chapter`, `ending`, story flags, and fired flags `fired_*` |
| `owes(g, h, k)` | `("owes", g, h, k)` | what `g` owes `h`. `k` is `promise` (a promise tied to `h`'s favor) or `kindness` (goodwill received) |
| `follows(h, g)` | `("follows", h, g)` | agent `h` travels with `g` (the player). When `g` moves, `h` moves along |
| `due(g, c)` | `("due", g, c)` | a cost to choose under an old rule. It stays in the index only so saves from before this rule still load, and nothing creates it |
| `spent(g, s)` | `("spent", g, s)` | trait `s`, already leaned on this chapter |

`blocks(o, x)` ("o blocks x") is a derived atom and is never stored. It holds for each `x` in `o`'s story `blocks` list while `at(o, ·)` exists and `fill(o) < boxes`. Condition evaluation and observation compute it over the atom set they receive.

### 1.3 Values and limits

| Value kind | Range |
|---|---|
| regard `regards` | `−3…3` |
| boxes `fill` | `0…boxes` (`1…6` per obstacle) |
| approach value | `0…3` |
| `beats` | `0…B` (the story's scene length) |
| `wounds` | `0…wound_boxes` |
| `growth` | `0…` |
| slot | `1…3` |
| approach | `{force, finesse, wits, charm}` |
| tag | kind `{edge, snag}`, life `{scene, chapter, scar}` |
| flag value | a finite set the story declares |

The `set_` operation clamps its result at both ends of the range (section 4).

### 1.4 Conformance `C`

- **C1 One place**: each agent, thing and obstacle has at most one `at(x, ·)`.
- **C2 Functionality**: `regards(g, h, axis, ·)`, `fill(o, ·)`, `stat(g, s, ·)`, `flag(f, ·)` and `mark(x, ·, ·, i)` each have at most one atom.
- **C3 Limits**: every value lies within its range in 1.3.
- **C4 Company**: if `follows(h, g)` holds, `at(h, ·)` and `at(g, ·)` name the same place.

Each one says "no such combination of atoms exists", so each also holds on a subset (`F`). "The player is always in exactly one place" is an existence condition, so the initial state (5.2) and the `move` operation enforce it, not `C`. There are no crowds (agents without a place). `conforms(S)` rechecks C1–C4 over the atom set and is used only in fuzzing (story.md V6) and rebuilding (section 6).

## 2. Transitions and the log

- **Action** `a`: a schema with its arguments filled in, one to one with a canonical action id (story.md 3.12). The set of all actions `Act` is finite.
- **Dice** `rₜ = H(seed, t)`. `H` is a fixed function (rule.md 3.1), and each game has one `seed`.
- **Rules** `R(S, h, a, r) = (Δ, mods)`. `mods ⊆ Atom` are the atoms that adjusted the roll.
- **Event** `e = (t, a, r, Δ, W, mods, result)`. The witnesses `W` are the agents in the places where the player was just before and just after the action.
- **Log** `L`: a sequence of events. `L₀ = ε`.
- **History summary** `h(L) ⊆ Pat`: the patterns, among the story's `did` patterns and the engine patterns (rule.md 5.1), that some event in `L` matches. Patterns read only an event's action id and result, never `t`, and a pattern never leaves once it is in.

The world moves only under these five invariants.

| Invariant | Statement |
|---|---|
| Transition | `(Δₜ, modsₜ) = R(Sₜ, h(Lₜ), aₜ, rₜ)`, `Sₜ₊₁ = Sₜ ⊕ Δₜ`. Narration, model answers and the screen are not arguments of `R`, so they cannot change the world |
| Log | `Lₜ₊₁ = Lₜ · eₜ`. Append only |
| Admission | an executed action is a candidate at that moment: `aₜ ∈ K(Vₜ)`. Clarifying questions, refusals and cards are not actions; they do not advance `t` or create events |
| Non-interference | everything the player and the models receive at turn `t` is a function of `(Vₜ, exogenous input)` (for narration, of `Vₜ₊₁`). Exogenous input is the player's sentence, earlier model output and the models' randomness |
| Generality | `R`, `V`, `K`, `W`, `h` and `C` know no entity by name. Their results follow any kind-preserving renaming |

Changes and events in code:

```python
@dataclass(frozen=True)
class Delta:
    add: frozenset[Atom]
    remove: frozenset[Atom]      # add ∩ remove = ∅

@dataclass(frozen=True)
class Event:
    t: int
    action: str                  # canonical action id (story.md 3.12)
    roll: tuple[int, int, int] | None   # (d1, d2, u) only when the step rolled
    result: str                  # success, fail, none, blocked
    delta: Delta                 # minimal difference
    witnesses: tuple[str, ...]   # sorted
    mods: tuple[Atom, ...]       # atoms that adjusted the roll, in rule order
```

A step's `Δ` is the sequential composition of effect operations, but it is stored reduced to the **difference**: `add = S* ∖ S`, `remove = S ∖ S*`. The resulting state is the same, and an atom removed and re-added within one step leaves no trace in the log or the narration. `result` is stored so that `none` (achieved without a roll) and `blocked` (a hidden block came to light) can be told apart without interpreting `Δ`.

A pattern compiles to `(leading pieces, judge arguments, set of results)` (no results listed means every result), and `matches(pattern, action, result)` tests one event. `h(L)` is the set of matched pattern indices, updated as each event is appended. No function edits or deletes an event.

## 3. Propositions and observation

### 3.1 Propositions

For each proposition `p` the story gives `text(p)` (the sentence handed to the models), `about(p)` and `shows(p) ⊆ U` (what it is about, and what becomes visible to whoever believes it), `against(p)` (the propositions that cannot be believed alongside it), and optionally a meaning `⟦p⟧` (a sentence over `Σ`). A proposition without a meaning is a true or false constant set by the story (story.md 2.5).

- **Truth** `true(p, S) ⟺ S ⊨ ⟦p⟧`. When the world changes, the truth of a proposition changes with it.
- **Knowledge** `knows(g, p, S) ⟺ believes(g, p) ∈ S ∧ true(p, S)`. Not stored. False beliefs are allowed, and truth is judged against `S`.
- **Hidden** `hidden(x, o, S)`: some proposition `shows` `x`, and `o` believes none of them.
- **Exposure**: if the player asserts a story proposition `p` in conversation and the listener believes a proposition in `against(p)`, the player is caught. A claim that matches no story proposition stays in the event only as a sentence and never grounds an exposure.

### 3.2 Observation `V`

`observe(U, S, L, o) → Obs`. `here(o)` is the place `q` with `at(o, q) ∈ S`.

```python
@dataclass(frozen=True)
class Obs:
    observer: str
    seen: frozenset[str]          # E
    facts: State                  # F, a sub-state of S
    beliefs: tuple[str, ...]      # B, in reveal order
    memory: tuple[Seen, ...]      # M
    hist: frozenset[int]          # hᵥ
```

1. **`E`** seen entities: `o` itself, what `o` carries (things, clocks, threats), `here(o)`, the unhidden entities there, and each unhidden place `q` with `link(here, q)`. A distant entity known only through a believed proposition is not in `E`. It comes across only as a name inside the proposition's sentence, and it enters `E` once it is in the current place or a linked one.
2. **`F`** visible facts: the atoms of `S` that satisfy the rules below. `F ⊆ S` holds by construction. The rules are a single function, `fact_rule(o, S, atom)`, and memory projection uses the same function.

| Predicate | Visible when |
|---|---|
| `at`, `link`, `mark`, `fill` | every entity position is in `E` |
| `stat(g, ·)`, `believes(g, ·)`, `due(g, ·)`, `spent(g, ·)` | `g = o` |
| `regards(g, h, ·)`, `owes(g, h, ·)`, `follows(g, h)` | `g = o` or `h = o` |
| `flag` | never |

3. **`B`** beliefs: the `p` of each `believes(o, p)`, in the order they came to be believed (the event that first added it to the log, or story order for beliefs held from the start). Each `text(p)` is handed over, but `⟦p⟧` is never mixed into `F`.
4. **`M`** memory: for each event with `o ∈ W`, a projection that keeps only what was visible then. `Eₑ` and `F-ruleₑ` are the union of what is computed from the states just before and just after the event.
5. **`hᵥ`**: the patterns matched by events in `M`. Patterns read only the action id and the result, and since the player is the actor of every event, the projection keeps both intact, so `hᵥ = h`. If patterns ever read `Δ` or witnesses, the two must be separated.

```python
@dataclass(frozen=True)
class Seen:
    t: int
    action: str
    roll: tuple[int, int, int] | None
    result: str
    witnesses: tuple[str, ...]    # W ∩ E_e
    delta: Delta                  # Δ ∩ F-rule_e
    mods: tuple[Atom, ...]        # mods ∩ F-rule_e
```

Projections are computed when an event is appended and kept in a cache. Only the player's projection `seen[player]` is built; it feeds the narration input `δ`, step records, recaps and the memory lines of the context. People have no prompts of their own, so there are no per-person projections. Memory is used only in prompts; `R` and conditions read only `h(L)`. The cache is not saved and is rebuilt on load.

Observation reads only `S`, `L` and `U`, never the presentation layer (engine.md 6).

### 3.3 Conditions and candidates

`cond.py` compiles conditions (story.md 2.3) to an AST and evaluates them with `holds(c, facts, hist)`. World evaluation is `holds(c, S, h)` and visible evaluation is `holds(c, F, hᵥ)`. There is one evaluator, so the only difference is the atom set passed in. The derived atom `blocks` and hiddenness are computed over that set.

Candidates `K(O)` read only `(E, F, B, hᵥ)` and story constants (rule.md 2). Entity arguments come from `E` and proposition arguments from `B`, and conditions are evaluated over `(F, hᵥ)`. The evaluation is deliberately optimistic: with no visible block, it assumes there is none. So `R` must be defined even when the visible condition is true but the real one is false (a hidden block), and the only way to learn what is hidden is to act and run into it. Conditions that reach the screen or a prompt (a topic's free condition, solution names) use the same visible evaluation.

## 4. Effects and operations

The only code that changes the world is the operations in `change.py`. Each operation has the form `op(work, …)` and reads and edits the working copy `Work(S)`; each one sees the state the previous ones left. Every operation preserves `C`, so their sequential composition does too.

| Operation | What it does |
|---|---|
| `move(x, y)` | `at[x] = y`. If `x = player`, `y` must be a place or the move is refused, and every `h` with `follows(h, player)` moves to `y` too. If `x` is a person following someone, that `follows` is removed. Both keep C4 |
| `set_(pred, key, v)` | sets a `regards`, `fill`, `stat` or `flag` value. If `v` is `"+n"` or `"-n"`, it is added to the current value, and the result is clamped to its range in 1.3. Does nothing if the value is unchanged |
| `reveal(g, p)` | adds `believes(g, p)` |
| `tag(x, kind, life)` | uses the lowest-numbered empty slot. If all are full, it clears the lowest-numbered slot that is not a `scar` and uses that. If only `scar` tags remain, it does nothing |
| `untag(x, slot)` | clears that slot |
| `link(p, q)`, `unlink(p, q)` | adds or removes a `link` |
| `retire(o)` | removes `at[o]`. For a threat or fork, it also clears the fired flag of its appearance trigger |
| `expire(life)` | removes every `mark` with that life |
| `assert_(atom)`, `retract(atom)` | adds or removes `owes`, `spent` and `follows` atoms |
| `clear_spent(g)` | removes all of `g`'s `spent` atoms |

Story effects (story.md 2.4) translate directly into these operations. `{set: [regards, g, h, axis, v]}` becomes `set_("regards", (g, h, axis), v)`, and `{tag: [x, kind, life, name]}` becomes `tag(x, kind, life)` plus a default name kept in the presentation layer.

**Atomicity**: the rules compute a step on `Work(S)` and return a `Delta` (the difference). The service creates the event, then replaces the state, log and presentation layer in a single save (engine.md 7). If an exception occurs midway, only the copy is discarded.

**Iteration order**: every iteration that affects output (complication candidates, threat arrivals, triggers) follows the story's declaration order, and every other set is emitted sorted, because the order of a Python `set` can differ between runs.

## 5. Universe and initial state

`story/compile.py` reads the story, builds a `Universe` (`onto/universe.py`) that never changes during play, and wires the triggers.

| Field | Contents |
|---|---|
| `kind` | `id → kind`, and the obstacle subkind (`plain`, `clock`, `deadline`, `threat`, `fork`) |
| `name`, `aliases` | name tables. Engine entities take their names from the story's `clock.name` and `deadline.name` |
| `props` | proposition id → `text`, `about`, `shows`, `against`, source (story.md 2.5) |
| `params` | per-entity story parameters: boxes, base risk, `fits` and `clashes`, `blocks`, solutions, complications, topics, favors, `wants`, sense cues |
| `chapters` | per chapter: goal condition, clock id, deadline id, crisis effects, goal effects |
| `triggers` | the list of wired triggers (5.3) |
| `patterns` | `Pat`: every `did` in the story plus the engine patterns |
| `flags` | flag name → finite set of values |
| `limits` | `B`, `wound_boxes`, slot count |

### 5.1 Engine ids

Entities, propositions and triggers that the engine creates use ids containing `.`. Story ids use only `[a-z0-9_]`, so the two never collide.

| Item | id |
|---|---|
| chapter `k`'s risk clock and deadline | `clock.k`, `deadline.k` |
| hidden and clue propositions | `x.hidden`, `x.clue` |
| engine complications | `engine.snag`, `engine.beat`, `engine.wound`, `engine.end` |
| wired triggers | threat or fork appearance `appear.<id>`, chapter goal `goal.<k>`, ending `end.<id>` |
| a trigger's fired flag | `fired_<trigger id>` (for both story triggers and wired triggers) |

### 5.2 Initial state

`initial(universe, creation) → State`. `creation` is the player's chosen approach allocation, traits and name (story.md 3.2). The name appears only on screen and never enters `S₀`. The same story and `creation` always produce the same `S₀`.

1. The story's `at`, `exits` (→ `link`), and people's `beliefs` and `regards` become atoms.
2. `fill 0` for every obstacle (clocks, deadlines, threats and forks included). `at(·, player)` for the first chapter's clock and deadline.
3. The player's `stat`: the four approaches from the `creation` allocation, 1 for each trait, and 0 for `beats`, `wounds` and `growth`.
4. Each person's two `regards` axes toward the player (0 if unset). People a latent brings in are included too, without `at` and hidden.
5. `flag(chapter, 1)` and the initial values of story flags.

This is also where `creation` is checked: its approach values must spend the full sum of the story's `approaches` with each at most the largest of them, and it must have exactly `pick` traits.

### 5.3 Wiring triggers

Story triggers are wired as `Trigger(id, when, effects, repeat, kind)` in the order of story.md 3.11 (appearances, `triggers`, chapter goals, endings). Unless a trigger is `repeat`, `not flag(fired_<id>, 1)` is added to its `when` and `set(flag, fired_<id>, 1)` to the end of its effects. Chapter goal and ending effects are the engine macros `chapter_to(k+1)` and `end(e)`, defined in rule.md 4.3.

## 6. Saves

Each game is a single file, `saves/engine/g_<id>.json`, and the log is the source of truth. The state and memory are caches rebuilt from the log, so they are not saved.

```json
{
  "schema_version": 2,
  "story": {"id": "lighthouse", "version": 1, "digest": "sha256:…"},
  "seed": 4821930017,
  "creation": {"approaches": {"force": 1, "finesse": 2, "wits": 1, "charm": 0}, "traits": ["sailor", "tinker"]},
  "log": [{"t": 0, "action": "go:village", "roll": null, "result": "none", "delta": {"add": [["at", "player", "village"], ["stat", "player", "beats", 1]], "remove": [["at", "player", "dock"], ["stat", "player", "beats", 0]]}, "witnesses": ["dohae", "player", "yunseul"], "mods": []}],
  "presentation": {}
}
```

`presentation` is the presentation layer `P` (engine.md 6), and `digest` is a hash of the story file's bytes.

- **Write**: write to a temporary file, `fsync`, then `rename`. A request's state, log and presentation layer change together in this one write. The server is a single process with one lock per game.
- **Rebuild** `load(path) → Game`: refuses the save if `schema_version` or the story `digest` differs (if `U` and `S₀` change, the atoms in the log lose their meaning). A change in engine code is not refused, because `R` is not rerun. Starting from `S₀ = initial(U, creation)`, it applies `S ← apply(S, e.delta)` for each event, checks `conforms(S)` at every step and refuses on a violation, and rebuilds `h`, the memory cache and the belief order in the same pass. The cost is linear in the number of events, and a game has a few hundred.

## 7. Properties and checks

| Property | Statement and reason | Enforced in | Check |
|---|---|---|---|
| Reproducibility | `Sₜ = S₀ ⊕ Δ₀ ⊕ … ⊕ Δₜ₋₁`. The state is rebuilt from the story and the log alone, without `R`, `seed` or the models (by induction on the transition and log invariants). The same `(story, seed, action sequence)` gives the same state and log | `save.py` | state rebuilt after saving = in-memory state; the same input twice → the same result (even with a different `PYTHONHASHSEED`) |
| Conformance | every `Sₜ ⊨ C`, since `S₀ ⊨ C` and every operation preserves `C`. This holds whatever the models answer | `change.py`, `State` structure | property tests per operation; `conforms` at every step while fuzzing random action sequences |
| Atomicity | a step's `Δ` is applied entirely or not at all | `Work`, a single save | an exception midway through an operation → state and file unchanged |
| No creation | `U` and `Σ` are constant, so the models cannot create entities or predicates | `universe.py`, `story/compile.py` | every atom in an event is in `Atom` |
| Bounded model influence | model output reaches the world only through the next action `aₜ ∈ K(Vₜ)` (it is the only argument of the transition the models can touch). A misinterpretation runs an unwanted candidate, never anything outside the candidates | admission check (rule.md 10) | an id outside the candidates → refused |
| No leakage | with the same observation and exogenous input, the player and the models receive the same things. A hidden fact can reach them only by changing later observations | `observe` reads only `S`, `L`, `U`; the screen, prompts and rewrite feedback receive only `Obs` | two states that differ only in hidden atoms → the same `Obs`, screen and prompt |
| Single source | everything the screen, candidates, fact list and prompts assert as fact at one moment lies in `F ⊆ S`, so it is true all together and never violates `C`. Beliefs are shown as beliefs | renderers, `context` | renderers use no atom outside `F` and `B` |
| Story independence | engine code contains no story id, name or sentence (a syntactic proxy for generality). The properties must hold for every story that passes validation, so each story is fuzzed | all of `server/src/` | a boundary test that searches `src/` for the skeleton story's ids and names |
| Story conformance | `S₀ ⊨ C`, the player in exactly one place, parameters defined over `Σ` and `U`, and effects limited to the operations in section 4 | `initial`, story.md V1–V2 | validation at startup |
| Reachability | configurations `(S, h)` are finite and the next one is determined by `(S, h, a, r)`, so "can the goal be reached?" is reachability in a finite graph. Dice expand into all three results | story.md V5–V6 | validation at startup |

## 8. Decisions

| Question | Decision | Reason |
|---|---|---|
| Meaning of a proposition | the sentence is required, `⟦p⟧` is optional | a story constant is enough for a proposition without a meaning |
| Time intervals on facts, variables in conditions | none | the history summary and a finite `U` are enough, and stories stay simple |
| Autonomous NPC actions | reactions and story effects only | goal-seeking NPCs would need a planner |
| Crowds, units smaller than a place | none | `V` stays simple when `here` is a single place |
| Story flags | as few as possible | the history summary and `fill` cover most of it |
