"""Layer 1 option wording now that talk covers asking someone to come along or to wait, and the sureness rule.

  python variants.py record bench    # decision-1 bench, normal and cf, the new wordings (v0 is answers.jsonl)
  python variants.py record casual   # casual/items.jsonl: every wording, and the talk/go intent of each item
  python variants.py score

v0 is the wording before; v1 adds come/stay to talk; v2 is v1 with cut said of the player's own waiting.
casual/items.jsonl was written by a subagent from scene summaries alone, blind to the engine and to the misreads.
"""
import asyncio
import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).parent
spec = importlib.util.spec_from_file_location("mb", ROOT / "bench.py")
M = importlib.util.module_from_spec(spec)
spec.loader.exec_module(M)
B = M.B
from src.interpret import Interpreter, choice, mentions, ranked  # noqa: E402
from src.locale import ko  # noqa: E402

SAY = B.SAY
OUT = M.common.RUNS / "misread-1" / "variants.jsonl"
V0 = {**ko.SCHEMA_ASK,
      "talk": "누군가에게 묻거나, 부탁하거나, 겁을 주거나, 속이는 말을 한다 (예: 노인에게 길을 묻는다)",
      "cut": "기다리거나 쉬며 시간을 보낸다 (예: 날이 밝을 때까지 기다린다, 잠깐 눈을 붙인다)"}
VARIANTS = {
    "v0": V0,
    "v1": {**V0, "talk": "누군가에게 묻거나, 부탁하거나, 같이 가자거나 기다려 달라고 하거나, 겁을 주거나, 속이는 말을 "
                         "한다 (예: 노인에게 길을 묻는다)"},
}
VARIANTS["v2"] = {**VARIANTS["v1"], "cut": "자신이 기다리거나 쉬며 시간을 보낸다 (예: 날이 밝을 때까지 기다린다, 잠깐 눈을 "
                                            "붙인다)"}


def casual():
    sc = M.scenes()
    out = []
    for r in map(json.loads, (ROOT / "casual" / "items.jsonl").read_text().splitlines()):
        out.append({**r, "full": sc[(r["genre"], r["scene"])]})
    return out


def options(desc, have):
    return {s: desc[s] for s in sorted(SAY, key=lambda s: s not in have)}


def person_names(h):
    return [h["name"], *h.get("aliases", [])]


def talk_intents(it):
    sc, follow = it["full"], set(it.get("following", []))
    out = {k: v for k, v in B.intents(sc, "talk").items()}
    for h in sc.get("people", []):
        topic = "stay" if h["name"] in follow else "come"
        out[f"talk:{h['name']}:{topic}"] = B.fill(ko.ACTION[topic], h=h["name"])
    hit = [h["name"] for h in sc.get("people", []) if any(mentions(w, it["text"]) >= 0 for w in person_names(h))]
    if hit:
        out = {k: v for k, v in out.items() if k.split(":")[1] in hit}
    return out


def go_intents(it):
    sc = it["full"]
    out = {f"go:{e}": B.fill(ko.ACTION["go"], q=e) for e in sc.get("exits", [])}
    hit = {k: v for k, v in out.items() if mentions(k[3:], it["text"]) >= 0}
    if hit:
        return hit
    here = sc["place"]["name"]
    return {**out, f"go:{here}": B.fill(ko.ACTION["go"], q=here)}


async def record(which):
    kev, llm = M.common.models()
    it = Interpreter(kev, llm, timeout=60)
    done = {json.loads(x)["key"] for x in OUT.read_text().splitlines()} if OUT.exists() else set()
    f = OUT.open("a")

    async def layer1(key, text, have, gold, kind, names):
        for v in names:
            k = f"{v}:{key}"
            if k in done:
                continue
            opts = options(VARIANTS[v], have)
            a = await kev.decide(it.sentence(text), {"s1": choice(ko.STEP_QUESTION, opts),
                                                     "n": choice(ko.COUNT_QUESTION, ko.COUNT)})
            row = {"key": k, "variant": v, "set": kind, "text": text, "have": have, "gold": gold,
                   "kev": {q: dict(x.probabilities) for q, x in a.items()}, "read": await it.read(text, opts)}
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
            f.flush()

    if which == "bench":
        for n, (key, text, have, gold, kind) in enumerate(M.layer1_requests()):
            await layer1(key, text, have, gold, kind, ("v1", "v2"))
            if n % 50 == 0:
                print("bench", n, flush=True)
    else:
        for n, x in enumerate(casual()):
            have = B.available(x["full"])
            await layer1(x["id"], x["text"], have, x["steps"][:3], "casual", ("v0", "v1", "v2"))
            first = x["steps"][0]
            k = f"l2:{x['id']}"
            if first in ("talk", "go") and k not in done:
                labels = talk_intents(x) if first == "talk" else go_intents(x)
                row = {"key": k, "schema": first, "text": x["text"], "detail": x["detail"], "labels": labels,
                       "here": x["full"]["place"]["name"]}
                if len(labels) > 1:
                    state = B.render(x["full"], x["text"])
                    q = choice(ko.SLOT_QUESTION["intent"], labels)
                    a = await kev.decide(state, {"intent": q})
                    row["kev"] = dict(a["intent"].probabilities)
                    row["pick"] = await it.pick(state, q["instructions"], labels)
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
                f.flush()
            if n % 25 == 0:
                print("casual", n, flush=True)
    print("done", flush=True)


