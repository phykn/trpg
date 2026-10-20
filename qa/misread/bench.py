"""Closed options that miss the sentence's answer: layer 1 over every schema, and go with the current place.

  python bench.py record     # Kev and the narration model on every request; appends to answers.jsonl
  python bench.py score      # the engine's plan before and after, paired

Items: decision-1's 216 bench sentences and 120 held-out ones, as they are ("normal"), and the same sentences with
the asked thing made impossible ("cf"): layer 1 with the first step's schema removed from the scene, go with the
player already standing at the destination. Nothing here is written for this test.
"""
import asyncio
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).parent
D1 = ROOT.parent / "decision"
sys.path.insert(0, str(ROOT.parent))
sys.path.insert(0, str(D1))
import bench as B  # noqa: E402
import common  # noqa: E402
from src.interpret import Interpreter, choice, mentions, ranked  # noqa: E402
from src.locale import ko  # noqa: E402

THETA = 0.5
SAY = B.SAY
OUT = common.RUNS / "misread-1" / "answers.jsonl"
REPLACEABLE = {"go", "take", "give", "talk", "declare", "choose"}   # look, try and cut are always possible


def scenes():
    out = {}
    for g in ("fantasy", "horror", "joseon", "mystery", "postapoc", "scifi"):
        seen = []
        for r in map(json.loads, (D1 / "data" / f"{g}.jsonl").read_text().splitlines()):
            if r["kind"] == "sentence":
                k = json.dumps(r["scene"], sort_keys=True, ensure_ascii=False)
                if k not in seen:
                    seen.append(k)
        for i, k in enumerate(seen):
            out[(g, i)] = json.loads(k)
    return out


def items():
    out = [{"id": r["id"], "scene": r["scene"], "text": r["text"], "steps": r["gold"]["steps"],
            "detail": r["gold"]["detail"]} for r in B.load() if r["kind"] == "sentence"]
    sc = scenes()
    for h in map(json.loads, (D1 / "heldout" / "plan.jsonl").read_text().splitlines()):
        out.append({"id": h["id"], "scene": sc[(h["genre"], h["scene"])], "text": h["text"], "steps": h["steps"],
                    "detail": None})
    return out


def layer1_requests():
    """(key, text, have, gold plan, set)."""
    for it in items():
        have = B.available(it["scene"])
        yield it["id"], it["text"], have, it["steps"][:3], "normal"
        if it["steps"][0] in REPLACEABLE:
            yield it["id"] + "~cf", it["text"], [s for s in have if s != it["steps"][0]], it["steps"][:1], "cf"


def go_requests():
    """(key, scene, text, gold destination, set); the gold of a cf item is the place the player is in."""
    for it in items():
        if it["steps"][0] != "go" or not it["detail"]:
            continue
        sc, to = it["scene"], it["detail"]["to"]
        yield it["id"], sc, it["text"], to, "normal"
        here = sc["place"]["name"]
        moved = {**sc, "place": {**sc["place"], "name": to},
                 "exits": [e for e in sc["exits"] if e != to] + [here]}
        yield it["id"] + "~cf", moved, it["text"], to, "cf"


def go_options(sc, stay):
    names = list(sc["exits"]) + ([sc["place"]["name"]] if stay else [])
    return {f"e{i + 1}": n for i, n in enumerate(names)}


def narrow(names: dict, text):
    """interpret.narrow for one-entity intents: the options the sentence names, else all."""
    hit = [k for k, n in names.items() if mentions(n, text) >= 0]
    return hit or list(names)


async def record():
    kev, llm = common.models()
    it = Interpreter(kev, llm, timeout=60)
    done = {json.loads(x)["key"] for x in OUT.read_text().splitlines()} if OUT.exists() else set()
    f = OUT.open("a")
    n = 0
    for key, text, have, gold, kind in layer1_requests():
        k = f"l1:{key}"
        if k in done:
            continue
        first = {s: ko.SCHEMA_ASK[s] for s in SAY if s in have}
        every = first | {s: ko.SCHEMA_ASK[s] for s in SAY if s not in have}
        state = it.sentence(text)
        row = {"key": k, "set": kind, "text": text, "have": have, "gold": gold}
        for name, opts in (("base", first), ("all", every)):
            a = await kev.decide(state, {"s1": choice(ko.STEP_QUESTION, opts), "n": choice(ko.COUNT_QUESTION, ko.COUNT)})
            row[name] = {q: dict(v.probabilities) for q, v in a.items()}
        row["read"] = await it.read(text, every)
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
        f.flush()
        n += 1
        if n % 25 == 0:
            print("l1", n, flush=True)
    for key, sc, text, to, kind in go_requests():
        k = f"go:{key}"
        if k in done:
            continue
        state = B.render(sc, text)
        row = {"key": k, "set": kind, "text": text, "gold": to, "here": sc["place"]["name"]}
        for name, stay in (("base", False), ("stay", True)):
            names = go_options(sc, stay)
            keys = narrow(names, text)
            labels = {x: ko.fill(ko.ACTION["go"], q=names[x]) for x in keys}
            got = {"names": names, "narrowed": keys}
            if len(keys) > 1:
                q = choice(ko.SLOT_QUESTION["intent"], labels)
                a = await kev.decide(state, {"intent": q})
                got["kev"] = dict(a["intent"].probabilities)
                got["pick"] = await it.pick(state, q["instructions"], labels)
            row[name] = got
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
        f.flush()
    print("done", flush=True)


