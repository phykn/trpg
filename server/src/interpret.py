from __future__ import annotations

import asyncio
import re
import unicodedata

from .cards import rely_options
from .lang.context import about, context, render
from .locale import ko
from .models.decision import ModelUnavailable, choice, noul, probs_of
from .onto.atoms import APPROACHES, PLAYER
from .onto.view import observe
from .rules.acts import JUDGE, make, parse
from .rules.candidates import (
    Slot,
    blockers,
    candidates,
    expand,
    solution_action,
    solution_holds,
    solution_label,
    space,
)
from .view import action_label, rely_label

THETA = 0.5
# Layer 1's first step: from 0.5 to 0.7 Kev's sure answer was wrong where the narration model's reading was right 24
# times to 4, above it 4 to 3 (qa_test/runs/misread-1).
STEP_THETA = 0.7
# A reliance stays on the roll card when it takes this share of the one relevance choice (engine.md 4.2).
RELY_SHARE = 0.1
TIMEOUT = 10.0
SAY = ("go", "look", "take", "give", "talk", "try", "declare", "cut", "choose")
FALLBACK_APPROACH = "wits"         # try(player) when layer 1 is unsure: no roll, no change, narration only
SAY_TONES = ("polite", "friendly", "plead")   # threats and lies change regard, so only an act makes them (engine.md 3.3)
REQUESTS = ("favor", "come", "stay")


def squeeze(text: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFC", text)
                   if not c.isspace() and unicodedata.category(c)[0] not in "PS")


TAIL = r"(?:을|를|이|가|에|의|은|는|으로|로|과|와|도|만|에게|한테|께|에서|아|야)?(?![가-힣])"
SHORT = r"(?:을|를|이|가|에|의|은|는|으로|로|과|와|에게|한테)"


def mentions(word: str, text: str) -> int:
    """A one-syllable word counts only with a particle; -1 when it is absent. Called by name, a word ending in the
    suffix 이 drops it ("누렁이" → "누렁아"); players call people and animals that way."""
    m = re.search(re.escape(word) + (TAIL if len(word) >= 2 else SHORT), text)
    if m is None and len(word) >= 3 and word.endswith("이"):
        m = re.search(re.escape(word[:-1]) + r"아(?![가-힣])", text)
    return m.start() if m else -1


def names_way(u, q: str, ways: list[str], text: str) -> bool:
    """The sentence names way q and no other way, so its move card only confirms it (engine.md 4.4)."""
    said = [w for w in ways
            if any(mentions(n, text) >= 0 or mentions(n.replace(" ", ""), text) >= 0
                   for n in (u.name(w), *u.aliases(w)))]
    return said == [q]


def named(u, o, text: str) -> list[str]:
    found = []
    for x in o.seen:
        if x == PLAYER or u.kind(x) is None:
            continue
        at = [i for w in (u.name(x), *u.aliases(x)) if (i := mentions(w, text)) >= 0]
        if at:
            found.append((min(at), x))
    return [x for _, x in sorted(found)]


def says(u, x: str, text: str) -> bool:
    return any(mentions(w, text) >= 0 for w in (u.name(x), *u.aliases(x)))


def guarded(u, o, text: str, schema: str) -> tuple[str, str] | None:
    """(target, the visible obstacle blocking it) for what the sentence aims at: something it names, or, spoken to no
    one by name ("왜 못하지?"), the people here when all of them are guarded."""
    f, here = o.facts, o.facts.where(PLAYER)
    for x in named(u, o, text):
        by = blockers(u, f, x) if x != here else []
        if by:
            return x, by[0]
    if schema in ("talk", "give"):
        here_people = [x for x in sorted(o.seen, key=u.rank) if x in u.agents and f.where(x) == here]
        held = [(x, by) for x in here_people if (by := blockers(u, f, x))]
        if here_people and len(held) == len(here_people) and not set(named(u, o, text)) & set(u.agents):
            return held[0][0], held[0][1][0]
    return None


