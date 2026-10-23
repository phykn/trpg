import asyncio
import sys
from collections import Counter
from pathlib import Path
from types import SimpleNamespace

import yaml

sys.path[:0] = [str(Path(__file__).resolve().parent), str(Path(__file__).resolve().parents[1])]
import common
import mirror as M
from src.cards import rely_options
from src.interpret import SAY, Interpreter, rely_name
from src.lang.context import _past, scene
from src.narrate import Job, Narrator
from src.onto.atoms import APPROACHES, PLAYER
from src.onto.view import hidden, observe
from src.rules.acts import make
from src.rules.candidates import space, traits_of
from src.service import fresh_presentation
from src.story.evals import replay
from src.story.validate import _path, load
from src.view import action_label


class Kev:
    """Records each request; answers every choice with its last option, so tone reads as deceit and claims get asked."""

    def __init__(self, s1=None, n=None, k=None):
        self.calls, self.s1, self.n, self.k = [], s1, n, k

    async def decide(self, state, questions):
        self.calls.append((state, questions))
        out = {}
        for k, q in questions.items():
            if k == "s1" and self.s1 is not None:
                p = self.s1
            elif k == "n" and self.n is not None:
                p = self.n
            elif k == "k" and self.k is not None:
                p = self.k
            elif q["type"] == "noul":
                p = {"true": 1.0, "false": 0.0}
            else:
                p = {c: float(c == list(q["criteria"])[-1]) for c in q["criteria"]}
            out[k] = SimpleNamespace(probabilities=p)
        return out


class Reader:
    def __init__(self, raw="1"):
        self.raw = raw

    async def pick(self, messages):
        return self.raw


def scene_of(u, o) -> dict:
    """The engine's view of a state written as a bench scene (GUIDE.md), with the story order and the blocks a scene
    may carry."""
    f, here = o.facts, o.facts.where(PLAYER)
    seen = sorted(o.seen, key=u.rank)
    slots = space(u, o)
    open_topics = {s.intent for s in slots if s.schema == "talk"}
    people = []
    for h in seen:
        if h not in u.agents or f.where(h) != here:
            continue
        a = u.agents[h]
        people.append({"name": a.name, "aliases": list(a.aliases), "persona": a.persona, "voice": a.voice,
                       "desire": a.desire, "fear": a.fear, "topics": [t.title for t in a.topics],
                       "favor": a.favor.label if (h, "favor") in open_topics else None,
                       "wants": [u.name(w) for w in a.wants if not hidden(u, w, PLAYER, o.facts)],
                       "trust": f.regards(h, PLAYER, "trust") or 0})
    things = [{"name": u.name(t), "aliases": list(u.aliases(t)), "look": u.things[t].look,
               "where": "player" if f.where(t) == PLAYER else "here"} for t in seen if t in u.things]
    obstacles, threats, forks = [], [], []
    for x in seen:
        ob = u.obstacles.get(x)
        if ob is None:
            continue
        if f.where(x) == PLAYER and ob.sub == "fork":
            forks.append({"name": ob.name, "options": [n for _, n, _ in ob.choices]})
        elif f.where(x) == PLAYER:
            threats.append(ob.name)
        else:
            obstacles.append({"name": ob.name, "aliases": list(ob.aliases), "look": ob.look, "boxes": u.boxes(x),
                              "fill": f.fill(x) or 0, "blocks": [u.name(b) for b in ob.blocks]})
    return {
        "place": {"name": u.name(here), "aliases": list(u.aliases(here)), "senses": list(u.places[here].senses),
                  "rest": u.places[here].rest},
        "exits": [{"name": u.name(q), "aliases": list(u.aliases(q))} for q in seen
                  if u.kind(q) == "place" and q != here and f.has("link", here, q)],
        "people": people, "things": things, "obstacles": obstacles, "threats": threats, "forks": forks,
        "latents": [{"name": u.latents[s.intent[0]].name} for s in slots if s.schema == "declare"],
        "claims": [u.props[c].text for c in sorted(u.claims)],
        "following": [u.name(h) for h in u.agents if f.has("follows", h, PLAYER)],
        "player": {"traits": [{"name": u.traits[t][0], "text": u.traits[t][1]} for t in traits_of(u, f)],
                   "stats": {ap: f.stat(PLAYER, ap) or 0 for ap in APPROACHES}, "wounds": f.stat(PLAYER, "wounds") or 0},
        "memory": [_past(u, m) for m in o.memory],
        "order": [u.name(x) for x in seen if x != PLAYER],
    }


