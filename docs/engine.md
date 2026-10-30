# Engine

The engine is a round trip: language → ontology → language. The middle (world and rules) is exact, so properties guarantee it; the two ends (interpretation and narration) are approximated by models, so they are measured.

```
   sentence ─► ρ(Vₜ) ─► [decision model] ─► a ∈ K(Vₜ) ─► R ─► Vₜ₊₁ ─► ρ(Vₜ₊₁), δ ─► [narration model] ─► sentence
                               ▲                                                            │
                               └──────────────── checked by κ and [decision model] ◄────────┘
```

**One law**: a model either picks from a finite set the engine built (the decision model `D(c, q, Ω)`: context, question, options → a probability distribution over `Ω`), or writes text the engine will check (the narration model `N(c)`). Only the former touches the world, and only inside `K`. Both models' outputs are exogenous inputs, and the engine assumes nothing about model internals. Anything that yields one element of a finite set — the decision model, rules (name matching), the narration model's reading and picking, the player's buttons and card answers — is a **selector**, and any of them can fill the same place.

```
server/src/
  onto/  rules/          ontology.md, rule.md
  story/                 load.py (reads YAML), compile.py (story → Universe, V1 structure),
                         validate.py (story.md V1–V6), evals.py (interpretation evals)
  locale/ko.py           frame table 𝔗, action names λ, common text, interpretation vocabulary
  lang/                  context.py (ρ), claims.py (κ), polite.py (합니다체)
  models/                decision.py (decision model), llm.py (narration model)
  interpret.py           question tree and acceptance
  cards.py               clarify, roll, confirm and move cards
  narrate.py             narration, checks, rewrites, recaps
  jobs.py                what one narration or recap reads from a save (5.1)
  view.py                GameView, step records (api.md)
  service.py             turn protocol (lock, revision, receipts)
  api.py                 HTTP boundary (api.md)
  config.py              settings from the environment
  fun.py                 offline fun metrics (fun.md 4)
```

Models are called only from `interpret.py`, `narrate.py` and the startup check. These two files receive only `Obs` and text built from it, exogenous inputs, and story constants (style).

## 1. Frame table and names

The frame table `𝔗` in `locale/ko.py` gives each predicate a **present frame** (states a fact) and a **change frame** (tells that an atom appeared or disappeared). It is engine vocabulary, independent of any story; the story's `name` and `aliases` fill in the names. The context `ρ`, action names `λ` and claim extraction `κ` all use this one table, so the facts the screen states never drift from the facts the check knows.

| Predicate | Present frame | Change frame (added / removed) |
|---|---|---|
| `at(x, place)` | {x}은(는) {y}에 있습니다 | {x}이(가) {y}에 왔습니다 ("당신과 함께", with you, for a companion) / {x}이(가) {y}를 떠났습니다 |
| `at(x, agent)` | {y}이(가) {x}을(를) 지니고 있습니다 | {y}이(가) {x}을(를) 얻었습니다 / {y}이(가) {x}을(를) 내주었습니다 |
| `link(p, q)` | {p}에서 {q}(으)로 갈 수 있습니다 | 길이 열렸습니다 / 길이 끊겼습니다 |
| `mark` | {x}에 {tag name}이(가) 있습니다 ({x}에게 for a person) | {x}에 (or {x}에게) {tag name}이(가) 생겼습니다 / 사라졌습니다 |
| `fill` | {o}: {n}/{boxes} | {o}이(가) {n}칸이 되었습니다 |
| `regards` | {g}이(가) 당신을 {trust or fear word}합니다 | 마음이 움직였습니다 (axis and direction) |
| `stat` | 당신의 {item}: {n} | {item}이(가) {n}이(가) 되었습니다 |
| `owes` | 당신은 {h}에게 지킬 약속이 있습니다: {promise name} / {g}이(가) 당신에게 신세를 졌습니다 | 약속했습니다: {promise name} / 약속을 지켰습니다 / 어겼습니다 |
| `follows` | {h}은(는) 당신과 함께 다닙니다 | 함께 다니기로 했습니다 (…했지만 {places}에는 가지 않습니다, for one who avoids places) / 이제 따라다니지 않습니다 |
| `spent` | Screen only; not put in the context | |

A fork coming to the player (`at(g, player)` added for a fork `g`) is the one appearance with a change frame: 고를 때입니다: '{choice}' 또는 '{choice}'. Without it a fork was only a red clock named after its default; no tester saw a choice in it, and one narration made it oil seeping from the village ground (goal-4-talker 44, goal-4-explorer 16, 31). A threat's appearance has no line; its clock shows it.

Particles are chosen by the final-consonant (받침) function in `locale/ko.py`. A tag name is the presentation-layer name (section 6), or else the story's default name or the engine's default name ("이점" (advantage), "불리함" (disadvantage); "유리함" was narrated as glass, 유리, play-5-odd 9).

**Action names** `λ(a)` are one frame per schema: `go` "{q}(으)로 간다", `try` "{x}을 {approach}(으)로 다룬다" ("상대한다" for a person; "말한 대로 해 본다" for the player alone, which changes nothing), the story's `label` for a solution (kept under "무리해서" when forced), `talk` "{h}에게 {topic title}을 묻는다", and so on. Buttons, clarify cards, the decision model's options and step records all use `λ`.

## 2. Context `ρ`

`context(U, O, X) → list[Line]` in `lang/context.py` turns an observation into text. `X ⊆ E` is the **focus**: the currently visible entities this question or narration needs. A `Line` carries its section and, for a fact, its atom. In the prompt it goes out as text under a section header, and the check (5.3) finds atoms on the same lines.

1. **Facts**: one present-frame line for each atom of `F` with an entity slot in `X` and every entity slot in `E`. A flag with texts has no entity slot and is a line wherever it holds a value with a text. The player is in every focus, and `F` holds the player's regard, debts and promises with people anywhere, so without the second condition the decision model read "윤슬은 당신을 덤덤하게 대합니다" in the village while she was at the dock, and the same line for a latent person not yet brought in (963 bench requests, `decision-2/parity-context.txt`).
2. **Beliefs**: "당신이 믿는 것: {text}" (what you believe) for each proposition in `B` whose `about` overlaps `X`. A proposition with no place (a topic's `text`, a person's belief) goes in when a person who holds that topic is in `X`. Beliefs can be false, so they are marked apart from facts.
3. **Memory**: recent events in `M` that involve an entity of `X`, in change frames, written as past events.
4. **Public parameters**: for each entity of `X`, its sensory cues, persona, voice, desires, fears, looks and topic titles. A person's `wants` only when that thing is not hidden from the player. In `scene` (below) a person's `knows` too, as "{name}이 아는 것: …" (what they know), so narration and its check share what that person may state (ontology.md 3.4); interpretation never needs it.

| Used in | Focus |
|---|---|
| Interpretation layer 1 | None: the sentence alone. On the skeleton evals `ρ({player, here})` lowered accuracy from 80% to 71% (`interp-2-ctx`) |
| Interpretation layer 2 | `{player, here}` plus the entities in that slot's options |
| Narration | `({player, here} ∪ visible people in here ∪ entities of δ) ∩ E` |

A small decision model is more accurate and faster with a shorter context, so the focus trims the context to what the options need. The narration focus is trimmed to `E` so that no fact lines are made about entities not visible now, such as the place just left; those entities appear only in the change lines of `δ`.

