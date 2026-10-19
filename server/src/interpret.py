"""A sentence to a plan, a clarify card or a refusal (engine.md 3).

Every question is closed and its options are computed from the observation before the model is called.
Layer 0 is rules, layer 1 asks the schemas of up to three steps in one Kev call, and layer 2 asks one
step's slots right before that step runs. `δ_θ` accepts an answer only when its probability is ≥ θ.

A partial plan step is {"schema", "text", "fixed": {slot: value}}; `fill` turns it into
{"action", "rely", "slots"}, {"card"} or {"refused"}, or returns it without "action" to stop the plan.
"""

from __future__ import annotations

import asyncio
import re
import unicodedata

from .cards import rely_options
from .lang.context import context, render
from .locale import ko
from .models.decision import ModelUnavailable
from .onto.atoms import APPROACHES, PLAYER
from .onto.view import observe
from .rules.acts import JUDGE, make, parse
from .rules.candidates import candidates, expand, solution_label, space
from .view import action_label, rely_label

THETA = 0.5
TIMEOUT = 10.0
SAY = ("go", "look", "take", "give", "talk", "try", "declare", "cut", "choose")
END = "end"
FALLBACK_APPROACH = "wits"         # try(player) when layer 1 is unsure: no roll, no change, narration only


# -- layer 0: rules --

def squeeze(text: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFC", text)
                   if not c.isspace() and unicodedata.category(c)[0] not in "PS")


TAIL = r"(?:을|를|이|가|에|의|은|는|으로|로|과|와|도|만|에게|한테|께|에서)?(?![가-힣])"
SHORT = r"(?:을|를|이|가|에|의|은|는|으로|로|과|와|에게|한테)"


def mentions(word: str, text: str) -> int:
    """Where the word stands on its own in the sentence (a one-syllable word only with a particle), or -1."""
    m = re.search(re.escape(word) + (TAIL if len(word) >= 2 else SHORT), text)
    return m.start() if m else -1


def named(u, o, text: str) -> list[str]:
    """Entities of E whose name or alias the sentence mentions, in sentence order."""
    found = []
    for x in o.seen:
        if x == PLAYER or u.kind(x) is None:
            continue
        at = [i for w in (u.name(x), *u.aliases(x)) if (i := mentions(w, text)) >= 0]
        if at:
            found.append((min(at), x))
    return [x for _, x in sorted(found)]


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
    """The rely value whose name the sentence mentions; a roll card's default (engine.md 4.2)."""
    if "rely" not in JUDGE.get(a.schema, ()):
        return None
    hits = [v for v in rely_options(u, o, a.with_(rely=None)) if mentions(rely_label(u, p, o.facts, v), text) >= 0]
    return hits[0] if len(hits) == 1 else None


def rules(u, o, p: dict, text: str) -> dict | None:
    """Layer 0 decisions that need no model: a refusal or a whole plan."""
    flat = squeeze(text)
    if any(squeeze(w) in flat for w in u.impossible):
        return {"refused": ko.NOT_IN_WORLD}
    if any(w in text for w in ko.META):
        return {"refused": ko.META_REPLY}
    for a in candidates(u, o):
        if squeeze(action_label(u, o, p, a)) == flat or (
                (lab := solution_label(u, o, a)) and squeeze(lab) == flat):
            return {"plan": [{"action": str(a)}]}
    return None


# -- model calls --

def choice(question: str, criteria: dict[str, str]) -> dict:
    return {"type": "choice", "instructions": question, "criteria": criteria}


def ranked(answer, options) -> list[tuple[str, float]]:
    """Options by probability; answers outside the options count 0 (engine.md 3)."""
    probs = getattr(answer, "probabilities", None) or {}
    return sorted(((w, float(probs.get(w, 0.0))) for w in options), key=lambda x: -x[1])