def plan_base(r):
    have = r["have"]
    first = [s for s in SAY if s in have]
    top, pr = ranked(_ans(r["base"]["s1"]), first)[0]
    sure, one = pr >= THETA, ranked(_ans(r["base"]["n"]), ko.COUNT)[0][0] == "1"
    if sure and one:
        return [top]
    steps = r["read"]
    if steps and steps[0] not in have:
        steps = None
    if not one and steps and len(steps) > 1:
        return steps
    if not sure:
        if not steps:
            return ["idle"]
        top = steps[0]
    return [top]


def plan_all(r):
    have = r["have"]
    every = [s for s in SAY if s in have] + [s for s in SAY if s not in have]
    top, pr = ranked(_ans(r["all"]["s1"]), every)[0]
    sure, one = pr >= THETA and top in have, ranked(_ans(r["all"]["n"]), ko.COUNT)[0][0] == "1"
    if sure and one:
        return [top]
    steps = r["read"]
    if sure and steps and steps[0] not in have:
        steps = None
    if not one and steps and len(steps) > 1:
        return steps
    if not sure:
        if not steps:
            return ["idle"]
        top = steps[0]
    return [top]


class _ans:
    def __init__(self, p):
        self.probabilities = p


def go_pick(got, here):
    """interpret.fill for go: Kev's sure answer, except that staying needs the narration model's pick too."""
    keys = got["narrowed"]
    if len(keys) == 1:
        return got["names"][keys[0]]
    top, pr = ranked(_ans(got["kev"]), keys)[0]
    w = top if pr >= THETA and got["names"][top] != here else got.get("pick")
    return got["names"][w] if w else None


def sign(b, c):
    n = b + c
    k = min(b, c)
    return 1.0 if n == 0 else min(1.0, 2 * sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n)


def outcome(plan, have):
    return "idle" if plan == ["idle"] else "refused" if plan[0] not in have else "acted"


def score():
    rows = [json.loads(x) for x in OUT.read_text().splitlines()]
    l1 = [r for r in rows if r["key"].startswith("l1:")]
    print("## layer 1: every schema offered (all) vs those possible here (base)\n")
    print("| set | n | base right | all right | +/- | p | base idle/refused/acted | all idle/refused/acted |")
    print("|---|---|---|---|---|---|---|---|")
    for kind, part in (("normal bench", lambda r: r["set"] == "normal" and "-s" in r["key"]),
                       ("normal held-out", lambda r: r["set"] == "normal" and "-h" in r["key"]),
                       ("cf bench", lambda r: r["set"] == "cf" and "-s" in r["key"]),
                       ("cf held-out", lambda r: r["set"] == "cf" and "-h" in r["key"])):
        rs = [r for r in l1 if part(r)]
        a = [plan_base(r) for r in rs]
        b = [plan_all(r) for r in rs]
        ra = [p[:len(r["gold"])] == r["gold"] if r["set"] == "cf" else p == r["gold"] for p, r in zip(a, rs)]
        rb = [p[:len(r["gold"])] == r["gold"] if r["set"] == "cf" else p == r["gold"] for p, r in zip(b, rs)]
        up = sum(y and not x for x, y in zip(ra, rb))
        down = sum(x and not y for x, y in zip(ra, rb))

        def outs(ps):
            o = [outcome(p, r["have"]) for p, r in zip(ps, rs)]
            return "/".join(str(o.count(k)) for k in ("idle", "refused", "acted"))
        print(f"| {kind} | {len(rs)} | {sum(ra)} | {sum(rb)} | +{up}/-{down} | {sign(up, down):.3g} | {outs(a)} | "
              f"{outs(b)} |")
    print("\nby genre, normal (bench + held-out): base → all")
    for g in ("fantasy", "horror", "joseon", "mystery", "postapoc", "scifi"):
        rs = [r for r in l1 if r["set"] == "normal" and r["key"][3:].startswith(g)]
        print(f"- {g}: {sum(plan_base(r) == r['gold'] for r in rs)} → {sum(plan_all(r) == r['gold'] for r in rs)} "
              f"/ {len(rs)}")
    print("\nchanged normal items:")
    for r in l1:
        if r["set"] == "normal" and plan_base(r) != plan_all(r):
            print(f"- {r['key'][3:]} gold {r['gold']} base {plan_base(r)} all {plan_all(r)}: {r['text']}")
    go = [r for r in rows if r["key"].startswith("go:")]
    print("\n## go: the current place offered (stay) vs not (base)\n")
    print("| set | n | base right | stay right | +/- | p |")
    print("|---|---|---|---|---|---|")
    for kind in ("normal", "cf"):
        rs = [r for r in go if r["set"] == kind]
        ra = [go_pick(r["base"], r["here"]) == r["gold"] for r in rs]
        rb = [go_pick(r["stay"], r["here"]) == r["gold"] for r in rs]
        up = sum(y and not x for x, y in zip(ra, rb))
        down = sum(x and not y for x, y in zip(ra, rb))
        print(f"| {kind} | {len(rs)} | {sum(ra)} | {sum(rb)} | +{up}/-{down} | {sign(up, down):.3g} |")
    for r in go:
        a, b = go_pick(r["base"], r["here"]), go_pick(r["stay"], r["here"])
        if a != b:
            print(f"- {r['key'][3:]} gold {r['gold']} base {a} stay {b}: {r['text']}")


if __name__ == "__main__":
    asyncio.run(record()) if sys.argv[1] == "record" else score()
