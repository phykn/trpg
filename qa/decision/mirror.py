import sys
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import common  # noqa: F401  (puts the checkout's server on the path)
from src.interpret import (
    SAY,
    STEP_THETA,
    Interpreter,
    approach_cue,
    mentions,
    ranked,
    squeeze,
    title_words,
)
from src.lang.context import MEMORY, Line, render
from src.locale import ko
from src.models.decision import choice, noul
from src.onto.atoms import APPROACHES, PLAYER

sentence = Interpreter.sentence
YOU = ko.YOU
# Reliances the engine keeps without asking (interpret.relevant): an edge is spent, a companion is at the player's side.
UNASKED = ("tag", "with")


class Probs:
    def __init__(self, probabilities):
        self.probabilities = probabilities or {}


class Scene:
    """A bench scene (GUIDE.md) read the way the engine's space() reads a state: `order` is the story's declaration
    order (default: place, exits, people, things, obstacles, threats, forks), and things a person holds are unseen."""

    def __init__(self, sc: dict):
        self.sc = sc
        self.here = sc["place"]["name"]
        # An exit is a name, or {name, aliases} like the place itself.
        exits = [e if isinstance(e, dict) else {"name": e} for e in sc.get("exits", [])]
        self.exits = [e["name"] for e in exits]
        self.places = {self.here: sc["place"], **{e["name"]: e for e in exits}}
        self.people = {h["name"]: h for h in sc.get("people", [])}
        self.things = {t["name"]: t for t in sc.get("things", [])}
        self.obstacles = {o["name"]: o for o in sc.get("obstacles", [])}
        self.threats = list(sc.get("threats", []))
        self.forks = {f["name"]: f for f in sc.get("forks", [])}
        self.following = set(sc.get("following", []))
        order = sc.get("order") or [self.here, *self.exits, *self.people, *self.things, *self.obstacles,
                                    *self.threats, *self.forks]
        self.rank = {x: i for i, x in enumerate(order)}
        seen = {self.here, *self.exits, *self.people, *self.obstacles, *self.threats, *self.forks,
                *(t for t, d in self.things.items() if d["where"] in ("here", "player"))}
        self.seen = sorted(seen, key=lambda x: self.rank.get(x, len(order)))

    def where(self, t: str) -> str:
        return self.things[t]["where"]

    def open_(self, x: str) -> bool:
        return not any(x in o.get("blocks", ()) and o.get("fill", 0) < o.get("boxes", 1)
                       for o in self.obstacles.values())

    def aliases(self, x: str) -> list[str]:
        d = self.places.get(x) or self.people.get(x) or self.things.get(x) or self.obstacles.get(x) or {}
        return list(d.get("aliases", []))

    def slots(self, σ: str) -> list[tuple]:
        """Intents of schema σ in space() order."""
        seen = self.seen
        people = [h for h in seen if h in self.people and self.open_(h)]
        if σ == "go":
            return [(q,) for q in seen if q in self.exits and self.open_(q)]
        if σ == "look":
            return [(x,) for x in seen]
        if σ == "take":
            return [(x,) for x in seen if x in self.things and self.where(x) == "here" and self.open_(x)]
        if σ == "give":
            return [(x, h) for x in seen if x in self.things and self.where(x) == "player" for h in people]
        if σ == "talk":
            out = []
            for h in people:
                d = self.people[h]
                topics = [*d.get("topics", []), *(["favor"] if d.get("favor") else []),
                          "stay" if h in self.following else "come", "chat"]
                out += [(h, t) for t in topics]
            return out
        if σ == "try":
            return [(PLAYER,)] + [(x,) for x in seen if self.open_(x) and x not in self.threats and x not in self.forks
                                  and not (x in self.obstacles and self.filled(x))]
        if σ == "declare":
            return [(lt["name"],) for lt in self.sc.get("latents", [])]
        if σ == "cut":
            return [("pass",)] + ([("rest",)] if self.sc["place"].get("rest") else [])
        if σ == "choose":
            return [(f, c) for f, d in self.forks.items() for c in d["options"]]
        return []

    def filled(self, o: str) -> bool:
        d = self.obstacles[o]
        return d.get("fill", 0) >= d.get("boxes", 1)

    def have(self) -> set[str]:
        return {σ for σ in SAY if self.slots(σ)}

    def choices(self) -> list[str]:
        """The fork choices plan() names in the choose option."""
        return [c for _, c in self.slots("choose")]

    @staticmethod
    def ents(σ: str, i: tuple) -> tuple:
        """The entities in an intent; topic, choice and latent names are not entities."""
        return () if σ in ("declare", "cut") else i[:1] if σ in ("talk", "choose") else i

    def label(self, σ: str, i: tuple) -> str:
        if σ == "go":
            return ko.fill(ko.ACTION["go"], q=i[0])
        if σ in ("look", "take"):
            return ko.fill(ko.ACTION[σ], x=i[0])
        if σ == "give":
            return ko.fill(ko.ACTION["give"], h=i[1], x=i[0])
        if σ == "talk":
            h, t = i
            if t == "favor":
                return ko.fill(ko.ACTION["favor"], h=h, label=self.people[h]["favor"])
            if t in ("come", "stay", "chat"):
                return ko.fill(ko.ACTION[t], h=h)
            return ko.fill(ko.ACTION["talk"], h=h, title=t)
        if σ == "declare":
            return ko.fill(ko.ACTION["declare"], name=i[0])
        if σ == "cut":
            return ko.ACTION[i[0]]
        return i[1]

    def named(self, text: str) -> list[str]:
        found = []
        for x in self.seen:
            at = [n for w in (x, *self.aliases(x)) if (n := mentions(w, text)) >= 0]
            if at:
                found.append((min(at), x))
        return [x for _, x in sorted(found)]

    def addressee(self, text: str) -> str | None:
        for h in self.seen:
            if h in self.people and any(w + t in text for w in (h, *self.aliases(h)) for t in ko.TO_PERSON):
                return h
        return None

    def narrow(self, σ: str, intents: list[tuple], text: str) -> list[tuple]:
        """interpret.narrow: the person spoken to, then the intents naming most of what the sentence names."""
        to = self.addressee(text)
        if to is not None and any(to in i for i in intents):
            intents = [i for i in intents if to in i]
        names = set(self.named(text))

        def score(i):
            title = σ == "talk" and i[1] in self.people[i[0]].get("topics", []) and squeeze(i[1]) in squeeze(text)
            return sum(x in names for x in self.ents(σ, i)) + title

        best = max(map(score, intents), default=0)
        return [i for i in intents if score(i) == best] if best else intents

    def context(self, focus: set[str]) -> list[Line]:
        """lang.context.context for what a bench scene holds: facts that touch the focus or the player (here is always
        in focus), then what is known about each focused entity."""
        x = set(focus) & set(self.seen)
        here = self.here
        located = [e for e in self.seen if e in self.people or e in self.obstacles
                   or e in self.things and self.where(e) == "here"]
        held = [t for t in self.seen if t in self.things and self.where(t) == "player"]
        facts = [ko.fill(ko.FRAME["at_place"], x=e, y=here) for e in located]
        facts.append(ko.fill(ko.FRAME["at_place"], x=YOU, y=here))
        facts += [ko.fill(ko.FRAME["at_agent"], y=YOU, x=t) for t in held]
        facts += [ko.fill(ko.FRAME["fill"], o=o, n=d.get("fill", 0), boxes=d.get("boxes", 1))
                  for o, d in self.obstacles.items() if o in x]
        facts += [ko.fill(ko.FRAME["follows"], h=h) for h in self.seen if h in self.following]
        for q in self.exits:
            facts += [ko.fill(ko.FRAME["link"], p=here, q=q), ko.fill(ko.FRAME["link"], p=q, q=here)]
        facts += [ko.fill(ko.FRAME["trust"], g=h, word=ko.TRUST_VERBS[d.get("trust", 0)])
                  for h, d in self.people.items()]
        pl = self.sc.get("player", {})
        facts += [ko.fill(ko.FRAME["stat"], item=ko.APPROACHES[k], n=v) for k, v in sorted(pl.get("stats", {}).items())]
        facts += [ko.fill(ko.FRAME["trait"], name=t["name"]) for t in pl.get("traits", [])]
        facts.append(ko.fill(ko.FRAME["stat"], item=ko.SHEET["wounds"], n=pl.get("wounds", 0)))
        out = [Line("fact", t) for t in facts]
        # A memory label holds names, not ids: one naming a focused entity stands for the engine's id match.
        out += [Line("memory", ko.fill(ko.FRAME["memory"], label=m)) for m in self.sc.get("memory", [])[-MEMORY:]
                if any(e in m for e in x)]
        for e in sorted(x, key=lambda e: self.rank.get(e, len(self.rank))):
            out += self.about(e)
        return out

    def about(self, e: str) -> list[Line]:
        if e == self.here:
            text = ko.fill(ko.FRAME["senses"], x=e, text=", ".join(self.sc["place"].get("senses", [])))
            return [Line("public", text)]
        out = []
        if e in self.people:
            h = self.people[e]
            if h.get("persona"):
                out.append(ko.fill(ko.FRAME["persona"], x=e, type=h["persona"], text=ko.PERSONAS[h["persona"]]))
            out += [ko.fill(ko.FRAME[f], x=e, text=h[k]) for k, f in (("voice", "voice"), ("desire", "desire"),
                                                                       ("fear", "fear_of")) if h.get(k)]
            if h.get("topics"):
                out.append(ko.fill(ko.FRAME["topics"], x=e, text=", ".join(h["topics"])))
            if h.get("wants"):
                out.append(ko.fill(ko.FRAME["wants"], x=e, text=", ".join(h["wants"])))
        elif e in self.things or e in self.obstacles and (self.obstacles[e].get("look")):
            d = self.things.get(e) or self.obstacles[e]
            out.append(ko.fill(ko.FRAME["look"], x=e, text=d.get("look", "")))
        return [Line("public", t) for t in out]

    def state(self, focus: set[str], text: str) -> str:
        return render(self.context(focus)) + "\n\n" + sentence(text)


