"""Layer 1 option wording against the engine's own, and the rule for a sure first step.

  python variants.py record bench --run RUN    # the misread bench's items under each experiment (needs bench.py's RUN)
  python variants.py record casual --run RUN   # casual/items.jsonl: the engine's wording and each experiment, and the
                                               # talk/go intent of each item
  python variants.py score --run RUN [-v EXPERIMENT [-cut]]

v0 is the engine's ko.SCHEMA_ASK (on the bench, the misread bench's answers in the same RUN). An experiment replaces
some options on purpose: v1 says talk covers asking someone to come along or to wait, v2 is v1 with cut said of the
player's own waiting. casual/items.jsonl was written by a subagent from scene summaries alone, blind to the engine and
to the misreads.
"""
import argparse
import asyncio
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).parent
spec = importlib.util.spec_from_file_location("mb", ROOT / "bench.py")
MB = importlib.util.module_from_spec(spec)
spec.loader.exec_module(MB)
M = MB.M
from src.interpret import SAY, STEP_THETA, THETA, Interpreter, ranked
from src.locale import ko

EXPERIMENTS = {
    "v1": {"talk": "누군가에게 묻거나, 부탁하거나, 같이 가자거나 기다려 달라고 하거나, 겁을 주거나, 속이는 말을 한다 "
                   "(예: 노인에게 길을 묻는다)"},
}
EXPERIMENTS["v2"] = {**EXPERIMENTS["v1"],
                     "cut": "자신이 기다리거나 쉬며 시간을 보낸다 (예: 날이 밝을 때까지 기다린다, 잠깐 눈을 붙인다)"}


def ask(v):
    return None if v == "v0" else {**ko.SCHEMA_ASK, **EXPERIMENTS[v]}


def casual():
    sc = MB.scenes()
    return [{**r, "full": {**sc[(r["genre"], r["scene"])], "following": r.get("following", [])}}
            for r in map(json.loads, (ROOT / "casual" / "items.jsonl").read_text().splitlines())]


async def record(which, out: Path):
    kev, llm = MB.common.models()
    it = Interpreter(kev, llm, timeout=60)
    done = {json.loads(x)["key"] for x in out.read_text().splitlines()} if out.exists() else set()
    out.parent.mkdir(parents=True, exist_ok=True)
    f = out.open("a")

    async def layer1(key, sc, text, have, gold, kind, names):
        for v in names:
            k = f"{v}:{key}"
            if k in done:
                continue
            state, qs = M.layer1(text, have, M.Scene(sc).choices() if "choose" in have else [], ask(v))
            a = await kev.decide(state, qs)
            row = {"key": k, "variant": v, "set": kind, "text": text, "have": [σ for σ in SAY if σ in have],
                   "gold": gold, "kev": {q: dict(x.probabilities) for q, x in a.items()},
                   "read": await it.read(text, qs["s1"]["criteria"])}
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
            f.flush()

    if which == "bench":
        for n, (key, sc, text, have, gold, kind) in enumerate(MB.layer1_requests()):
            await layer1(key, sc, text, have, gold, kind, list(EXPERIMENTS))
            if n % 50 == 0:
                print("bench", n, flush=True)
    else:
        for n, x in enumerate(casual()):
            s = M.Scene(x["full"])
            await layer1(x["id"], x["full"], x["text"], s.have(), x["steps"][:3], "casual", ["v0", *EXPERIMENTS])
            first, d = x["steps"][0], x["detail"]
            k = f"l2:{x['id']}"
            if first in ("talk", "go") and k not in done:
                a = M.layer2(s, x["text"], first)
                want = (d["to"], d["topic"]) if first == "talk" else (d["to"],) if d.get("to") else None
                keys = a.keys["intent"]
                row = {"key": k, "schema": first, "text": x["text"], "gold": keys.get(want) if want else None,
                       "stay": keys.get((s.here,)) if first == "go" else None, "keys": list(keys.values())}
                if a.request and "intent" in a.request[1]:
                    state, qs = a.request
                    row["kev"] = dict((await kev.decide(state, qs))["intent"].probabilities)
                    row["pick"] = await it.pick(state, qs["intent"]["instructions"], qs["intent"]["criteria"])
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
                f.flush()
            if n % 25 == 0:
                print("casual", n, flush=True)
    print("done", flush=True)


def plan(kev, read, have, theta=STEP_THETA, always=False, both=()):
    """interpret.plan's rule (mirror.plan), or an experiment on it: the narration model's reading always taken first, or
    the decision model alone never sure of a schema in `both`."""
    if not always and not both:
        return M.plan(kev["s1"], kev["n"], read, have, theta)
    top, pr = ranked(M.Probs(kev["s1"]), sorted(SAY, key=lambda σ: σ not in have))[0]
    sure, one = pr >= theta and top in have, ranked(M.Probs(kev["n"]), ko.COUNT)[0][0] == "1"
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