class _ans:
    def __init__(self, p):
        self.probabilities = p


def plan(kev, read, have, theta, always=False, both=()):
    """interpret.plan's layer 1 on recorded answers; Kev alone is never sure of a schema in both."""
    every = [s for s in SAY if s in have] + [s for s in SAY if s not in have]
    top, pr = ranked(_ans(kev["s1"]), every)[0]
    sure, one = pr >= theta and top in have, ranked(_ans(kev["n"]), ko.COUNT)[0][0] == "1"
    if sure and top in both and read and read[0] != top:
        sure = False
    if sure and one and not always:
        return [top]
    steps = read
    if sure and steps and steps[0] not in have:
        steps = None
    if not one and steps and len(steps) > 1:
        return steps
    if not sure or always and steps:
        if not steps:
            return ["idle"]
        top = steps[0]
    return [top]


def right(p, r):
    return p[:len(r["gold"])] == r["gold"] if r["set"] == "cf" else p == r["gold"]


def score():
    rows = [json.loads(x) for x in OUT.read_text().splitlines()]
    old = {r["key"][3:]: r for r in map(json.loads, M.OUT.read_text().splitlines()) if r["key"].startswith("l1:")}
    l1 = {}
    for r in rows:
        if "variant" in r:
            l1[r["key"]] = r
    for k, r in old.items():           # v0 on the bench: misread-1's "all" answers
        l1.setdefault(f"v0:{k}", {**r, "key": f"v0:{k}", "variant": "v0", "kev": r["all"]})
    policies = [(v, th, al, bo) for v in VARIANTS for th, al, bo in (
        (0.5, False, ()), (0.5, False, ("cut",)), (0.6, False, ()), (0.7, False, ()), (0.5, True, ()))]

    def run(key, pol):
        v, th, al, bo = pol
        r = l1.get(f"{v}:{key}")
        return None if r is None else plan(r["kev"], r["read"], r["have"], th, al, bo)

    sets = {"casual": lambda r: r["set"] == "casual", "bench normal": lambda r: r["set"] == "normal",
            "bench cf": lambda r: r["set"] == "cf"}
    base = ("v0", 0.5, False, ())
    print("| set | policy | n | right | +/- vs v0 θ0.5 | p |")
    print("|---|---|---|---|---|---|")
    for name, part in sets.items():
        keys = sorted({k.split(":", 1)[1] for k, r in l1.items() if part(r)})
        for pol in policies:
            got = [(run(k, pol), run(k, base), l1[f"v0:{k}"]) for k in keys if f"{pol[0]}:{k}" in l1]
            if not got:
                continue
            a = [right(p, r) for p, _, r in got]
            b = [right(q, r) for _, q, r in got]
            up = sum(x and not y for x, y in zip(a, b))
            down = sum(y and not x for x, y in zip(a, b))
            label = f"{pol[0]} {'read always' if pol[2] else f'θ{pol[1]}'}{' cut both' if pol[3] else ''}"
            print(f"| {name} | {label} | {len(got)} | {sum(a)} | +{up}/-{down} | {M.sign(up, down):.3g} |")
    if "-v" in sys.argv:
        pol = (sys.argv[sys.argv.index("-v") + 1], 0.5, False, ("cut",) if "-cut" in sys.argv else ())
        for k in sorted({k.split(":", 1)[1] for k, r in l1.items() if r["set"] == "casual"}):
            r = l1[f"v0:{k}"]
            a, b = run(k, base), run(k, pol)
            if right(a, r) != right(b, r) or not right(b, r):
                print(f"- {k} gold {r['gold']} v0 {a} {pol[0]} {b}: {r['text']}")
    l2 = [r for r in rows if r["key"].startswith("l2:")]
    if l2:
        print("\n## casual intents (Kev sure, else pick; staying on go needs both)\n")
        ok = {"talk": [0, 0], "go": [0, 0]}
        for r in l2:
            d = r["detail"]
            gold = (f"talk:{d['to']}:{d['topic']}" if r["schema"] == "talk"
                    else f"go:{d['to']}" if d.get("to") else None)
            keys = list(r["labels"])
            if len(keys) == 1:
                got = keys[0]
            else:
                top, pr = ranked(_ans(r["kev"]), keys)[0]
                stay = r["schema"] == "go" and top == f"go:{r['here']}"
                got = top if pr >= 0.5 and not stay else r.get("pick")
            hit = got == gold if gold else (got is not None and got != f"go:{r['here']}")
            ok[r["schema"]][0] += hit
            ok[r["schema"]][1] += 1
            if not hit:
                print(f"- {r['key'][3:]} gold {gold or 'any exit'} got {got}: {r['text']}")
        print({k: f"{a}/{n}" for k, (a, n) in ok.items()})


if __name__ == "__main__":
    asyncio.run(record(sys.argv[2])) if sys.argv[1] == "record" else score()