def blocked_why(u, x: str, ob: str) -> str:
    return ko.fill(ko.WHY["blocked_way" if u.kind(x) == "place" else "blocked"], ob=u.name(ob), x=u.name(x))


def unreachable(u, o, text: str, schema: str) -> str | None:
    """Why the sentence's own target is out of reach, when the engine knows it. Refused with no reason, players could
    not tell a guard dog from a broken game, and a sentence aimed at a guarded person landed on another target
    ("도해의 아구창을 날린다" → a try on the letter)."""
    f = o.facts
    if (g := guarded(u, o, text, schema)) and g[0] in named(u, o, text):
        return blocked_why(u, *g)
    if schema == "give":
        # a thing handed over is out of sight in its new holder's hands, so memory says it is known
        known = {a[1] for s in o.memory for a in (*s.delta.add, *s.delta.remove) if a[0] == "at" and a[1] in u.things}
        for x in sorted(known | {x for x in o.seen if x in u.things}):
            if f.where(x) != PLAYER and says(u, x, text):
                return ko.fill(ko.WHY["not_held"], x=u.name(x))
    if schema in ("talk", "give"):
        met = {w for s in o.memory for w in s.witnesses}
        for x in sorted(met - set(o.seen)):
            if x in u.agents and says(u, x, text):
                return ko.fill(ko.WHY["away"], x=u.name(x))
    return blocked_why(u, *g) if g else None


def title_words(title: str) -> list[str]:
    """The words a sentence names a topic by: its title's words without a final particle, two syllables or more, and
    its last word, the head noun, whatever its length ("폐허", "길" for "폐허로 가는 길")."""
    words = [re.sub(r"(?:으로|로|의|에|과|와|을|를|이|가)$", "", w) for w in title.split()]
    return [w for w in words[:-1] if len(w) >= 2] + [words[-1]]


def topic_named(u, h: str, topic: str, text: str) -> bool:
    """A story topic is offered only when the sentence names it: offered every topic, the models put any question near
    the place on its one topic (qa_test/runs/intent-1-base). By the head noun alone, 5 of 18 bench questions lost
    theirs ("폐허 가는 길"); by any title word, 1, and no other topic came in (qa_test/runs/intent-1-probe)."""
    t = next((t for t in u.agents[h].topics if t.id == topic), None)
    return t is None or any(mentions(w, text) >= 0 for w in title_words(t.title))


def addressee(u, o, text: str) -> str | None:
    for x in o.seen:
        if x in u.agents:
            for w in (u.name(x), *u.aliases(x)):
                if any(w + t in text for t in ko.TO_PERSON):
                    return x
    return None


def approach_cue(text: str) -> str | None:
    hits = [ap for ap, words in ko.APPROACH_WORDS.items() if any(w in text for w in words)]
    return hits[0] if len(hits) == 1 else None


def rely_hint(u, o, p: dict, a, text: str) -> str | None:
    """The hint becomes the roll card's default (engine.md 4.2)."""
    if "rely" not in JUDGE.get(a.schema, ()):
        return None
    hits = [v for v in rely_options(u, o, a.with_(rely=None)) if mentions(rely_name(u, p, o.facts, v), text) >= 0]
    return hits[0] if len(hits) == 1 else None


def rely_name(u, p: dict, facts, v: str) -> str:
    kind, _, rest = v.partition(":")
    return u.name(rest) if kind in ("bond", "with") else rely_label(u, p, facts, v)


def rely_desc(u, p: dict, facts, v: str) -> str:
    kind, _, rest = v.partition(":")
    name = rely_name(u, p, facts, v)
    text = (u.traits[rest][1] if kind == "trait" else u.things[rest].look if kind == "thing"
            else u.props[rest].text if kind == "prop" else "")
    return ko.fill(ko.RELY_DESC[kind], name=name, text=text)