Narration and its check read `scene(U, O, X)`, which is `context` with these changes:

- Fact lines involving people outside the focus (their regard, debts, promises) are dropped. The narration model tries to move anyone the context mentions, so someone who is not present must not appear even as a line.
- Ways out are included only from places in the focus.
- Number lines are dropped. Approach values are for rolls, and narration may not state numbers. A wound is written once, however many there are, as "당신은 다친 몸입니다" (you are wounded). A regard line at 0 says nothing yet reads as an attitude at odds with the persona ("덤덤하게", indifferently), so it is dropped.
- Obstacle progress is dropped at 0 and otherwise written "{name}: 조금씩 뜻대로 되어 갑니다 · 거의 뜻대로 되었습니다 · 뜻대로 되었습니다" (coming along · nearly done · done): the second when one box is left, the third when full. "풀렸습니다" leaked into the prose as hinges and dogs coming loose.
- The current chapter's risk clocks and deadlines go in without numbers, as "{name}: 아직 멀었습니다 · 다가오고 있습니다 · 코앞에 닥쳤습니다" (still far · drawing near · upon you). With no box filled it is the first; with one box left or all full, the third. The passage of time that the story's `style` describes (light, waves) follows this line. Their names are events ("배가 암초에 닿는다") that were narrated as happening, so the turn's steering repeats the lines whose word this turn changed and adds that what has not happened is not written as happened. Only the steering says it: in the context lines the check read "아직 일어나지 않았고" against ordinary sentences and called 13 of them contradictions in the narration bench, against 1 before (`narr-2/fix-2`). The turn's steering also lists up to three two-word phrases found in two of the last three narrations, to be said differently this time. Left out are a phrase that is part of a name or of a place's senses, the story's own wording that the context lists and the cue asks for, and one made only of names and 당신, which says who and not how ("윤슬이 당신을"). A phrase that only shares a word with them is the narration's own: when every such phrase was skipped, "젖은 손" (beside "젖은 밧줄 냄새"), "파도 소리가" and "렌즈를 응시합니다" were never named, and "젖은 손" came three turns running (play-5-talker 28–30).

## 3. Interpretation

`interpret.py` turns one sentence into a plan (a sequence of steps, `k ≤ 3`), a clarify card, or a refusal. Every question `q = (sentence, Ω)` is closed, and the engine computes `Ω` from `(Vₜ, earlier answers)` **before** calling the model. An answer outside the options, or one that cannot be read, has probability 0.

```
K_σ(O) = { a ∈ K(O) | a's schema is σ }
Σ_말 = {go, look, take, give, talk, try, declare, cut, choose}     (the 9 schemas a sentence can choose)
```

| Layer | Asks | Options `Ω` | When |
|---|---|---|---|
| 0. Rules | Should the sentence be refused; does a name appear verbatim | The story's `impossible` phrases, requests about the game, names from `λ` | Always first. Once settled, that question does not go to a model |
| 1. Kind and parts | What kind of line it is; how many actions, and which schema the first step is. If unsure or several, the narration model reads the sequence of steps | Kind `{act, say, muse}`; count `{1, 2, 3}`; step 1 from the 9 of `Σ_말` (schemas possible here, `{σ ∣ space(σ) ≠ ∅}`, first). The narration model gets the same 9 | One decision-model call, plus one narration-model call if needed |
| 2. Slots | The arguments of step `i` | Values of `space(V_{t+i−1})` consistent with earlier slots. For the destination, also the current place | **Just before** executing step `i`. Only when there are two or more values. If empty, stop at that step (refuse the sentence if it is the first step) |

Layer 1 options are a few fixed, story-free choices, which is the kind of question a small model handles best. The one exception: when a fork waits in the scene, the `choose` option's examples are that fork's own choices, since with general examples "pour the oil on the lamp" read as a `try` (qa_test/runs/play-1-*). Arguments for steps 2 and 3 are asked from the observation after the earlier step has run: in "창고로 가서 상자를 연다" (go to the storeroom and open the box), the box becomes visible only after entering the storeroom.

### 3.1 Layer 0: rules

Decided without a model.

| Rule | Result |
|---|---|
| The sentence contains one of the story's `impossible` phrases as a substring | Refuse ("이 이야기에는 그런 것이 없습니다", there is no such thing in this story) |
| A request about the game (`ko.META`: whole phrases for save, restart, questions about the rules, etc., so "저장고" or "처음부터 차근차근" stays in the story) | Refuse with guidance |
| "성장" (growth) while the player has growth to spend | Refuse, pointing to the growth card |
| The sentence equals a candidate's `λ` or a solution's `label` (ignoring spacing and punctuation) | A plan of that one action |
| An entity's name or alias appears, also as called by name ("윤슬아", "누렁아" for 누렁이) | Fills that layer-2 slot with that entity (when the value is among the candidates) |
| A name before `…에게` or `…한테` ("to") | The other party of `give` or `talk` |
| Approach words (`ko.APPROACH_WORDS`: "밀어" (push), "몰래" (sneak), "살펴" (examine), "달래" (soothe), etc.) | The approach of `try` |
| The name of something to rely on (a held thing, a trait, a tag name, a key word of a believed proposition) | The roll card's `selected` (4.2) |

### 3.2 Layer 1: kind and parts

**Kind.** Players type anything, in any form: no quotes, no addressee, no polite form, fragments ("하이", "왜 불을 켜야해", "먹을거 어디에 있어?", "누렁아~ 이리온 쭈쭈", in the saved games of real play). Form is no signal, so the same call that asks for the parts also asks what kind of line it is, from the sentence alone, over `ko.KIND`:

| Kind | What the line does |
|---|---|
| `act` | Does something in the scene: goes, looks, takes, gives, faces something, or asks someone for something, urges, threatens, deceives, brings someone along |
| `say` | Speaks to someone without asking anything of them: a greeting, small talk, a passing question, an answer, thanks |
| `muse` | Neither: talking to oneself, an exclamation, a feeling, a laugh |

Only an action may roll or spend time, so a line that is not clearly one must not become one. Asked only for parts, every line became the nearest action: "먹을거 어디에 있어?" and "왜 불을 켜야해" opened a roll on the one topic there, the wall behind the lighthouse, and "와 바람 개쎄네" spent a beat looking at the yard (qa_test/runs/intent-1-base).

The decision model's kind is taken when `p(ω₁) ≥ θ₁`; below that the narration model picks it from the same options, and with no pick the line goes to the parts. On 35 typed lines the decision model was right on 30 and the narration model on 33, and every miss of the decision model was below 0.7 ("문 발로 차" read as speech at 0.53; qa_test/runs/intent-1-probe).

| Kind | Plan |
|---|---|
| `say` or `muse` naming a thing, an obstacle or a place | The parts below |
| `say` with a person here | One `talk` step limited to small talk (3.3) |
| `say` with no person here, or `muse` | `try(player)`: narration only, no roll, no change, no time |
| Otherwise | The parts below |

A line that names something in the scene is about it: words to an animal ("누렁아~ 이리온") are an attempt on it, and "문 발로 차" or "문이 왜 안 열려?", read as speech or musing, became idle (qa_test/runs/intent-1-a).