def sections(state: str) -> tuple[Counter, str]:
    """A context's lines by section, and what follows it (the sentence)."""
    body, _, tail = state.partition("\n\n")
    lines, head = Counter(), ""
    for ln in body.splitlines():
        if ln.startswith("- "):
            lines[(head, ln)] += 1
        else:
            head = ln
    return lines, tail


def compare(where: str, engine, bench, context: bool = False) -> list[str]:
    """Requests must match exactly, except that intent and target keys stand in for story ids, claim questions are
    keyed by position, and a scene context may leave out lines a bench scene cannot hold (exit senses, personas,
    beliefs): every line the bench sends must be one the engine sends."""
    if bench is None:
        return [f"{where}: the engine asks, the bench does not"]
    out = []
    (es, eq), (bs, bq) = engine, bench
    if context:
        el, et = sections(es)
        bl, bt = sections(bs)
        extra = bl - el
        if extra or et != bt:
            out.append(f"{where}: context lines the engine does not send: {sorted(extra)} / {et!r} vs {bt!r}")
    elif es != bs:
        out.append(f"{where}: state differs:\n  engine {es!r}\n  bench  {bs!r}")
    claims = all(q["type"] == "noul" for q in eq.values()) and eq
    if claims:
        if sorted(q["instructions"] for q in eq.values()) != sorted(q["instructions"] for q in bq.values()):
            out.append(f"{where}: claim questions differ: {eq} vs {bq}")
        return out
    if list(eq) != list(bq):
        return out + [f"{where}: questions {list(eq)} vs {list(bq)}"]
    for k in eq:
        e, b = eq[k], bq[k]
        if (e["type"], e["instructions"]) != (b["type"], b["instructions"]):
            out.append(f"{where} {k}: {e['type']} {e['instructions']!r} vs {b['type']} {b['instructions']!r}")
        ec, bc = list(e["criteria"].items()), list(b["criteria"].items())
        same = [v for _, v in ec] == [v for _, v in bc] if k in ("intent", "target") else ec == bc
        if not same:
            out.append(f"{where} {k}: options\n  engine {ec}\n  bench  {bc}")
    return out


async def run_check() -> tuple[list[str], Counter]:
    """Every story's eval states with their sentences, and every step of its witness paths with one sentence of each
    kind the evals expect."""
    bad, n = [], Counter()
    for evals in sorted((common.checkout() / "scenarios").glob("*/evals.yaml")):
        u = load(evals.parent / "story.yaml")
        cases = yaml.safe_load(evals.read_text(encoding="utf-8"))
        states, kinds = {}, {}
        for e in cases:
            states.setdefault(repr(e["at"]), (e["at"], []))[1].append(e["text"])
            want = e["expect"][0] if isinstance(e["expect"], list) else e["expect"]
            kinds.setdefault(want.split(":")[0], e["text"])
        paths = u.witnesses["paths"]
        for i in range(len(paths)):
            for k in range(len(_path(paths, i, "parity")) + 1):
                states.setdefault(repr({"path": i, "step": k}), ({"path": i, "step": k}, list(kinds.values())))
        for at, texts in states.values():
            bad += await check_state(u, at, texts, n)
        n["states"] += len(states)
    return bad, n


async def check_state(u, at, texts, n: Counter) -> list[str]:
    run = replay(u, at)
    g = SimpleNamespace(state=run.s, log=run.log, presentation=fresh_presentation(""))
    o = observe(u, g.state, g.log)
    s = M.Scene(scene_of(u, o))
    bad = []
    have = {x.schema for x in space(u, o)} & set(SAY)
    if s.have() != have:
        bad.append(f"{at}: schemas possible here: engine {sorted(have)}, bench {sorted(s.have())}")
    for text in texts:
        where = f"{at} {text!r}"
        kev = Kev()
        it = Interpreter(kev, Reader())
        await it.plan(u, g, text)
        if kev.calls:              # layer 0 settles some sentences with no model
            bad += compare(f"{where} layer 1", kev.calls[0], M.layer1(text, s.have(), s.choices()))
            n["layer 1"] += 1
        for σ in sorted(have):
            kev.calls = []
            got = await it.fill(u, g, {"schema": σ, "text": text, "fixed": {}})
            a = M.layer2(s, text, σ)
            mine = [r for r in (a.request, a.claims) if r] if a else []
            if not kev.calls and mine:
                if got.get("refused"):
                    n["refused by the engine, not compared"] += 1
                    continue
                bad.append(f"{where} {σ}: the bench asks {mine[0][1].keys()}, the engine nothing")
            for i, call in enumerate(kev.calls):
                bad += compare(f"{where} {σ}", call, mine[i] if i < len(mine) else None, context=i == 0)
                n["layer 2"] += 1
    bad += await check_rely(u, o, g, s, texts[0], n)
    bad += await check_narration(u, o, g, n)
    bad += await check_plan(u, g, s, n)
    return bad