def layer1(text: str, have: set[str], choices: list[str], ask: dict | None = None) -> tuple[str, dict]:
    """interpret.plan's first request; `ask` stands in for ko.SCHEMA_ASK in a named experiment."""
    ask = ask or ko.SCHEMA_ASK
    say = {σ: ask[σ] for σ in sorted(SAY, key=lambda σ: σ not in have)}
    if choices:
        say["choose"] = ko.fill(ko.CHOOSE_HERE, choices=", ".join(choices))
    return sentence(text), {"k": choice(ko.KIND_QUESTION, ko.KIND), "s1": choice(ko.STEP_QUESTION, say),
                            "n": choice(ko.COUNT_QUESTION, ko.COUNT)}


def plan(s1: dict, n: dict, read: list[str] | None, have, theta: float = STEP_THETA) -> list[str]:
    """interpret.plan's layer 1 on recorded answers: the steps' schemas, or ["idle"]."""
    top, pr = ranked(Probs(s1), sorted(SAY, key=lambda σ: σ not in have))[0]
    sure, one = pr >= theta and top in have, ranked(Probs(n), ko.COUNT)[0][0] == "1"
    if sure and one:
        return [top]
    steps = read
    if sure and steps and steps[0] not in have:
        steps = None
    if not one and steps and len(steps) > 1:
        return steps
    if not sure:
        if not steps:
            return ["idle"]
        top = steps[0]
    return [top]


