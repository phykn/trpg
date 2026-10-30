import argparse
import asyncio
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
D1 = ROOT.parent / "decision"
sys.path[:0] = [str(D1), str(ROOT.parent)]
import common
import mirror as M
import parity
from src.interpret import SAY, STEP_THETA, THETA, Interpreter, ranked

GENRES = ("fantasy", "horror", "joseon", "mystery", "postapoc", "scifi")
REPLACEABLE = {"go", "take", "give", "talk", "declare", "choose"}   # look, try and cut are always possible


def bench_items():
    return [json.loads(x) for f in sorted((D1 / "data").glob("*.jsonl")) for x in f.read_text().splitlines()
            if x.strip()]


def scenes():
    out = {}
    for g in GENRES:
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
            "detail": r["gold"]["detail"]} for r in bench_items() if r["kind"] == "sentence"]
    sc = scenes()
    for h in map(json.loads, (D1 / "heldout" / "plan.jsonl").read_text().splitlines()):
        out.append({"id": h["id"], "scene": sc[(h["genre"], h["scene"])], "text": h["text"], "steps": h["steps"],
                    "detail": None})
    return out


def layer1_requests():
    """(key, scene, text, have, gold plan, set)."""
    for it in items():
        have = M.Scene(it["scene"]).have()
        yield it["id"], it["scene"], it["text"], have, it["steps"][:3], "normal"
        if it["steps"][0] in REPLACEABLE:
            yield it["id"] + "~cf", it["scene"], it["text"], have - {it["steps"][0]}, it["steps"][:1], "cf"


def go_requests():
    """(key, scene, text, gold destination, set); the gold of a cf item is the place the player is in."""
    for it in items():
        if it["steps"][0] != "go" or not it["detail"]:
            continue
        sc, to = it["scene"], it["detail"]["to"]
        yield it["id"], sc, it["text"], to, "normal"
        here = sc["place"]["name"]
        moved = {**sc, "place": {**sc["place"], "name": to}, "exits": [e for e in sc["exits"] if e != to] + [here]}
        yield it["id"] + "~cf", moved, it["text"], to, "cf"


def layer1(sc, text, have):
    """The engine's first request; with choose removed, no fork is open and its choices are not named."""
    return M.layer1(text, have, M.Scene(sc).choices() if "choose" in have else [])


async def record(out: Path):
    kev, llm = common.models()
    it = Interpreter(kev, llm, timeout=60)
    done = {json.loads(x)["key"] for x in out.read_text().splitlines()} if out.exists() else set()
    out.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with out.open("a") as f:
        for key, sc, text, have, gold, kind in layer1_requests():
            k = f"l1:{key}"
            if k in done:
                continue
            state, qs = layer1(sc, text, have)
            a = await kev.decide(state, qs)
            row = {"key": k, "set": kind, "text": text, "have": [σ for σ in SAY if σ in have], "gold": gold,
                   "kev": {q: dict(v.probabilities) for q, v in a.items()},
                   "read": await it.read(text, qs["s1"]["criteria"])}
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
            f.flush()
            n += 1
            if n % 50 == 0:
                print("l1", n, flush=True)
        for key, sc, text, to, kind in go_requests():
            k = f"go:{key}"
            if k in done:
                continue
            a = M.layer2(M.Scene(sc), text, "go")
            names = {v: i[0] for i, v in a.keys["intent"].items()}
            row = {"key": k, "set": kind, "text": text, "gold": to, "here": sc["place"]["name"], "names": names,
                   "narrowed": list(names)}
            if a.request:
                state, qs = a.request
                row["kev"] = dict((await kev.decide(state, qs))["intent"].probabilities)
                row["pick"] = await it.pick(state, qs["intent"]["instructions"], qs["intent"]["criteria"])
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
            f.flush()
    print("done", flush=True)


def l1_answers(r):
    """misread-1 recorded the engine's request under "all" (and the one before it under "base")."""
    return r.get("kev") or r["all"]


def go_answers(r):
    return r if "names" in r else r["stay"]


def plan(r, theta=STEP_THETA):
    a = l1_answers(r)
    return M.plan(a["s1"], a["n"], r["read"], set(r["have"]), theta)


def go_pick(got, here):
    """interpret.fill for go: the decision model's sure answer, except that staying needs the narration model's pick."""
    keys = got["narrowed"]
    if len(keys) == 1:
        return got["names"][keys[0]]
    top, pr = ranked(M.Probs(got["kev"]), keys)[0]
    w = top if pr >= THETA and got["names"][top] != here else got.get("pick")
    return got["names"][w] if w else None


def sign(b, c):
    n, k = b + c, min(b, c)
    return 1.0 if n == 0 else min(1.0, 2 * sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n)


def outcome(p, have):
    return "idle" if p == ["idle"] else "refused" if p[0] not in have else "acted"


def right(p, r):
    return p[:len(r["gold"])] == r["gold"] if r["set"] == "cf" else p == r["gold"]