def rules(u, o, p: dict, text: str) -> dict | None:
    """Layer 0 decisions that need no model: a refusal or a whole plan."""
    flat = squeeze(text)
    if any(squeeze(w) in flat for w in u.impossible):
        return {"refused": ko.NOT_IN_WORLD}
    if any(w in text for w in ko.META):
        return {"refused": ko.META_REPLY}
    # Growth is picked on its own card; typed, it became an empty attempt (play-3-odd 10).
    if ko.GROWTH_WORD in text and (o.facts.stat(PLAYER, "growth") or 0) >= 1:
        return {"refused": ko.GROWTH_REPLY}
    for a in candidates(u, o):
        if squeeze(action_label(u, o, p, a)) == flat or (
                (lab := solution_label(u, o, a)) and squeeze(lab) == flat):
            return {"plan": [{"action": str(a)}]}
    return None


def yes_share(answer) -> float:
    return float(probs_of(answer).get("true", 0.0))


def listed(options: dict[str, str]) -> str:
    return "\n".join(f"{i + 1}. {d}" for i, d in enumerate(options.values()))


def ranked(answer, options) -> list[tuple[str, float]]:
    """Answers outside the options count 0 (engine.md 3)."""
    probs = probs_of(answer)
    return sorted(((w, float(probs.get(w, 0.0))) for w in options), key=lambda x: -x[1])