**Parts.** The decision model is asked for the number of actions and the first step in the same call. The step options are described by `SCHEMA_ASK` in `locale/ko.py`: schema descriptions with story-free examples attached ("어딘가로 간다 (예: 북쪽 문으로 나간다, 위층으로 올라가자)" …). The options are all nine of `Σ_말`, with the schemas possible here first. The first step is **sure** when its `ω₁` is a schema possible here and `p(ω₁) ≥ θ₁` (0.7). If it is sure and the count's `ω₁` is 1, that one step is the plan.

Otherwise the narration model **reads** the sentence. It gets the same descriptions, numbered in the same order, and writes the numbers of the sentence's actions in the order they happen (temperature 0). A schema identical to the one just before it is one action told in two clauses ("무릎을 꿇고 빈다", kneels and begs), so the two merge; up to three are used. If the decision model was sure but the first number is not a schema possible here, the reading counts as absent.

The first matching row from the top applies.

| Decision model | Narration model's reading | Plan |
|---|---|---|
| Sure, count 1 | Not asked | The decision model's first step |
| Count 2 or more | Two or more steps | The sequence of steps read |
| Sure | Anything else | The decision model's first step |
| Unsure | One or more steps | The first step read |
| Unsure | None | `try(player)` |

If layer 0 settled the plan, nothing is asked. Why the split and the thresholds:

- **Reading.** The decision model reads one sure action well, but asked step by step it attached a next step even to one-action sentences and got about one in five multi-action sentences right. The narration model's reading gets most of them right and matches it on one-action sentences. The decision model's count filters first, so the reading is called only for unsure or multi-action sentences (qa_test/runs/decision-1).
- **`θ₁` = 0.7**, above the `θ` (0.5) of other questions. Between 0.5 and 0.7 the reading was right more often (24 sentences to 4), mostly on short spoken sentences ("같이 가자", let's go together, read as movement). Raising it gave +24/−4 across three benches, at the cost of more reading calls (qa_test/runs/misread-1).
- **Impossible schemas.** A first step that is not possible here leaves its slot empty at layer 2, and the sentence is refused with what that schema lacks here (state and `revision` unchanged): "여기에는 집을 수 있는 것이 없습니다" (nothing here to pick up) for an empty floor, "여기에는 말을 걸 사람이 없습니다" (no one here to talk to) for a call to someone elsewhere, one line per schema in `ko.LACK` (a give says whether it lacks someone here or a thing in hand). The bare "지금은 할 수 없는 행동입니다" (you cannot do that now) gave no reason, and players met it in 4 of 6 games without telling why (play-6-odd 18, 23; play-7-explorer 3, 38, 45). Offering only the possible schemas made both models land on a wrong action instead, so all nine are offered and a sure but impossible answer counts as unsure. With the asked schema removed from the scene, refusals went from 0 to 155 of 207 sentences and wrong actions from 115 to 50 (qa_test/runs/misread-1).

### 3.3 Layer 2: slots

Just before executing step `i`, its slots are asked together in one call, using the observation at that moment. Slots with only one value, and slots layer 0 filled, are not asked.

| Slot | Kind | How it is asked |
|---|---|---|
| Destination, target, thing, other party, topic, latent, fork option | Intent | The values of `space`, as `λ` or names |
| Approach | Intent | Four. After the `try` target is settled |
| Strain | Judgment | `natural`, `forced`, `불가능` (impossible). If `불가능`, refuse the sentence |
| Tone | Judgment | Three, asked only for an `act` line |
| Claim | Judgment | Only when the tone is `deceive`. For each claim sentence in the story, a yes/no question "플레이어는 이렇게 말합니까?" (Does the player say this?), asked on the sentence alone with no context. The claim with the highest "yes" at or above `θ` is taken; if none, there is no claim |
| Reliance | Judgment | **Not chosen.** The roll card shows the target number and modifiers, so the player chooses there; layer 0 name matching sets the default, and the model only filters out what is unrelated to this attempt (4.2) |

**Out of reach.** Before the slots are asked, a sentence whose named target is out of reach is refused with that cause instead of the bare refusal. The causes are:

- an obstacle in sight blocks a person, thing or way the sentence names: "{장애물}이 {대상}을 막고 있습니다", "{장애물}이 {곳}으로 가는 길을 막고 있습니다";
- a `talk` or `give` names someone the player met who is not here: "{이름}은 여기 없습니다";
- a `talk` or `give` that names no one, where everyone here is blocked: the first of them, as above ("왜 못하지?" beside a guarded 도해);
- a `give` names a known thing the player does not hold: "{물건}을 지니고 있지 않습니다".

This also happens when the schema has values here but none of them is anything the sentence names. Otherwise the slot fell to another target: "도해의 아구창을 날린다", with 도해 behind a guard dog, became a try on the letter. A hidden obstacle is not a cause: it is not in the observation, so the step runs and is blocked, which reveals it. Players met the bare refusal in every playtest and could not tell a guard from a broken game (qa/findings.md).

**Topics are named.** A story topic is offered only when the sentence names it: a word of its title, without a final particle, of two syllables or more, or its last word, the head noun ("담장" or "등대" for "등대 뒤 담장"; "폐허" or "길" for "폐허로 가는 길"). `chat`, favors, `come` and `stay` are always offered. With every topic offered, the models put any question near the place on its one topic ("먹을거 어디에 있어?" → the wall, qa_test/runs/intent-1-base), and a topic rolls, so a passing question became a roll. By the head noun alone, 5 of the decision bench's 18 topic questions lost their topic ("폐허 가는 길"); by any title word, 1, and no other topic came in (qa_test/runs/intent-1-probe).

**Small talk.** A `say` line is a `talk` whose topic is `chat` or a named topic, and whose tone is `polite`. Threats and lies change how people regard the player (rule.md 5.1), so they come only from an `act` line. A `say` line names its person or, unnamed, goes to the people here as an intent slot.

For the destination, the **current place** is offered along with the ways out, unless the sentence names a way out ("마당에서 마을로 간다", go from the yard to the village). Choosing it means the move is already done: that step is skipped, or, if no step has run, the sentence is refused with "이미 …에 있습니다" (you are already at …) when it names this place, and otherwise with "여기서 갈 수 있는 곳은 …입니다." (from here you can go to …), since a walk about the place asked where one can go (play-3-explorer 9). "등대 앞 안에서 따로 갈 곳은 없습니다" (nowhere else to go inside the lighthouse front) read as broken Korean for an open place (play-6-odd 8, play-6-talker 26). Offered only the ways out, the decision model picked another way even when the sentence named the current place in other words; but it is also sometimes sure of the current place for sentences that pass through here and go on ("열린 문으로 들어가 꼭대기까지 오른다", go in through the open door and climb to the top). So, as with layer-1 refusals, the current place is accepted only when the narration model picks it too (qa_test/runs/misread-1).

### 3.4 Acceptance `δ_θ`

In one question's answer distribution, `ω₁, ω₂, ω₃` are the options in order of probability. `θ` is a setting, initially 0.5 (adjusted by the measurements in section 9). Layer 1 step 1 uses `θ₁` instead (3.2).

| Question | `p(ω₁) ≥ θ` | Otherwise |
|---|---|---|
| Layer 1 step 1 | Accept if `p(ω₁) ≥ θ₁` (with a count of 2 or more, the narration model's reading may set the sequence). A schema not possible here goes to the Otherwise column | The narration model's reading (3.2). If the first step read is an impossible schema, refuse the sentence. With no reading, the whole step is `try(player)`: narration only, with no roll and no change. Layer 2 is not asked |
| Layer 1 count | One step if `ω₁` is 1 | Use `ω₁` (1 if there is no answer) |
| Layer 2 intent slot | Accept. But for the `try` target and approach the narration model's pick always comes first, and the current place as destination goes to the Otherwise column | The narration model gets the same context, question and options, numbered, and picks one (temperature 0). With no answer, the player picks on a clarify card `{ω₁, ω₂, ω₃}` (all values if there are three or fewer). For the approach alone, the player's highest stat (ties broken by approach order) is used instead of a card: its modifier is then the largest, and the roll card shows the approach |
| Layer 2 judgment slot | Accept | `ν₀` |

The narration model answers only at layer 1 and at intent slots, which decide what the player aims at, never how it resolves; so both models erring together cannot produce a gain in a judgment slot. Where the decision model is unsure of an intent slot, the narration model is almost always right, and for the `try` target and approach it is right even where the decision model is sure and wrong, so its pick comes first there (qa_test/runs/decision-1).

**Conservatism.** Every part of an executed action is set by an answer with probability `≥ θ`, the narration model's reading or pick (layer 1 and intent slots only), a rule, the player's choice, or `ν₀`; otherwise the whole action is `try(player)`, which changes nothing. An unsure judgment slot gives neither gain nor added risk.

### 3.5 Decision model calls

`decide(state, questions)` in `models/decision.py` sends one context text and several closed questions at once, and gets back probabilities over the options of each question. An answer outside the options, unreadable, or past the time limit becomes an answer with probability 0 on every option. Latency grows with the number of questions, so one call carries 2 questions at layer 1, the step's asked slots at layer 2 (claims go in a separate call, one question per claim), and 1 for the roll card's relevance.

## 4. Cards

A card is the engine stopping to ask the player. It creates no event and does not advance `t`, and its content is a function of `(Vₜ, plan)` (a roll card also reads one relevance answer). The presentation layer holds only one pending card, and it is discarded when a new sentence or button arrives.

```python
@dataclass(frozen=True)
class Card:
    id: str                 # unique per game
    kind: str               # clarify, roll, confirm, move
    plan: Plan              # the stopped step (fixed arguments) and the rest
    echo: str               # the player's sentence or the button label
    options: tuple[Option, ...]
    selected: str | None    # default option id (roll card)
```

### 4.1 Clarify

When neither the decision model nor the narration model settles a layer-2 intent slot. The options are the `λ` of `{ω₁, ω₂, ω₃}` and "그만두기" (cancel). The answer fills that slot and the plan continues.

**Detour.** When a step would be refused because what the sentence aims at (a person, a thing, a way) is blocked by a visible obstacle `ob` here, the step becomes a clarify card about `ob` instead. The question names the block and asks what to do ("사나운 누렁이가 도해를 막고 있습니다. 어떻게 할까요?"); the options are `ob`'s solutions whose condition holds in the view, each the `try(ob, approach)` with its `rely`, under its `label`. A pick continues the plan as that try, with its roll card (4.2). The card is the hint: the block and the ways around it, all public parameters of a visible obstacle, so nothing hidden leaks and nothing runs until the player picks. With no solution holding, the step is refused with the reason as before. Refused with the reason alone, a player kept talking to a guarded person and got five refusals in a row with no reply (qa_test/runs/loop-1, talker 11–15). A `go` that names no open way out, aimed at a way, at nothing or at the place itself ("이제 출발한다", "눈더미를 넘는다"), meets the first visible blocked way out of here the same way, with that way's blocker as `ob`: told only the open ways ("여기서 갈 수 있는 곳은 마구간, 주막입니다."), a player who wrote the chapter aim nearly word for word read the way forward as closed and gave up (qa_test/runs/play-10-human).

**Ways when stuck.** A sentence read as idle (`try(player)`, 3.1) right after a sentence that changed nothing (refused, or idle itself) becomes a clarify card "무엇을 해 볼까요?" with at most three options: `recommend(U, O)` (rule.md 9), then the holding solutions of the plain obstacles here, then the open ways out, each under its button or solution label. A pick runs that action: a roll gets its roll card, a way out is taken without a move card, since the card already chose it. With no option, the sentence is the muse below. The request still counts as idle (fun.md F1). One muse is answered with a hint; two in a row are a player asking what to do: after a refusal, "이제 뭐하지?", "어쩌냐" and "벌써 막힘" each got scenery with the same hint, and the round ended there (qa_test/runs/play-10-human).

### 4.2 Roll

If the plan's next step `a` is a rolled action, the engine stops just before executing it and puts up a roll card. Whether it rolls is decided from the observation: `try(x ≠ player)` always; `talk` when the topic is not in `B` and `free_when` is false on what is visible, or when it is a request without goodwill (rule.md 5.1). The visible and world verdicts agree because story.md V3 limits the atoms of `free_when` to visible ones. Only a hidden block makes this decision differ from execution, and then the block is revealed through the card (`blocked`).

| Field | Content |
|---|---|
| `plan` | The step with `a`'s intent arguments and its judgment arguments other than `rely` fixed, plus the rest of the plan |
| `options` | One for each relevant allowed value of `rely` (below), plus one "기대지 않음" (rely on nothing): action id, name, whether using it uses it up, its `rely` value and whether it is forced, `preview(U, O, a_rely)` (rule.md 3.4). Ordered by the rows of the `rely` table in rule.md 2, within one kind by the story's declaration order (tags by slot order), with "rely on nothing" last. For a `try` on something, the same list again with `strain = forced` when forcing buys a box there (rule.md 7) or the sentence forced: forcing is a toggle on the card, not a word the model must catch, and the player sees what it buys and what it costs |
| `selected` | The `rely` option layer 0 set; otherwise "rely on nothing" |
| `echo` | The sentence or button name, plus the names of the slots layer 2 read (target, approach, strain, tone) |

**Relevance.** The rules never ask whether a `rely` fits the attempt (rule.md 2), so before the card is placed only what is relevant to this roll is kept. Kept without asking: the `rely` values listed in the target obstacle's solutions, every edge tag in reach (rule.md 3.2), companions, the value layer 0 named, and whatever an earlier card for the same attempt offered. The rest goes to the decision model once. The context is the step's name, the target's appearance and the player's sentence; the single question is "이 시도를 실제로 돕는 것은 무엇입니까?" (What actually helps this attempt?); the options are a description of each remaining value (a trait's text, a thing's appearance, a known proposition's text, a bond name) plus "아무것도 돕지 않음" (nothing helps). Only values whose probability is at least `θ_rely` (initially 0.1) are kept. Asked yes/no value by value, the small decision model gave the same answer for every value in a scene, so the values are laid out in one question to be compared. With no answer, nothing is filtered, so that a model failure does not take a choice away from the player.

What a card offers is kept in `P` per attempt (schema and intent arguments), so a help once offered for an attempt stays while it is allowed; what was dropped is asked again with the next sentence. Asked anew with each sentence, the same help came and went on identical attempts (play-2-explorer 14, 42; play-4-bold 8, 12, 15; play-4-odd 25, 31). Dropping the sentence from the question instead made every verdict fixed but cut exact answers on the decision-1 reliance items from 0.53 to 0.31: the sentence says how the attempt is made. An edge is kept unasked because its name, often the default "이점", is all the model would have to judge it by, and an edge exists to be spent.

Acceptance is `{card, pick}`, where `pick` is one action id from `options`. The service executes only if the request's `revision` matches the current one, `card` is the id of the pending card, `pick` is one of that card's options, and `admits(U, Vₜ, pick)` holds. A stale `revision` gets 409, and a `pick` outside the options at the same `revision` gets `refused` (api.md). This acceptance confirms exactly that action, so a high-risk roll gets no separate confirm card. The risk and modifiers shown on the card equal the values at execution (rule.md 3.4).

### 4.3 Confirm

A step that does not roll but has high risk, namely `choose`, and a `give` or `cut` that a sentence chose. The options are "고른다" (choose) and "그만두기" (cancel), and the card shows the name of the choice and the names of its effects (for a give, the thing going to that person; for a cut, the scene ending and the threats drawing closer). A give's card also offers `show(x, h)` by its name, "{h}에게 {x}을 보여 준다": the player who meant to show keeps the thing without retyping. A sentence that says it shows ("보여준다") matches the show button's name at layer 0 and runs at once. A sentence read as waiting spent the rest of the scene with no card (qa/findings.md). A high-risk step does not run until that exact action is accepted, and the acceptance is valid only at that card's `revision`. A thing given does not come back, and sentences that only showed something were read as giving it: the player's only item was gone with no card (play-2-odd 3, play-3-talker 3, play-4-talker 7). Asking for every give from a sentence keeps that one rule instead of lists of showing and giving words; a button's give runs at once.

### 4.4 Move

A `go(q)` step chosen by a sentence (`origin` is the sentence, also for the rest of its plan after a card it opened) stops just before executing and puts up a move card. A sentence chooses its destination by meaning even when it does not name the place exactly (section 3), so the player sees where they are going and who comes along and leaves with one tap, and a misread move never runs. A sentence that names the chosen place (its name or an alias) and no other way leaves at once, as a button does, unless a companion avoids that place: the destination is not in doubt, and a card that only repeated it cost one more tap on every typed or chip-filled move (play-6-ui 7, 15; play-7-explorer 7, 21, 33; play-9-ui 3, 6, 12). A move chosen by a button needs no card, since the button is the confirmation.

A sentence that names a person here who could be asked to come (`talk(h, come)` is a candidate) also gets the card, with one more option for the sentence's way: the same place with `h` asked first, its plan `[talk(h, come), go(q)]` (`plans` in the card), chosen by default. "윤슬과 같이 마을로 간다" went alone, the second half dropped. The ask may roll and fail like any `come`; then the turn stops before the move.

| Field | Content |
|---|---|
| `options` | `{id: action id, label: place name, with: the person asked first (only on the companion option, whose id joins its plan's action ids with `+`), effects: [for each companion "{name}과 함께" (with {name}), or for avoids "{name}은 남음: {fear}" ({name} stays, with the character's `fear` as the reason); beside an option that asks `h` first, the plain option of the same place adds "{name}을 두고 감" (leaving {name})]}`. When the sentence names the chosen place alone, so the card is up only because someone stays, only that place. Otherwise every current `go` candidate, the sentence's choice first, the rest in candidate order |
| `selected` | The `go(q)` the sentence chose |
| `plan` | That step and the rest of the plan. Choosing another place goes there, and the rest of the plan fills its slots again from there |

Acceptance is `{card, pick}`, where `pick` is one action id from the options. Cancelling is closing the card.

## 5. Narration

`narrate.py` builds turn `n`'s narration when it is requested and caches it in the presentation layer; a cached narration is not written again. The **visible change** `δ` is the in-order composition of this turn's steps' memory projections `seen[player]` (ontology.md 3.2); the raw `Δ` is not used. Each step is projected over its own before and after, so what happens after you leave is not included.

### 5.1 Input

| Section | Content |
|---|---|
| System | Role, format rules (5.2) |
| Context | `scene(Vₜ₊ₖ, X_N)` (section 2) |
| What happened | For each step, `λ(aᵢ)`, the outcome name ("성공", success), and lines rendering `δ` in change frames. A way cut or opened in both directions is one line, "A와 B 사이의 길이 끊겼습니다" ("등대 앞으로 가는 길이 끊겼습니다" read oddly while standing there, play-4-talker 40) |
| New tags | The default names of tags created this turn. The model writes the name it uses for each in the narration as a final line `태그: 이름` (tag: name) |
| Previous narration | The narration of the last 3 turns (presentation layer) |
| Said before | For each speaker, up to 4 earlier exchanges older than the previous narration: the player's sentence and that person's quoted lines (`said`, section 6). The steering adds that they keep to what they said and do not say it again. The 3-turn window alone let an answer drift once it fell out (loop-1 base) |
| Lived together | For each speaker, up to 4 events of `shared(g)` (ontology.md 3.4) older than the previous narration, as step lines. The steering adds that they remember these and bring them up in their own words when the talk turns that way. The check's context gets the same lines, since they are facts |
| Player | This turn's sentence (if any) |
| Style | The story's `style` |
| This narration | The last few lines. For each person present whom this turn's actions named, who started or stopped following, or who moved with you: a persona summary and voice. On a turn the player arrives, the first sensory cue of the current place that has not yet appeared in the last 3 turns of narration (it counts as appeared when at least half of its character bigrams overlap); on any other turn, or when all have appeared, a line says to depict people and what changed instead of scenery. The pace words of the risk clocks and deadlines whose word changed this turn (sky, light and waves change only as much as this pace); when none changed and nothing struck or ran out, a line that time did not move, so sky, light and weather are left out. "바뀐 것을 보이고 인물의 반응이나 눈앞의 것으로 끝냄" (show what changed, and end on a person's reaction or what is in front of you). With no one at the player's place, these lines leave people out and say no one else is here: asked for people where nobody stood, the narrator brought back whoever the last turns told (`narr-3/ending-after` game 0, 12–15) |

Small models follow the end of a prompt best, so style and this narration come last (the same position as SillyTavern's Author's Note or the card spec's `post_history_instructions`). Sensory cues rotate one at a time so the same scenery does not repeat every turn. Scenery and time are shown when they change: with a cue and the pace on every act turn, the sky, wind and waves took one or two of four sentences each turn, and a failed detour roll was told as weather alone, without the dog that stopped the player (3 of 15, qa_test/runs/loop-1/presume-summary.md). Leaving the lines out was not enough, since the story's style still asks for time in the sky; saying that time did not move cut weather sentences from 51% to 34% of act narration (qa_test/runs/loop-1/weather-summary.md). On a rewrite, the points to fix are appended after this narration.

### 5.2 Generation

The narration model is always called in non-thinking mode (`enable_thinking: false`), with an output limit of 500 tokens. Narration must fit on one screen without paging (ui.md 2), so accepted text is at most 4 sentences and 200 characters including spaces; in a turn with a chapter change or an ending, at most 160, plus a recap of at most 100 (5.5); a reply to small talk or musing is shorter (below). Drafts never stream to the player; only text that passes the check goes out.

**Replies follow the kind of line** (3.2). A turn is a **talk reply** when every step is small talk (rule.md 4.1) that nothing blocked, a **muse reply** when it is only `try(player)`, and an **act reply** otherwise.

| Reply | Size | What the steering asks instead of the place cue, pace and close |
|---|---|---|
| Talk | 3 sentences, 150 characters | Open on the person's answer: one gesture of theirs and their line, no scenery. They answer from what they know and their own worry or wish shows through; what they do not know they say so or turn to their own concern |
| Muse | 2 sentences, 110 characters | `당신` only spoke or thought, and did nothing. A person here reacts to it briefly; with no one, one moment of the surroundings answers its feeling. `당신` does not move or act. The reply ends on the hint below |
| Act | As above | The place cue, pace and close (5.1) |

What happened tells a muse turn as "당신이 말하거나 혼잣말을 했습니다" instead of `λ(try(player))`, and every person here is a speaker. With every reply built like an act, a greeting got four sentences that opened on scenery ("밧줄 냄새" in 19 of 20 small-talk replies, "눈을 반짝이며" in 16), and musing with no one there was ignored or turned into an act: "당신은 말한 대로 행동을 이어갑니다", the idle label leaking (6 of 16; qa_test/runs/typed-1/base-summary.md).

**A muse ends on a hint.** A player talks to themself mostly when they do not know what to do next, so the GM answers with a way forward. The engine picks it: the first of `recommend(U, O)` (rule.md 9) not hinted in the previous 3 narrations, else the first. It is told by its button label, so it names only what the player can already see, and its targets join the narration's ids. The steering asks for it as something noticed, never as done or ordered: with people here, through a speaker's line or gesture; alone, as the moment of the surroundings that answers. The narration entry keeps the hinted action for the rotation. With no hint, the reply is as above. Without it, every muse alone got the same shape, "목소리가 바람에 흩어집니다" (4 of 4 per game; qa_test/runs/loop-1/after-summary.md), and moved nothing.

**Only what happened is answered.** The player's sentence reaches the narrator whole, but the rules decide what it did, and the reply must not do more:

- In an act reply, a person here whom no step names was not spoken to, so the steering says they do not answer the sentence or give what it asks. A question typed to 도해 behind the dog became a detour roll that failed, and 도해 still answered it ("…기름은 밑에 두게"; 10 of 10 failed detour turns, qa_test/runs/loop-1/detour.json).
- A talk or muse reply that a sentence presumes an event for, one that is not in what they lived through or the narration, says it did not happen or that they do not know, and never plays along. Asked "할아버지가 열쇠 빌려줄 때 무슨 말 했지?" after the favor was refused, 윤슬 made up the lending (1 of 2, qa_test/runs/loop-1/long-summary.md).

**The prose carries the game.** The screen has no pictures, so the writing must do what art and voice do elsewhere, as a narrator does in Baldur's Gate 3: one sharp concrete detail per sentence, chosen for this person and this place, instead of stock phrases ("눈을 반짝이며", "코끝을 스칩니다"); people who sound like themselves, whose lines answer and also let a want, a fear or a habit show; and a last sentence that leaves an echo or a tension rather than a summary. These are rules of craft and name no story; the story's `style` sets the tone they serve.

Format rules:

- 합니다체 and `당신`; no numbers, no lists of options, never the player's feelings.
- What happened is a record: its frames ("…생겼습니다", "뜻대로 되어 갑니다") and tag names are told as what is seen, not copied. They reached the screen as written (goal-6-odd 3).
- When there is a success or failure, the first sentence makes it clear; a failure shows things going wrong.
- The player's sentence is read for its meaning, not copied, and shown as the actions and words of `당신`. Questions are answered from facts in the context; anything else is not yet knowable.
- A person spoken to or handed something answers directly, from where they stand, in double-quoted dialogue attributed to them and true to their persona and voice, without copying sample lines and without any form of address for you.
- People know only what the context and what happened state; otherwise they say they do not know or change the subject.
- A companion left behind this turn (their `avoids`) is shown parting, with their `fear` as the reason; after that they are not in the scene.
- Someone who begins to follow the player this turn but avoids places says so: the change line names the places avoided for good ("…함께 다니기로 했지만 …에는 가지 않습니다"; the record has no state to read an `until` against), and the steering, which reads the current state, names every place still avoided and adds their `fear` and that they promise no farther. Agreeing out loud to the very trip they then refused read as a broken promise (play-3-talker 27, 32; play-3-explorer 21).
- An obstacle this turn moved forward is named in the steering: short of full, as a small visible change that must not read as done; full, as what changed before the player's eyes. The prose said the lamp pushed back the dark at 1/4 and the flame poured out at 3/4 (play-2-bold 6–7, play-4-odd 28).
- A clock or threat that came to pass this turn, and a deadline that ran out, are named in the steering to be shown in one sentence each. A bridge collapse and a missed sunset went untold behind the turn's other changes (play-4-talker 28, 40; play-4-odd 29; play-4-explorer 29).
- A step that something hidden blocked is named in the steering as not having happened: no one answers and nothing is done; the narration shows what stood in the way. A blocked talk was answered in full, so testers could not tell what the dog had stopped (play-4-explorer 10, play-4-talker 21). The step still spent its beat, so its lines in what happened carry the scene end, arrival, chapter change or ending that beat brought; with only the reveal, the sunset went from 0 to 1/3 untold (`narr-3` turn 6).
- What a roll leaned on is named in the steering as the resource the attempt drew on, to be shown once in use; a step something hidden blocked rolled nothing and leaned on nothing. A leaned-on letter never appeared in the prose (play-4-talker 6, play-4-odd 4).
- A sentence's attempt that rolled is told as the sentence said it: the steering says the attempt's motion stays the sentence's own and only the result follows what happened. The odds never read the verb, so the narrator chose its own, and "kicked" became "shouldered".
- A scene end and an overwritten tag are change lines of their own, from the step's happenings (ontology.md 3): "장면이 넘어가고, 다가오던 일들이 한 걸음씩 더 다가옵니다" before the clocks it moved, and "{owner}의 {old}이 밀려나고 {new}이 자리 잡았습니다". A wound tag added or removed reads "당신이 다쳤습니다" or "당신의 상처가 조금 나았습니다".
- A flag with texts (story.md 2.2) is a fact line in every context while its value has a text, and its change is a step line in the author's words. A consumed thing is "{name}을 다 썼습니다", and a person in sight giving up a belief is "{name}은 더는 이렇게 믿지 않습니다: {text}", the one place a person's belief reaches narration.
- What a look found is named in the steering: each thing or obstacle a look step reached, with its look text, to be shown. A letter was read and none of its words were told, because its look sat among every entity's public parameters (play-5-talker 35).
- A fork that came this turn is named in the steering with its choices, and the narration ends on that question, asked by someone present if anyone is; the usual close gives way. Told only as a change, it fell behind the lamp's first light and a person's arrival, and no narration asked it (goal-4-check 6, goal-4-talker 44).
- A turn that only spent growth gets two sentences and 100 characters and is told as the change settling in, without the place cue or a replay of the last scene. Told as a turn, a growth pick replayed taking the oil or listed the scenery again (play-3-talker 24, play-3-explorer 30, play-3-bold 7).
- A turn that stopped before the rest of the sentence (at a card, after a failure, or at a step that could not be read) says which action has not happened yet, or that the rest has not, so the narration stops short of it. Given the whole sentence, the narration lit the lamp on the look before its roll card (play-3-odd 18, play-3-explorer 41).

### 5.3 Check

1. **Rule check**, without a model:
   - Length: sentence and character counts. A quoted line counts as part of its sentence, and a sentence that is only a quote attaches to the preceding one that names the speaker.
   - Form: Markdown emphasis (`*`, `\`, backticks) is removed before the check; it reached the screen as "\*컥\*" (play-4-talker 24). 합니다체 (`lang/polite.py` fixes 해라체 endings), no second person other than `당신`, no list or option shapes, numbers or parentheses (sounds and gestures go in sentences too), a `태그:` line of at most 12 characters, no names of hidden entities.
   - Facts, read outside quotes only (dialogue is not something happening now): obtaining a thing not held (`at(x, player) ∉ F'`), handing over a thing held, or reaching a place not reached (`at(player, place) ∉ F'`), each found as a name plus a verb of that kind.
   - Presence: a person who is not at the player's place may not stand as a subject (`윤슬이`, `노인은`) outside quotes, even when a change names them (their regard, a thing they got). Two exceptions: a companion left behind this turn, in a sentence that tells the parting (`ko.PARTING` words or the place they stayed at), and in the ending, anyone the legacy lines name, in a sentence that sets them far off (`ko.AFAR`) (5.5).
   - Repetition: a phrase of 10 or more characters, spaces excluded, identical to the last 3 turns of narration, to the sample lines of a person speaking now, or to that person's lines in said before (about three words; shorter overlaps are common phrasing). Punctuation, names, `당신` and any stretch of 4+ characters shared with the story's own wording in the context (senses, looks, what people know) do not count toward the 10, as for the worn phrases (5.1): counted, they sent back a third of the rewritten turns for a name between quotes ("윤슬이 고개를 저으며 당신") or a fact retold in the story's words ("새벽에 고깃배를 몰고"; qa_test/runs/loop-1).
   - Address: a form of address for you in dialogue that guesses age or gender, like 아저씨 (mister) or 언니 (big sister) (`ko.ADDRESS`).
2. **Claim extraction** `κ` (`lang/claims.py`): from each sentence, `Σ` literals are extracted using names and aliases and the verb forms of the frame table's change and present frames. Taking `F'` as the facts of `Vₜ₊ₖ`, a positive literal `φ` is accepted only if `φ ∈ F'`, and a negative literal `¬φ` only if it follows from `F'` and `C` (e.g. `at(key, A) ∈ F'` gives `¬at(key, B)` by C1). A negative claim such as "여기엔 경비가 없다" (there is no guard here) is not accepted, since there may be a hidden guard. A plain obstacle told as opened, broken or giving way (fleeing, stepping aside, crossed) claims its full `fill`, so a failed roll told as the target yielding is caught like an unopened door told as open. Sentences that cannot be rendered in `Σ` (smells, weather, expressions) contradict no state, so they are free. Growing `Σ` widens what the check covers and narrows narration's freedom.
3. **Decision model check**: for each sentence that passed 1 and 2, one choice question ("이 문장은 문맥과 비교해 어떻습니까?" (How does this sentence compare with the context?): 맞다 (correct), 사실과 어긋난다 (contradicts the facts), 없는 사람·물건·길을 지어냈다 (invents a person, thing or way that does not exist)) is asked with the context `ρ(Vₜ₊ₖ, X_N)`, all in one call. If the probability of "맞다" is at most `1 − θ_N` (initially 0.5), the sentence is rejected, and the more probable of the two faults is given as the point to fix. Asked yes/no per fault, the model answered "no" to both and missed most bad sentences (qa_test/runs/decision-1). When the turn rolled an attempt a sentence made, the context also holds that sentence as the attempt (its manner as said, its result as happened), so an attempt told with another verb ("걷어찬다" told as "어깨로 들이받는다") is a contradiction; the odds never read the verb.

Acceptance reads only `Vₜ₊ₖ` (non-interference). Classifying a fault as invention or leak requires looking at `S`, so it is done only in offline analysis and never fed back to the model.

### 5.4 Rewrites and fallback

If any sentence is rejected, the narration is rewritten with that sentence and the reason (the rule check's name, the contradicted fact line) as feedback. Feedback reads only `(Vₜ₊ₖ, δ, draft)`. There are at most two rewrites. If the third attempt is still rejected, the rejected sentences are deleted from the draft with the fewest rejected sentences (the later one on a tie), since a rewrite can be worse. If everything is deleted, only the change lines of `δ` remain as the narration. Each attempt gets a different seed. The stream format is in api.md 4.

### 5.5 Tag names and recaps

Names from the `태그:` line are kept in the presentation layer, keyed by `(mark atom, t at creation)`. When a slot is rewritten, an old name does not attach to the new tag, and a name is shown only while its atom is in `F`. `R` and conditions do not read this table.

In a turn where a chapter change or ending happens, a recap of the finished chapter `k` is written after the narration, in the same way. Instead of 5.1, its input is first what passed with people in that chapter (up to 4 lines of the ledger, api.md 3: things handed over either way, promises and how they ended, companions who came or stayed, a trust that ended the chapter moved) and a line per choice made ("당신이 고른 길: …"), whether or not a roll marked them, then up to 5 notable events from that chapter's `M` (improvisations that raised `fill` by 2, obstacles overcome, claims, declarations, wounds, threat arrivals; choices are told by their own line) rendered in change frames, the last always the step that closed the chapter. Told from the notable steps alone, the scenery won (goal-6-bold 9); the check is the same. `GET /games/{id}/chapters/{k}/recap` returns it in the same stream, and it is kept only in `P`. The ending's steering replaces the place cue, pace lines and usual close: it lists the legacy lines and asks for the change, then one legacy line, then the story's `frame` as the last sentence; with no legacy lines, the change and the frame. The legacy lines are what the player leaves behind, rendered as context facts. They are trust that moved from its start for someone the player met (a witness in `M`), debts to or from the player, things the player saw go to an agent that did not start there (from `M`), companions, and from the ledger every promise kept or broken and every companion who stayed behind, which no atom remembers; each person they name who is not here adds a line saying so (with the place when the player sees it). They also go into the check's context with the frame. Anyone not here appears only far off and gets no new event, and the rewrite feedback for such a person says how to keep them: far off, where they are. Before this, the pace line and the usual close outweighed the frame: no ending told whether the boats came home, and none named a person (play-1-talker 46, play-2-talker 48). Re-narrating the round-2 endings gave the frame in 6 of 6 and a legacy line in 6 of 6, with one invented event for an absent person (`qa_test/runs/play-2-reending-3.txt`).

## 6. Presentation layer `P`

A game is `G = (story, seed, S, L, P)`. `R`, `K`, conditions and observations do not read `P`. When the screen and the narration input read `P`, they are reading earlier model outputs and player inputs, that is, exogenous inputs.

| Field | Content |
|---|---|
| `revision` | Rises by 1 on each request that changes the state or the pending card. Refusals and receipt replays do not raise it |
| `turns` | For each turn `n`: the request kind (sentence, button, card answer), the sentence, and the range of executed events `t` |
| `requests` | Records of requests that ended without events (clarify, refusal, card discard), and each sentence's outcome with the seconds its interpretation took (`secs`) |
| `card` | One pending card, or none |
| `narration` | Turn `n` → accepted narration, attempt count, deleted sentence count, the seconds it took (`secs`), and `said`: speaker → their quoted lines. A quote belongs to the speaker its sentence names (name or alias), or to the only speaker when it names no one; any other quote is not kept |
| `recap` | Chapter `k` → recap, with the same fields |
| `tag_names` | `(atom, t)` → name |
| `relevance` | Attempt → the `rely` values its roll cards have offered (4.2) |
| `receipts` | Request id → (body hash, response) |

## 7. Turn protocol

A player's **turn** `n` is one request that executed at least one step. It consists of ontology steps `t, …, t+k−1` (`1 ≤ k ≤ 3`) and one narration; a request that stopped at a card and continues once the card is answered is a new turn. `command(game_id, request_id, revision, body)` in `service.py`:

```
lock(game_id)
  1. If receipts[request_id] exists with the same body hash, return the saved response. If the hash differs, refuse (409, with the current view)
  2. If revision ≠ P.revision, refuse (409, with the current view)
  3. Build a plan from the body
       action   → check admits → plan [a]
       card     → put the answer into that card's plan (an accepted roll or confirm marks that step "accepted")
       cancel   → discard the card, no event
       text     → layer 0, layer 1 → plan, clarify, or refusal
     A new sentence or button discards the pending card
  4. For each step
       set aᵢ through layer 2 (clarify → place a card and stop; empty slot → stop; going to the current place → skip)
       stop unless admits(U, Vₜ, aᵢ)
       if the step rolls and is not accepted, place a roll card and stop
       if it is high risk without a roll and not accepted, place a confirm card and stop
       step = resolve(U, S, h, aᵢ, roll(seed, t)), append the event and S ← S ⊕ Δ
       stop on an ending, or a fail or blocked result
  5. If at least one step ran, advance turn n and record it in turns. With neither a step nor a card, refuse
  6. If the state or the card changed, revision +1, write the receipt, and save L and P at once (ontology.md 6)
  7. Respond: CommandResult (api.md 2)
```

- Layer-2 questions are asked inside the lock. Requests for the same game queue up one at a time; other games are not blocked.
- Between the steps of 4, the observation is recomputed each time. What an earlier step revealed appears in the next step's slots.
- A request that accepts a roll card runs that step without calling a model. If a remaining step has layer-2 questions, they are asked then, and that time is spent while the dice are rolling.
- The game is saved before responding. If a response is lost, the client resends the same `request_id` and body and gets the same result at 1.
- Narration is requested separately, after the response. Narration does not change the state, so it is built outside the lock, and the lock is taken only to write the cache into the save. When narration requests for the same turn overlap, only one builds it and the rest wait for its result.

## 8. Models and startup

| | Decision model (malkuth-2b, `:8081`) | Narration model (`:8082`) |
|---|---|---|
| Does | Layer 1, layer 2, narration check | Narration, rewrites, recaps, layer-1 action reading, picking layer-2 intent slots |
| Time limit | 10 s per call | 60 s for narration, 10 s for reading and picking |
| On timeout | An unreadable answer | That attempt fails; if all three attempts fail, stream `error` |

At startup the server validates every story against story.md V1–V6 and sends a short request to both models. If anything fails, it does not start. It never starts or stops the models.

## 9. Properties and checks

| Property | Statement and reason | Enforced in | Check |
|---|---|---|---|
| Model substitution | Replacing either model with any function (rules, randomness, a person, an adversarial model) keeps the properties of the world and rules. Model output enters only as elements of `Ω` (which become an action, clarify, refusal or `ν₀`, with actions inside `K`) and as checked text (kept only in `P`) | Sections 3, 5 | A fake decision model that answers nonsense; a fake checker that always rejects |
| Context purity | Every model input is built only from `ρ(Vₜ, X)`, `λ`, exogenous inputs and story constants. Narration and rewrite feedback use `Vₜ₊ₖ` and `δ` | `interpret`, `narrate` | Two states differing only in hidden atoms → the same prompt (compare the text a fake model received) |
| Closed questions | `Ω` is computed before the call, and answers outside it have probability 0 | `decide` | Answers outside the options |
| Interpretation totality | Every sentence ends as a plan, clarify, or refusal, because the tree's depth `1 + k` is finite, `δ_θ` always yields a value, and the layer-1 step-1 default `try(player)` is always a candidate | Section 3 | Random-sentence fuzzing |
| Conservatism under uncertainty | 3.4, Conservatism | `δ_θ`, 4.2 | Low confidence on every judgment slot → `ν₀`; low confidence on every intent slot with no narration-model answer → clarify |
| Bounded misreading | An executed step yields the `R` outcome of one candidate, and its gain stays within rule.md's bounded advantage | Admission check | An id outside the candidates → refusal |
| Cost bound | A turn finishes within `1 + k` decision-model interpretation calls, one narration-model action reading plus up to 2 picks per step, 3 narration attempts and 3 check calls, and each call has a time limit. A turn that ends a chapter adds 3 recap attempts + 3 checks | 3.5, section 8 | A fake model that never answers |
| Card honesty | The risk, target number and modifiers shown on a roll card equal those at execution, and a high-risk step runs only after that exact action is accepted | 4.2, 4.3, section 7 | A card's `preview.mods`·`risk` equal its step's `Step` (the step record's `mods` is a projection of it); a high-risk second step in a chain; accepting a stale card; a `pick` outside the card |
| Display reproducibility | The screen at any point is a function of `(story, L, P)`. Narration is cached per `(game, turn)`, and a repeated request gets the same result through its receipt. Narration cut off before caching is written again, so its sentences may differ, but it goes through the same `δ` and checks | Sections 6, 7 | Concurrent requests, the same request id, the same view and narration after a server restart |
| One table | `ρ`, `λ` and `κ` use the one `𝔗`, and each fact line corresponds to one atom of `F` | Section 1 | Round trip `κ(ρ_fact(O, X)) = {φ ∈ F ∣ some entity slot of φ is in X, and all are in E}` |
| Calibration and error rate | If the decision model is calibrated, an answer accepted at `p(ω₁) ≥ θ` is wrong with probability at most `1 − θ`, and with `d` answers accepted in one action, at most `d(1 − θ)`. Raising `θ` lowers errors and increases clarify cards and `try(player)` | 3.4 | The measurements below |

**What to measure** (measurement targets the properties do not depend on):

- Narration acceptance: the share accepted on the first attempt, and the share with deleted sentences.
- Interpretation accuracy: per-layer and per-slot accuracy on the sentences in `scenarios/<folder>/evals.yaml`, and the share that fell to `ν₀` or `try(player)`. Before changing interpretation rules, measure on a freshly collected eval set first, and report the numbers from before the change alongside.
- Calibration: whether answers the model gave probability `p` are right at a rate close to `p`. Measured on questions that reached the model in real play, after rule pre-filling.
- Change coverage: the share of narrations in which every atom of `δ` shows.
- Cost: decision-model calls and latency per turn.