class Interpreter:
    def __init__(self, decision, llm=None, theta: float = THETA, timeout: float = TIMEOUT):
        self.decision, self.llm, self.theta, self.timeout = decision, llm, theta, timeout
        self.calls: list[dict] = []          # the last sentence's questions and answers, for evals

    async def ask(self, state: str, questions: dict[str, dict]) -> dict:
        try:
            out = await asyncio.wait_for(self.decision.decide(state, questions), self.timeout)
        except (ModelUnavailable, TimeoutError):
            out = {}
        self.calls.append({"questions": questions, "answers": {
            k: dict(getattr(v, "probabilities", {})) for k, v in out.items()}})
        return out

    async def second(self, text: str, options: dict[str, str]) -> str | None:
        """The narration model's pick over the same numbered options at temperature 0."""
        if self.llm is None:
            return None
        keys = list(options)
        listed = "\n".join(f"{i + 1}. {options[k]}" for i, k in enumerate(keys))
        messages = [{"role": "system", "content": ko.CHOOSER},
                    {"role": "user", "content": ko.fill(ko.CHOOSER_PROMPT, text=text, options=listed)}]
        try:
            raw = await asyncio.wait_for(self.llm.pick(messages), self.timeout)
        except (ModelUnavailable, TimeoutError, OSError):
            return None
        m = re.search(r"\d+", raw)
        i = int(m.group()) - 1 if m else -1
        return keys[i] if 0 <= i < len(keys) else None

    # -- layer 1 --

    async def plan(self, u, g, text: str) -> dict:
        self.calls = []
        o = observe(u, g.state, g.log)
        p = g.presentation
        out = rules(u, o, p, text)
        if out is not None:
            return out
        have = {s.schema for s in space(u, o)}
        first = {σ: ko.SCHEMA_DESC[σ] for σ in SAY if σ in have}
        later = {**{σ: ko.SCHEMA_DESC[σ] for σ in SAY}, END: ko.END}
        if not first:
            return {"plan": [self.idle()]}
        qs = {f"s{i}": choice(ko.STEP_QUESTION[i], first if i == 1 else later) for i in (1, 2, 3)}
        # Layer 1 options are scene-free, so Kev reads the sentence alone: on the skeleton evals the context
        # ρ({player, here}) lowered accuracy from 80% to 71% (qa_test/agency/interp-2-ctx).
        answers = await self.ask(self.sentence(text), qs)
        top, pr = ranked(answers.get("s1"), first)[0]
        if pr < self.theta and await self.second(text, first) != top:
            return {"plan": [self.idle(approach_cue(text))]}
        plan = [self.partial(top, text)]
        for i in (2, 3):
            σ, pr = ranked(answers.get(f"s{i}"), later)[0]
            if pr < self.theta or σ == END:
                break
            plan.append(self.partial(σ, text))
        return {"plan": plan}

    @staticmethod
    def sentence(text: str) -> str:
        return f"플레이어 문장: {text}"

    @staticmethod
    def idle(ap: str | None = None) -> dict:
        return {"action": str(make("try", (PLAYER, ap or FALLBACK_APPROACH))), "idle": True}

    @staticmethod
    def partial(schema: str, text: str) -> dict:
        return {"schema": schema, "text": text, "fixed": {}}

    # -- layer 2 --

    async def fill(self, u, g, st: dict) -> dict:
        o = observe(u, g.state, g.log)
        p = g.presentation
        text, fixed = st["text"], dict(st.get("fixed", {}))
        slots = [s for s in space(u, o) if s.schema == st["schema"]]
        if not slots:
            return st
        if st["schema"] == "try":
            return await self.fill_try(u, o, p, st, slots, text, fixed)
        intents = self.narrow(u, o, text, [s.intent for s in slots], fixed)
        if not intents:
            return st
        slot_of = {s.intent: s for s in slots}
        labels = {":".join(i): action_label(u, o, p, expand(slot_of[i])[0]) for i in intents}
        qs, judge = {}, {}
        if len(intents) > 1 and "intent" not in fixed:
            qs["intent"] = choice(ko.SLOT_QUESTION["intent"], labels)
        if st["schema"] == "talk":
            judge = {"tone": {t: ko.TONE_DESC[t] for t in ko.TONES}}
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
            opts = {"none": ko.NO_CLAIM, **{c: u.props[c].text for c in claims}}
            w, pr = ranked((await self.ask(state, {"claim": choice(ko.SLOT_QUESTION["claim"], opts)})).get("claim"),
                           opts)[0]
            fixed["claim"] = w if pr >= self.theta else None
        if "intent" not in fixed:
            if len(intents) == 1:
                fixed["intent"] = ":".join(intents[0])
            else:
                top = ranked(answers.get("intent"), labels)
                if top[0][1] >= self.theta:
                    fixed["intent"] = top[0][0]
                else:
                    return self.clarify(u, o, p, st, fixed, "intent", [w for w, _ in top[:3]], labels)
        intent = tuple(fixed["intent"].split(":"))
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
        answers = await self.ask(self.state(u, o, p, text, targets), qs) if qs else {}
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
                if top[0][1] < self.theta:
                    return self.clarify(u, o, p, st, fixed, "target", [w for w, _ in top[:3]], labels)
                fixed["target"] = top[0][0]
        if "approach" not in fixed:
            top = ranked(answers.get("approach"), approaches)
            if top[0][1] < self.theta:
                names = {ap: ko.APPROACHES[ap] for ap in APPROACHES}
                return self.clarify(u, o, p, st, fixed, "approach", [w for w, _ in top[:3]], names)
            fixed["approach"] = top[0][0]
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
        """Layer 0 on one step's intent options: the addressee and the named entities pick among them."""
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

    def done(self, u, o, p, a, text, echo) -> dict:
        return {"action": str(a), "rely": rely_hint(u, o, p, a, text), "slots": echo}

    def clarify(self, u, o, p, st, fixed, slot, top, labels) -> dict:
        """A clarify card over {ω₁, ω₂, ω₃} (engine.md 4.1); a pick fills the slot and the plan goes on."""
        resume = {w: {**st, "fixed": {**fixed, slot: w}} for w in top}
        return {"clarify": {"slot": slot, "question": ko.CLARIFY_SLOT[slot],
                            "options": [{"id": w, "label": labels[w]} for w in top], "resume": resume}}


__all__ = ["Interpreter", "mentions", "named", "parse", "rules", "squeeze"]