@dataclass
class Ask:
    """interpret.fill's requests for one step: the main one (None when a name settles everything), the claim
    questions asked once the tone reads as deceit, each option's key, and what layer 0 settled with no question."""
    request: tuple[str, dict] | None
    claims: tuple[str, dict] | None
    keys: dict[str, dict] = field(default_factory=dict)
    settled: dict[str, object] = field(default_factory=dict)


def layer2(s: Scene, text: str, σ: str) -> Ask | None:
    """None where the engine has no slot for σ and refuses."""
    slots = s.slots(σ)
    if not slots:
        return None
    if σ == "try":
        return _try(s, text, slots)
    if σ == "talk":
        # a story topic only when the sentence names it (interpret.topic_named)
        slots = [(h, t) for h, t in slots
                 if t in ("favor", "come", "stay", "chat") or any(mentions(w, text) >= 0 for w in title_words(t))]
    intents = s.narrow(σ, slots, text)
    # The place the player is in, unless the sentence names a way out (interpret.fill).
    if σ == "go" and not any(i[0] in s.named(text) for i in intents):
        intents = [*intents, (s.here,)]
    keys = {i: f"e{n + 1}" for n, i in enumerate(intents)}
    qs, settled = {}, {}
    if len(intents) > 1:
        qs["intent"] = choice(ko.SLOT_QUESTION["intent"], {keys[i]: s.label(σ, i) for i in intents})
    else:
        settled["intent"] = intents[0]
    if σ == "talk":
        qs["tone"] = choice(ko.SLOT_QUESTION["tone"], {t: ko.TONE_DESC[t] for t in ko.TONES})
    focus = {s.here, *(e for i in intents for e in s.ents(σ, i))}
    claims = s.sc.get("claims", []) if σ == "talk" else []
    return Ask(request=(s.state(focus, text), qs) if qs else None,
               claims=(sentence(text), {f"c{n + 1}": noul(ko.fill(ko.CLAIM_QUESTION, text=c), ko.YES, ko.NO)
                                        for n, c in enumerate(claims)}) if claims else None,
               keys={"intent": keys, "claim": {c: f"c{n + 1}" for n, c in enumerate(claims)}}, settled=settled)