def score(run: Path, verbose: str | None, cut: bool):
    rows = [json.loads(x) for x in (run / "variants.jsonl").read_text().splitlines()]
    l1 = {r["key"]: r for r in rows if "variant" in r}
    bench = run / "answers.jsonl"
    for r in map(json.loads, bench.read_text().splitlines() if bench.exists() else []):
        if r["key"].startswith("l1:"):           # v0 on the bench: the misread bench's own answers
            l1.setdefault(f"v0:{r['key'][3:]}", {**r, "variant": "v0", "kev": MB.l1_answers(r)})
    engine = ("v0", STEP_THETA, False, ())
    policies = [engine, ("v0", 0.5, False, ()), ("v0", STEP_THETA, False, ("cut",)), ("v0", STEP_THETA, True, ()),
                *((v, STEP_THETA, False, ()) for v in EXPERIMENTS)]

    def run_(key, pol):
        v, th, al, bo = pol
        r = l1.get(f"{v}:{key}")
        return None if r is None else plan(r["kev"], r["read"], set(r["have"]), th, al, bo)

    sets = {"casual": lambda r: r["set"] == "casual", "bench normal": lambda r: r["set"] == "normal",
            "bench cf": lambda r: r["set"] == "cf"}
    print(f"| set | policy | n | right | +/- vs the engine's (v0 θ{STEP_THETA}) | p |")
    print("|---|---|---|---|---|---|")
    for name, part in sets.items():
        keys = sorted({k.split(":", 1)[1] for k, r in l1.items() if part(r)})
        for pol in policies:
            got = [(run_(k, pol), run_(k, engine), l1[f"v0:{k}"]) for k in keys
                   if f"{pol[0]}:{k}" in l1 and f"v0:{k}" in l1]
            if not got:
                continue
            a = [MB.right(p, r) for p, _, r in got]
            b = [MB.right(q, r) for _, q, r in got]
            up = sum(x and not y for x, y in zip(a, b))
            down = sum(y and not x for x, y in zip(a, b))
            label = f"{pol[0]} {'read always' if pol[2] else f'θ{pol[1]}'}{' cut both' if pol[3] else ''}"
            print(f"| {name} | {label} | {len(got)} | {sum(a)} | +{up}/-{down} | {MB.sign(up, down):.3g} |")
    if verbose:
        pol = (verbose, STEP_THETA, False, ("cut",) if cut else ())
        for k in sorted({k.split(":", 1)[1] for k, r in l1.items() if r["set"] == "casual"}):
            r = l1[f"v0:{k}"]
            a, b = run_(k, engine), run_(k, pol)
            if MB.right(a, r) != MB.right(b, r) or not MB.right(b, r):
                print(f"- {k} gold {r['gold']} v0 {a} {pol[0]} {b}: {r['text']}")
    l2 = [r for r in rows if r["key"].startswith("l2:") and "keys" in r]      # misread-1's are in an older form
    if l2:
        print("\n## casual intents (the decision model when sure, else the narration model's pick; staying needs both)\n")
        ok = {"talk": [0, 0], "go": [0, 0]}
        for r in l2:
            keys = r["keys"]
            if len(keys) == 1:
                got = keys[0]
            else:
                top, pr = ranked(M.Probs(r.get("kev")), keys)[0]
                got = top if pr >= THETA and top != r["stay"] else r.get("pick")
            hit = got == r["gold"] if r["gold"] else got not in (None, r["stay"])
            ok[r["schema"]][0] += hit
            ok[r["schema"]][1] += 1
            if not hit:
                print(f"- {r['key'][3:]} gold {r['gold'] or 'any exit'} got {got}: {r['text']}")
        print({k: f"{a}/{n}" for k, (a, n) in ok.items()})


def main():
    ap = argparse.ArgumentParser(usage=__doc__)
    ap.add_argument("cmd", choices=("record", "score"))
    ap.add_argument("which", nargs="?", choices=("bench", "casual"))
    ap.add_argument("--run", required=True)
    ap.add_argument("-v", help="list the casual items this policy's wording changes")
    ap.add_argument("-cut", action="store_true", help="with -v: the decision model alone is never sure of cut")
    ap.add_argument("--root")
    a = ap.parse_args()
    run = MB.common.RUNS / a.run
    if a.cmd == "record":
        if not a.which:
            raise SystemExit("record bench or record casual")
        MB.parity.check()
        asyncio.run(record(a.which, run / "variants.jsonl"))
    else:
        score(run, a.v, a.cut)


if __name__ == "__main__":
    main()