SETS = (("normal bench", lambda r: r["set"] == "normal" and "-s" in r["key"]),
        ("normal held-out", lambda r: r["set"] == "normal" and "-h" in r["key"]),
        ("cf bench", lambda r: r["set"] == "cf" and "-s" in r["key"]),
        ("cf held-out", lambda r: r["set"] == "cf" and "-h" in r["key"]))


def score(path: Path, against: Path | None, theta: float):
    rows = [json.loads(x) for x in path.read_text().splitlines()]
    other = {r["key"]: r for r in map(json.loads, against.read_text().splitlines())} if against else {}
    l1 = [r for r in rows if r["key"].startswith("l1:")]
    print(f"## layer 1 as interpret.plan takes it (θ₁ {theta}): right, and what the turn did\n")
    print("| set | n | right | idle/refused/acted |" + (" there | +/− | p |" if other else ""))
    print("|---|---|---|---|" + ("---|---|---|" if other else ""))
    for kind, part in SETS:
        rs = [r for r in l1 if part(r)]
        a = [right(plan(r, theta), r) for r in rs]
        outs = [outcome(plan(r, theta), set(r["have"])) for r in rs]
        line = f"| {kind} | {len(rs)} | {sum(a)} | " + "/".join(str(outs.count(k)) for k in ("idle", "refused", "acted"))
        if other:
            pairs = [(x, right(plan(other[r["key"]], theta), other[r["key"]])) for x, r in zip(a, rs) if r["key"] in other]
            up = sum(x and not y for x, y in pairs)
            down = sum(y and not x for x, y in pairs)
            line += f" | {sum(y for _, y in pairs)}/{len(pairs)} | +{up}/−{down} | {sign(up, down):.3g}"
        print(line + " |")
    print("\nby genre, normal (bench + held-out):")
    for g in GENRES:
        rs = [r for r in l1 if r["set"] == "normal" and r["key"][3:].startswith(g)]
        print(f"- {g}: {sum(right(plan(r, theta), r) for r in rs)} / {len(rs)}")
    print("\nnormal sentences read wrong:")
    for r in l1:
        p = plan(r, theta)
        if r["set"] == "normal" and not right(p, r):
            print(f"- {r['key'][3:]} gold {r['gold']} got {p}: {r['text']}")
    go = [r for r in rows if r["key"].startswith("go:")]
    print("\n## go, the current place offered when no way out is named\n")
    print("| set | n | right |" + (" there | +/− | p |" if other else ""))
    print("|---|---|---|" + ("---|---|---|" if other else ""))
    for kind in ("normal", "cf"):
        rs = [r for r in go if r["set"] == kind]
        a = [go_pick(go_answers(r), r["here"]) == r["gold"] for r in rs]
        line = f"| {kind} | {len(rs)} | {sum(a)} |"
        if other:
            pairs = [(x, go_pick(go_answers(other[r["key"]]), r["here"]) == r["gold"]) for x, r in zip(a, rs)
                     if r["key"] in other]
            up = sum(x and not y for x, y in pairs)
            down = sum(y and not x for x, y in pairs)
            line += f" {sum(y for _, y in pairs)}/{len(pairs)} | +{up}/−{down} | {sign(up, down):.3g} |"
        print(line)
    for r in go:
        got = go_pick(go_answers(r), r["here"])
        if got != r["gold"]:
            print(f"- {r['key'][3:]} gold {r['gold']} got {got}: {r['text']}")


def main():
    ap = argparse.ArgumentParser(formatter_class=argparse.RawDescriptionHelpFormatter, description="""\
Layer 1 and go as the engine asks them, on sentences whose answer the scene may not offer.

  python bench.py record --run RUN                  # both models on every request; resumes RUN/answers.jsonl
  python bench.py score --run RUN [--against RUN2]  # the engine's plan, and paired with another recording

Items: decision-1's 216 bench sentences and 120 held-out ones, as they are ("normal"), and the same sentences with
the asked thing made impossible ("cf"): layer 1 with the first step's schema removed from the scene, go with the
player already standing at the destination. Nothing here is written for this test. The requests come from
qa/decision/mirror.py, checked against the engine first (parity.py), and plans follow interpret.plan at STEP_THETA.
""")
    ap.add_argument("cmd", choices=("record", "score"))
    ap.add_argument("--run", required=True, help="recording name under qa_test/runs/")
    ap.add_argument("--against", help="another recording to pair with (misread-1 works)")
    ap.add_argument("--theta", type=float, default=STEP_THETA, help="the first step's threshold, to try another")
    ap.add_argument("--root")
    a = ap.parse_args()
    out = common.RUNS / a.run / "answers.jsonl"
    if a.cmd == "record":
        parity.check()
        asyncio.run(record(out))
    else:
        score(out, common.RUNS / a.against / "answers.jsonl" if a.against else None, a.theta)


if __name__ == "__main__":
    main()