def _try(s: Scene, text: str, slots: list[tuple]) -> Ask:
    targets = s.narrow("try", sorted(set(slots), key=lambda t: -1 if t[0] == PLAYER else s.rank.get(t[0], 0)), text)
    keys = {t: f"e{n + 1}" for n, t in enumerate(targets)}
    qs, settled = {}, {}
    if len(targets) > 1:
        qs["target"] = choice(ko.SLOT_QUESTION["target"],
                              {keys[t]: ko.NO_TARGET if t[0] == PLAYER else t[0] for t in targets})
    else:
        settled["target"] = targets[0]
    cue = approach_cue(text)
    if cue:
        settled["approach"] = cue
    else:
        qs["approach"] = choice(ko.SLOT_QUESTION["approach"], {ap: ko.APPROACH_DESC[ap] for ap in APPROACHES})
    qs["strain"] = choice(ko.SLOT_QUESTION["strain"], dict(ko.STRAIN_DESC))
    focus = {s.here, *(t[0] for t in targets if t[0] != PLAYER)}
    return Ask(request=(s.state(focus, text), qs), claims=None, keys={"target": keys}, settled=settled)


def rely(item: dict) -> tuple[str, dict, list[int]] | None:
    """interpret.relevant for a bench reliance item: the request and which options it asks (by index); None when it
    asks nothing."""
    a = item["attempt"]
    lines = [ko.fill(ko.ATTEMPT, label=a["label"])]
    if a["target"].get("look"):
        lines.append(ko.fill(ko.FRAME["look"], x=a["target"]["name"], text=a["target"]["look"]))
    if item.get("text"):
        lines.append(sentence(item["text"]))
    asked = [i for i, o in enumerate(item["options"]) if o["kind"] not in UNASKED]
    if not asked:
        return None
    opts = {f"r{n}": ko.fill(ko.RELY_DESC[item["options"][i]["kind"]], name=item["options"][i].get("name") or "",
                             text=item["options"][i].get("text") or "") for n, i in enumerate(asked)}
    return "\n".join(lines), {"rely": choice(ko.RELY_QUESTION, {**opts, "none": ko.RELY_NONE})}, asked


def check(item: dict) -> tuple[str, dict]:
    """narrate.Narrator.judge for one sentence."""
    lines = [Line(sec, t) for sec, key in (("fact", "facts"), ("belief", "beliefs"), ("memory", "memory"),
                                           ("public", "public")) for t in item.get(key, [])]
    state = render(lines)
    if item.get("happened"):
        state += "\n" + ko.HEAD["happened"] + "\n" + "\n".join(f"- {x}" for x in item["happened"])
    q = choice(ko.fill(ko.CHECK_QUESTION, text=item["sentence"]), ko.CHECK)
    return state, {"0": q}