class Interpreter:
    def __init__(self, decision, llm=None, theta: float = THETA, timeout: float = TIMEOUT,
                 step_theta: float = STEP_THETA):
        self.decision, self.llm, self.theta, self.timeout = decision, llm, theta, timeout
        self.step_theta = step_theta
        self.calls: list[dict] = []          # the last sentence's questions and answers, for evals

    async def ask(self, state: str, questions: dict[str, dict]) -> dict:
        try:
            out = await asyncio.wait_for(self.decision.decide(state, questions), self.timeout)
        except (ModelUnavailable, TimeoutError):
            out = {}
        self.calls.append({"questions": questions, "answers": {
            k: probs_of(v) for k, v in out.items()}})
        return out

    async def numbers(self, system: str, prompt: str) -> list[int] | None:
        """The narration model's answer as option numbers, from 0; None when it gives none in time."""
        if self.llm is None:
            return None
        try:
            raw = await asyncio.wait_for(self.llm.pick([{"role": "system", "content": system},
                                                        {"role": "user", "content": prompt}]), self.timeout)
        except (ModelUnavailable, TimeoutError, OSError):
            return None
        return [int(m) - 1 for m in re.findall(r"\d+", raw)]

    async def read(self, text: str, options: dict[str, str]) -> list[str] | None:
        """The narration model's reading: the sentence's actions in order, at most three."""
        keys = list(options)
        got = await self.numbers(ko.READER, ko.fill(ko.READER_PROMPT, text=text, options=listed(options)))
        if got is None:
            return None
        steps = []
        for i in got:
            # the same schema twice in a row is one action told in two clauses ("kneels and begs")
            if 0 <= i < len(keys) and (not steps or steps[-1] != keys[i]):
                steps.append(keys[i])
        return steps[:3]

    async def pick(self, state: str, question: str, options: dict[str, str]) -> str | None:
        """The narration model's answer to an intent slot Kev was unsure of, with Kev's context and options."""
        keys = list(options)
        got = await self.numbers(ko.PICKER, ko.fill(ko.PICKER_PROMPT, state=state, question=question,
                                                    options=listed(options)))
        return keys[got[0]] if got and 0 <= got[0] < len(keys) else None

    async def plan(self, u, g, text: str) -> dict:
        self.calls = []
        o = observe(u, g.state, g.log)
        p = g.presentation
        out = rules(u, o, p, text)
        if out is not None:
            return out
        have = {s.schema for s in space(u, o)}
        if not have & set(SAY):
            return {"plan": [self.idle()]}
        # Every schema, those possible here first: offered only those, Kev put the weight of an impossible one (a
        # talk to someone kept away) on another and was sure of it. An impossible first step stops the sentence
        # (qa_test/runs/misread-1).
        say = {σ: ko.SCHEMA_ASK[σ] for σ in sorted(SAY, key=lambda σ: σ not in have)}
        forks = [action_label(u, o, p, a) for a in candidates(u, o) if a.schema == "choose"]
        if forks:
            say["choose"] = ko.fill(ko.CHOOSE_HERE, choices=", ".join(forks))
        qs = {"k": choice(ko.KIND_QUESTION, ko.KIND), "s1": choice(ko.STEP_QUESTION, say),
              "n": choice(ko.COUNT_QUESTION, ko.COUNT)}
        # Layer 1 options are scene-free, so Kev reads the sentence alone: on the skeleton evals the context
        # ρ({player, here}) lowered accuracy from 80% to 71% (qa_test/runs/interp-2-ctx).
        answers = await self.ask(self.sentence(text), qs)
        # Only an action may roll or spend time; asked only for parts, every line became the nearest action
        # (engine.md 3.2). A line that names a thing, an obstacle or a place is about it ("문 발로 차", "누렁아~").
        # Below θ₁ the narration model reads the kind: on 35 typed lines Kev was right on 30 and the narration model
        # on 33, and every Kev miss was under 0.7 (qa_test/runs/intent-1-probe). No reading leaves it to the parts.
        kind, kp = ranked(answers.get("k"), ko.KIND)[0]
        if kp < self.step_theta:
            kind = await self.pick(self.sentence(text), ko.KIND_QUESTION, ko.KIND)
        if kind in ("say", "muse") and all(x in u.agents for x in named(u, o, text)):
            here = o.facts.where(PLAYER)
            if kind == "muse" or not any(x in u.agents and o.facts.where(x) == here for x in o.seen):
                return {"plan": [self.idle()]}
            return {"plan": [{**self.partial("talk", text), "say": True}]}
        top, pr = ranked(answers.get("s1"), say)[0]
        # a silent model gives every option 0, which ranks "1" first; a refusal needs the narration model's reading too
        sure, one = pr >= self.step_theta and top in have, ranked(answers.get("n"), ko.COUNT)[0][0] == "1"
        if sure and one:
            return {"plan": [self.partial(top, text)]}
        # Kev reads one sure action well and little else: unsure, it was wrong where the narration model was right
        # 22 times to 1, and it got 11 of 48 several-action sentences right to the narration model's 35, with
        # one-action sentences even (qa_test/runs/decision-1). Later steps may happen elsewhere, so every schema.
        steps = await self.read(text, say)
        if sure and steps and steps[0] not in have:
            steps = None
        if not one and steps and len(steps) > 1:
            return {"plan": [self.partial(σ, text) for σ in steps]}
        if not sure:
            if not steps:
                return {"plan": [self.idle(approach_cue(text))]}
            top = steps[0]
        return {"plan": [self.partial(top, text)]}

    @staticmethod
    def sentence(text: str) -> str:
        return ko.fill(ko.SENTENCE, text=text)

    @staticmethod
    def idle(ap: str | None = None) -> dict:
        return {"action": str(make("try", (PLAYER, ap or FALLBACK_APPROACH))), "idle": True}

    @staticmethod
    def partial(schema: str, text: str) -> dict:
        return {"schema": schema, "text": text, "fixed": {}}

    async def fill(self, u, g, st: dict) -> dict:
        """Returning the step without "action" stops the plan; "already" skips it."""
        o = observe(u, g.state, g.log)
        p = g.presentation
        text, fixed = st["text"], dict(st.get("fixed", {}))
        slots = [s for s in space(u, o) if s.schema == st["schema"]]
        if st["schema"] == "talk":
            # small talk (a say line) is chat or a named topic; requests, threats and lies come from acts
            slots = [s for s in slots if topic_named(u, *s.intent, text)
                     and not (st.get("say") and s.intent[1] in REQUESTS)]
        # a target a card settled (a detour's pick) is not read from the sentence again
        why = None if {"target", "intent"} & set(fixed) else unreachable(u, o, text, st["schema"])
        names = named(u, o, text)
        if not slots or (why and not any(x in s.intent for s in slots for x in names if x != PLAYER)):
            g = guarded(u, o, text, st["schema"])
            if g and why == blocked_why(u, *g) and (ask := self.detour(u, o, text, *g)):
                return {"clarify": ask}
            return {"refused": why or ko.REFUSED["candidate"]}
        if st["schema"] == "try":
            return await self.fill_try(u, o, p, st, slots, text, fixed)
        here = (o.facts.where(PLAYER),)
        already = {"already": ko.fill(ko.ALREADY_HERE, place=u.name(here[0]))}
        if st["schema"] == "go" and fixed.get("intent") == here[0]:
            return already
        intents = self.narrow(u, o, text, [s.intent for s in slots], fixed)
        if not intents:
            return st
        slot_of = {s.intent: s for s in slots}
        # The place the player is in, unless the sentence names a way out: offered only the ways out, Kev took one
        # for a sentence naming this place (qa_test/runs/misread-1). Choosing it moves nowhere. Naming this place
        # alone does not settle it: "to the dock" stays where "leaving the dock" goes.
        if st["schema"] == "go" and "intent" not in fixed and not any(i[0] in names for i in intents):
            intents = [*intents, here]
            slot_of[here] = Slot("go", here)
        labels = {":".join(i): action_label(u, o, p, expand(slot_of[i])[0]) for i in intents}
        qs, judge = {}, {}
        if len(intents) > 1 and "intent" not in fixed:
            qs["intent"] = choice(ko.SLOT_QUESTION["intent"], labels)
        if st["schema"] == "talk":
            judge = {"tone": {t: ko.TONE_DESC[t] for t in (SAY_TONES if st.get("say") else ko.TONES)}}
        for k, opts in judge.items():
            if k not in fixed:
                qs[k] = choice(ko.SLOT_QUESTION[k], opts)
        state = self.state(u, o, p, text, intents)
        answers = await self.ask(state, qs) if qs else {}
        for k in judge:
            if k not in fixed:
                w, pr = ranked(answers.get(k), judge[k])[0]
                fixed[k] = w if pr >= self.theta else None
        claims = sorted({c for i in intents for c in slot_of[i].values("claim") if c})
        if fixed.get("tone") == "deceive" and claims and "claim" not in fixed:
            # One yes/no per claim: offered as one choice with "no claim", the model took "no claim" for every lie.
            # What the sentence says needs only the sentence; the scene lowered every right answer.
            got = await self.ask(self.sentence(text),
                                 {c: noul(ko.fill(ko.CLAIM_QUESTION, text=u.props[c].text), ko.YES, ko.NO) for c in claims})
            yes = max(claims, key=lambda c: yes_share(got.get(c)))
            fixed["claim"] = yes if yes_share(got.get(yes)) >= self.theta else None
        if "intent" not in fixed:
            if len(intents) == 1:
                fixed["intent"] = ":".join(intents[0])
            else:
                top = ranked(answers.get("intent"), labels)
                # Where Kev is unsure the narration model picks before the player is asked: on the bench it was
                # right on 44 of 45 such intents, targets and approaches (qa_test/runs/decision-1). Staying needs
                # the narration model too, as a refusal does: Kev took the place of a door to go through it.
                sure = top[0][1] >= self.theta and (st["schema"], top[0][0]) != ("go", here[0])
                w = top[0][0] if sure else await self.pick(state, qs["intent"]["instructions"], labels)
                if w is None:
                    return self.clarify(st, fixed, "intent", [x for x, _ in top[:3]], labels)
                fixed["intent"] = w
        intent = tuple(fixed["intent"].split(":"))
        if st["schema"] == "go" and intent == here:
            # Walking about the place ("오두막 뒤쪽으로 돌아가 본다") was told only where the player already was
            # (play-3-explorer 9); the ways out answer what was asked.
            if here[0] not in names and slots:
                return {"already": ko.fill(ko.NO_FARTHER, place=u.name(here[0]),
                                           ways=", ".join(u.name(s.intent[0]) for s in slots))}
            return already
        slot = slot_of[intent]
        judge_args = {}
        if st["schema"] == "talk":
            tone = fixed.get("tone") if fixed.get("tone") in slot.values("tone") else None
            claim = fixed.get("claim") if fixed.get("claim") in slot.values("claim") else None
            judge_args = {"tone": "deceive" if claim else tone, "claim": claim}
        a = make(st["schema"], intent, judge_args)
        echo = [{"slot": "tone", "label": ko.TONES[a.get("tone")]}] \
            if st["schema"] == "talk" and a.get("tone") != "polite" else []
        return self.done(u, o, p, a, text, echo)

    async def fill_try(self, u, o, p, st, slots, text, fixed) -> dict:
        targets = self.narrow(u, o, text, sorted({(s.intent[0],) for s in slots}, key=lambda x: u.rank(x[0])),
                              fixed, key="target")
        if not targets:
            return st
        labels = {t[0]: (ko.NO_TARGET if t[0] == PLAYER else u.name(t[0])) for t in targets}
        approaches = {ap: ko.APPROACH_DESC[ap] for ap in APPROACHES}
        strains = dict(ko.STRAIN_DESC)
        if "approach" not in fixed and (cue := approach_cue(text)):
            fixed["approach"] = cue
        qs = {}
        if len(targets) > 1 and "target" not in fixed:
            qs["target"] = choice(ko.SLOT_QUESTION["target"], labels)
        if "approach" not in fixed:
            qs["approach"] = choice(ko.SLOT_QUESTION["approach"], approaches)
        if "strain" not in fixed:
            qs["strain"] = choice(ko.SLOT_QUESTION["strain"], strains)
        state = self.state(u, o, p, text, targets)
        # The narration model picks the target and approach even where Kev is sure: on the bench it was right on 48
        # of 48 targets and 40 of 42 approaches to Kev's 33 and 25 (qa_test/runs/decision-1). Kev's answers stay
        # for when it gives none, and both models are asked at once.
        picking = [k for k in ("target", "approach") if k in qs]
        answers, *got = await asyncio.gather(
            self.ask(state, qs) if qs else asyncio.sleep(0, {}),
            *(self.pick(state, qs[k]["instructions"], labels if k == "target" else approaches) for k in picking))
        picks = dict(zip(picking, got))
        if "strain" not in fixed:
            w, pr = ranked(answers.get("strain"), strains)[0]
            fixed["strain"] = w if pr >= self.theta else "natural"
        if fixed["strain"] == "impossible":
            return {"refused": ko.NOT_POSSIBLE}
        if "target" not in fixed:
            if len(targets) == 1:
                fixed["target"] = targets[0][0]
            else:
                top = ranked(answers.get("target"), labels)
                w = picks["target"] or (top[0][0] if top[0][1] >= self.theta else None)
                if w is None:
                    return self.clarify(st, fixed, "target", [x for x, _ in top[:3]], labels)
                fixed["target"] = w
        if "approach" not in fixed:
            top = ranked(answers.get("approach"), approaches)
            # With no answer at all, the player's strongest stat instead of a question.
            fixed["approach"] = picks["approach"] or (top[0][0] if top[0][1] >= self.theta else max(
                APPROACHES, key=lambda ap: o.facts.stat(PLAYER, ap) or 0))
        x, ap = fixed["target"], fixed["approach"]
        slot = next(s for s in slots if s.intent == (x, ap))
        strain = fixed["strain"] if fixed["strain"] in slot.values("strain") else None
        a = make("try", (x, ap), {"strain": strain})
        echo = [{"slot": "approach", "label": ko.APPROACHES[ap]}]
        if x != PLAYER:
            echo.insert(0, {"slot": "target", "label": u.name(x)})
        if a.get("strain") == "forced":
            echo.append({"slot": "strain", "label": ko.STRAINS["forced"]})
        return self.done(u, o, p, a, text, echo)

    def narrow(self, u, o, text, intents, fixed, key="intent") -> list[tuple]:
        if key in fixed:
            want = tuple(fixed[key].split(":"))
            return [i for i in intents if i == want]
        to = addressee(u, o, text)
        if to is not None and any(to in i for i in intents):
            intents = [i for i in intents if to in i]
        names = named(u, o, text)
        titles = {}
        for i in intents:
            if len(i) == 2 and i[0] in u.agents:
                t = next((t for t in u.agents[i[0]].topics if t.id == i[1]), None)
                if t is not None and squeeze(t.title) in squeeze(text):
                    titles[i] = 1
        score = {i: sum(x in names for x in i) + titles.get(i, 0) for i in intents}
        best = max(score.values(), default=0)
        return [i for i in intents if score[i] == best] if best else intents

    def state(self, u, o, p, text, intents) -> str:
        focus = {PLAYER, o.facts.where(PLAYER), *(x for i in intents for x in i)}
        return render(context(u, o, focus, p)) + "\n\n" + self.sentence(text)

    async def relevant(self, u, o, p, a, values: list[str], hinted: str | None, text: str | None) -> list[str]:
        """The roll card's reliances (engine.md 4.2): what the story ties to the target, every edge in reach, who is at
        the player's side, what was offered for this attempt before, and what the model sees helping it now."""
        x = a.intent[0]
        linked = {s.rely for s in u.obstacles[x].solutions} if x in u.obstacles else set()
        # Once offered for an attempt, a reliance stays: asked anew with each sentence, the same one came and went
        # (qa_test/runs/play-4-bold 8, 12, 15).
        offered = p.setdefault("relevance", {}).setdefault(":".join((a.schema, *a.intent)), [])
        keep = {*linked, *offered, hinted}
        # An edge exists to be spent, and its name, often the default one, is all the model could judge it by.
        ask = [v for v in values if v not in keep and not v.startswith(("tag:", "with:"))]
        if ask:
            # One choice over every reliance: asked one by one, the small model gives the same answer to all of them.
            opts = {f"r{i}": rely_desc(u, p, o.facts, v) for i, v in enumerate(ask)}
            state = "\n".join([ko.fill(ko.ATTEMPT, label=action_label(u, o, p, a)), *(ln.text for ln in about(u, o, x)),
                               *([self.sentence(text)] if text else [])])
            answer = (await self.ask(state, {"rely": choice(ko.RELY_QUESTION, {**opts, "none": ko.RELY_NONE})})).get("rely")
            probs = probs_of(answer)
            # A silent model takes no choice away from the player.
            drop = {v for i, v in enumerate(ask) if probs.get(f"r{i}", 0.0) < RELY_SHARE} if probs else set()
            values = [v for v in values if v not in drop]
        offered += [v for v in values if v not in offered]
        return values

    def done(self, u, o, p, a, text, echo) -> dict:
        return {"action": str(a), "rely": rely_hint(u, o, p, a, text), "slots": echo}

    @staticmethod
    def detour(u, o, text: str, x: str, ob: str) -> dict | None:
        """The ways around what blocks the target, as a clarify card: the hint instead of a refusal (engine.md 4.1)."""
        sols = [s for s in u.obstacles[ob].solutions if solution_holds(u, o, ob, s)]
        if not sols:
            return None
        resume = {str(solution_action(ob, s)): {"schema": "try", "text": text, "rely": s.rely,
                                                "fixed": {"target": ob, "approach": s.approach, "strain": "natural"}}
                  for s in sols}
        return {"slot": "detour", "question": ko.fill(ko.DETOUR, why=blocked_why(u, x, ob)),
                "options": [{"id": str(solution_action(ob, s)), "label": s.label} for s in sols], "resume": resume}

    @staticmethod
    def clarify(st, fixed, slot, top, labels) -> dict:
        resume = {w: {**st, "fixed": {**fixed, slot: w}} for w in top}
        return {"clarify": {"slot": slot, "question": ko.CLARIFY_SLOT[slot],
                            "options": [{"id": w, "label": labels[w]} for w in top], "resume": resume}}


__all__ = ["Interpreter", "mentions", "named", "parse", "rules", "squeeze"]