async def check_rely(u, o, g, s, text, n) -> list[str]:
    bad = []
    for slot in space(u, o):
        x = slot.intent[0]
        if slot.schema != "try" or x == PLAYER or not (x in u.things or x in u.obstacles and u.obstacles[x].look):
            continue                # a bench reliance item's target is a thing or an obstacle with a look
        a = make("try", slot.intent)
        values = rely_options(u, o, a)
        linked = {sol.rely for sol in u.obstacles[x].solutions} if x in u.obstacles else set()
        p = fresh_presentation("")
        kev = Kev()
        await Interpreter(kev, Reader()).relevant(u, o, p, a, values, None, text)
        opts = []
        for v in values:
            if v in linked:
                continue            # the story ties it to the target: kept unasked, and a bench item has no ties
            kind, _, rest = v.partition(":")
            body = (u.traits[rest][1] if kind == "trait" else u.things[rest].look if kind == "thing"
                    else u.props[rest].text if kind == "prop" else "")
            opts.append({"kind": kind, "name": rely_name(u, p, o.facts, v), "text": body})
        item = {"attempt": {"label": action_label(u, o, p, a), "target": {"name": u.name(x), "look": (
            u.things[x].look if x in u.things else u.obstacles[x].look)}}, "text": text, "options": opts}
        mine = M.rely(item)
        if kev.calls or mine:
            bad += compare(f"rely {slot.intent}", kev.calls[0] if kev.calls else (None, {}),
                           mine[:2] if mine else None)
            n["rely"] += 1
    return bad


async def check_narration(u, o, g, n) -> list[str]:
    here = o.facts.where(PLAYER)
    focus = {PLAYER, here, *(h for h in o.seen if h in u.agents)}
    job = Job(u, o, g.presentation, ["당신이 주위를 둘러보았습니다"], [], focus)
    kev = Kev()
    said = "바람이 거세집니다."
    await Narrator(None, kev).judge(job, [said], set())
    lines = scene(u, o, focus, g.presentation)
    item = {key: [ln.text for ln in lines if ln.section == sec]
            for sec, key in (("fact", "facts"), ("belief", "beliefs"), ("memory", "memory"), ("public", "public"))}
    n["narration check"] += 1
    return compare("narration check", kev.calls[0], M.check({**item, "happened": job.happened, "sentence": said}))


async def check_plan(u, g, s, n) -> list[str]:
    """M.plan against interpret.plan over sure and unsure, possible and impossible, one and several steps, for a line
    read as an act (the bench's sentences are all actions; small talk and musing stop before the parts)."""
    have = s.have()
    say = list(M.layer1("", have, s.choices())[1]["s1"]["criteria"])
    inside, outside = [σ for σ in say if σ in have], [σ for σ in say if σ not in have]
    bad = []
    for top in (inside[0], *outside[:1]):
        for p in (0.6, 0.8):
            for count in ("1", "2"):
                for read in (None, [inside[-1]], [inside[-1], inside[0]], [*outside[:1]]):
                    s1 = {σ: (p if σ == top else (1 - p) / (len(say) - 1)) for σ in say}
                    count_p = {c: float(c == count) for c in ("1", "2", "3")}
                    raw = ",".join(str(say.index(σ) + 1) for σ in read) if read else ""
                    it = Interpreter(Kev(s1=s1, n=count_p, k={"act": 1.0}), Reader(raw))
                    got = [st.get("schema") or ("idle" if st.get("idle") else st)
                           for st in (await it.plan(u, g, "그냥 해 본다"))["plan"]]
                    want = M.plan(s1, count_p, read, have)
                    n["plan rule"] += 1
                    if got != want:
                        bad.append(f"plan rule: top {top} {p} n {count} read {read}: engine {got}, bench {want}")
    return bad


def check() -> None:
    """Stops the caller when the bench's base requests are not what the engine sends."""
    bad, n = asyncio.run(run_check())
    if bad:
        raise SystemExit("The bench no longer sends what the engine sends (qa/decision/parity.py):\n" +
                         "\n".join(bad[:40]) + (f"\n… {len(bad) - 40} more" if len(bad) > 40 else ""))
    print("parity: " + ", ".join(f"{k} {v}" for k, v in n.items()))


if __name__ == "__main__":
    check()
