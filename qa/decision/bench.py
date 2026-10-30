import argparse
import asyncio
import json
import math
import sys
import time
from contextlib import contextmanager
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent
sys.path[:0] = [str(ROOT), str(ROOT.parent)]
import common
import mirror as M
import parity
from src.interpret import RELY_SHARE, SAY, STEP_THETA, THETA
from src.locale import ko
from src.models.decision import DECISION_MODELS, normalize
from src.narrate import THETA_N

# An experiment: the locale strings it replaces, by name.
EXPERIMENTS = {
    "plain_ask": {"SCHEMA_ASK": ko.SCHEMA_DESC},          # layer-1 options without their examples
}
# The engine's thresholds: a sure first step (interpret.STEP_THETA), a rewrite (narrate.THETA_N), all else THETA.
GATE = {"s1": STEP_THETA, "check": THETA_N}
COLUMNS = ("s1", "n", "intent", "target", "approach", "strain", "tone", "claim", "check")


def gold_intent(σ: str, d: dict) -> tuple:
    return {"go": lambda: (d["to"],), "look": lambda: (d["at"],), "take": lambda: (d["thing"],),
            "give": lambda: (d["thing"], d["to"]), "talk": lambda: (d["to"], d["topic"]),
            "declare": lambda: (d["latent"],), "cut": lambda: (d["kind"],),
            "choose": lambda: (d["fork"], d["option"])}[σ]()


def asks(it: dict) -> tuple[list[tuple[str, dict, dict]], dict]:
    """Each request the engine would send for the item as (state, questions, {question: (column, gold)}), and what
    layer 0 settles without a question: {slot: (got, gold)}."""
    if it["kind"] == "rely":
        r = M.rely(it)
        return ([(r[0], r[1], {"rely": ("rely", r[2])})] if r else []), {}
    if it["kind"] == "check":
        state, qs = M.check(it)
        return [(state, qs, {"0": ("check", None)})], {}
    s, text, g = M.Scene(it["scene"]), it["text"], it["gold"]
    σ, d = g["steps"][0], g["detail"]
    state, qs = M.layer1(text, s.have(), s.choices())
    out = [(state, qs, {"s1": ("s1", σ), "n": ("n", str(min(len(g["steps"]), 3)))})]
    a = M.layer2(s, text, σ)
    if a is None:
        return out, {}
    if σ == "try":
        want = {"target": (d["target"],), "approach": d["approach"], "strain": d["strain"]}
        gold = {"target": a.keys["target"].get(want["target"]), "approach": d["approach"], "strain": d["strain"]}
    else:
        want = {"intent": gold_intent(σ, d), "tone": d.get("tone")}
        gold = {"intent": a.keys["intent"].get(want["intent"]), "tone": d.get("tone")}
    settled = {k: (got, want[k]) for k, got in a.settled.items()}
    if a.request:
        st, q = a.request
        # an impossible attempt is refused whatever its approach, so that answer is not scored
        out.append((st, q, {k: (k, gold[k]) for k in q if not (k == "approach" and d.get("strain") == "impossible")}))
    if a.claims and d.get("tone") == "deceive":
        st, q = a.claims
        mine = a.keys["claim"].get(d.get("claim"))
        out.append((st, q, {k: ("claim", "true" if k == mine else "false") for k in q}))
    return out, settled


def flat(x) -> str:
    return ":".join(x) if isinstance(x, tuple) else x


@contextmanager
def patched(strings: dict):
    old = {k: getattr(ko, k) for k in strings}
    for k, v in strings.items():
        setattr(ko, k, v)
    try:
        yield
    finally:
        for k, v in old.items():
            setattr(ko, k, v)


async def decide(client, url, state, qs):
    t = time.perf_counter()
    r = await client.post(f"{url}/v1/systemone", json={"state": state, "model": "kev-latest", "questions": qs})
    r.raise_for_status()
    ms = (time.perf_counter() - t) * 1000
    return {k: dict(normalize(a, 0.5).probabilities) for k, a in r.json()["answers"].items()}, ms


def load(only=None):
    items = []
    for f in sorted((ROOT / "data").glob("*.jsonl")):
        if only and f.stem not in only:
            continue
        items += [json.loads(line) for line in f.read_text().splitlines() if line.strip()]
    return items


def blank(it):
    """The item with its sentence emptied: the model's prior over the same options in the same context."""
    it = dict(it)
    if it["kind"] == "sentence":
        it["text"] = ""
    elif it["kind"] == "rely":
        it["text"] = None
    else:
        it["sentence"] = ""
    return it


def answer_rows(it, n, column, q, gold, probs, ms, n_q):
    base = {"id": it["id"], "genre": it["genre"], "ms": ms, "n_q": n_q, "req": n}
    if column == "rely":
        asked = gold
        p = {f"r{i}": probs["rely"].get(f"r{k}", 0.0) for k, i in enumerate(asked)} if probs else {}
        kept = [i for i in range(len(it["options"])) if i not in asked]
        return [{**base, "family": "rely", "q": "rely", "gold": sorted(it["relevant"]), "probs": p, "kept": kept}]
    if column == "check":
        # each flaw is the share of its option; "bad" is anything but fine, which the engine rewrites
        p = probs["0"]
        return [{**base, "family": "check", "q": k, "gold": "true" if g else "false",
                 "probs": {"true": pk, "false": 1 - pk}}
                for k, pk, g in (("contradicts", p["contradicts"], it["contradicts"]),
                                 ("invents", p["invents"], it["invents"]),
                                 ("bad", 1 - p["fine"], it["contradicts"] or it["invents"]))]
    family = "step" if column in ("s1", "n") else column
    return [{**base, "family": family, "q": q, "gold": gold, "probs": probs[q]}]


async def run(model, variants, url, only, prior, out_dir):
    items = load(only)
    if prior:
        items = [blank(it) for it in items]
    base = {it["id"]: asks(it) for it in items}
    async with httpx.AsyncClient(timeout=120) as client:
        runs = [m.get("run", "") for m in (await client.get(f"{url}/v1/models")).json()["models"]]
        known = DECISION_MODELS.get(model)
        if known and not any(r.startswith(known.run) for r in runs):
            raise SystemExit(f"{model} is {known.run}, but the server runs {runs}")
        print(f"{model}: server runs {runs}; {len(items)} items")
        for v in variants:
            if v != "base" and v not in EXPERIMENTS:
                raise SystemExit(f"unknown variant {v}; base or one of {sorted(EXPERIMENTS)}")
            path = out_dir / "results" / model / f"{v}{'.prior' if prior else ''}.jsonl"
            if path.exists():
                raise SystemExit(f"{path} exists; record to another --run")
            with patched(EXPERIMENTS.get(v, {})):
                mine = {it["id"]: asks(it) for it in items}
            rows, t0 = [], time.time()
            for it in items:
                reqs, settled = mine[it["id"]]
                for n, (state, qs, golds) in enumerate(reqs):
                    was = base[it["id"]][0]
                    if v != "base" and n < len(was) and was[n][:2] == (state, qs):
                        continue        # an experiment records only what it changes
                    probs, ms = await decide(client, url, state, qs)
                    for q, (column, gold) in golds.items():
                        rows += answer_rows(it, n, column, q, gold, probs, ms, len(qs))
                if it["kind"] == "rely" and not reqs:
                    rows += answer_rows(it, 0, "rely", "rely", [], {}, 0.0, 0)
                if v == "base":
                    rows += [{"id": it["id"], "genre": it["genre"], "family": k, "q": k, "rule": flat(got),
                              "gold": flat(want)} for k, (got, want) in settled.items()]
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows))
            print(f"  {v}: {len(rows)} rows in {time.time() - t0:.0f}s → {path}")


# ---------------------------------------------------------------- scoring

def column(r) -> str | None:
    if "rule" in r:
        return None
    if r["family"] == "step":
        return r["q"]
    if r["family"] == "check":
        return "check" if r["q"] == "bad" else None
    return r["family"]


def top(r):
    return max(r["probs"], key=r["probs"].get)


def ok(r) -> bool:
    return top(r) == r["gold"]


def metrics(rows, gate=THETA):
    if not rows:
        return None
    n = len(rows)
    sure = [r for r in rows if max(r["probs"].values()) >= gate]
    return {"n": n, "acc": sum(map(ok, rows)) / n, "sure": len(sure) / n,
            "sure_acc": sum(map(ok, sure)) / max(1, len(sure))}


def rely_metrics(rows, share=RELY_SHARE, asked_only=False):
    """The roll card's reliances against the labels; `asked_only` leaves out what the engine keeps unasked (edges), so
    it scores the model alone."""
    exact = hit = kept_n = gold_n = 0
    for r in rows:
        unasked = set(r.get("kept", []))
        if r.get("per_option"):          # decision-1's yes/no variant
            kept = {int(k[1:]) for k, p in r["probs"].items() if p >= 0.5}
        else:
            kept = {int(k[1:]) for k, p in r["probs"].items() if p >= share} | (set() if asked_only else unasked)
        gold = set(r["gold"]) - (unasked if asked_only else set())
        exact += kept == gold
        hit += len(kept & gold)
        kept_n += len(kept)
        gold_n += len(gold)
    return {"n": len(rows), "exact": exact / len(rows), "precision": hit / max(1, kept_n),
            "recall": hit / max(1, gold_n)}


def read(path: Path) -> list[dict]:
    return [json.loads(x) for x in path.read_text().splitlines()] if path.exists() else []


def sign(b, c):
    """Exact two-sided sign test on discordant pairs."""
    n, k = b + c, min(b, c)
    return 1.0 if n == 0 else min(1.0, 2 * sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n)


def score(run_dir, models, by, against):
    res = run_dir / "results"
    models = models or sorted(p.name for p in res.iterdir() if p.is_dir())
    for m in models:
        print(f"\n## {m} ({run_dir.name})")
        print("| variant | " + " | ".join(COLUMNS[:1]) + f" | s1 sure ≥{STEP_THETA} (acc) | " + " | ".join(COLUMNS[1:])
              + " | rely exact (P/R) | ms/call |")
        print("|---|" + "---|" * (len(COLUMNS) + 3))
        for f in sorted((res / m).glob("*.jsonl"), key=lambda p: (p.stem != "base", p.stem)):
            if "." in f.stem:           # `.prior` runs
                continue
            rows = read(f)
            cells = []
            for c in COLUMNS:
                mm = metrics([r for r in rows if column(r) == c], GATE.get(c, THETA))
                cells.append(f"{mm['acc']:.3f} ({mm['n']})" if mm else "·")
                if c == "s1":
                    cells.append(f"{mm['sure']:.2f} ({mm['sure_acc']:.3f})" if mm else "·")
            rr = [r for r in rows if r["family"] == "rely"]
            rely, alone = (rely_metrics(rr), rely_metrics(rr, asked_only=True)) if rr else (None, None)
            rc = f"{rely['exact']:.3f} ({rely['precision']:.2f}/{rely['recall']:.2f}), asked {alone['exact']:.3f}" \
                if rely else "·"
            calls = {(r["id"], r.get("req", r["family"] == "step")): r["ms"] for r in rows if r.get("ms")}
            ms = sum(calls.values()) / max(1, len(calls))
            print(f"| {f.stem} | " + " | ".join(cells) + f" | {rc} | {ms:.0f} |")
            rules = [r for r in rows if "rule" in r]
            if rules:
                print("  settled without the decision model: " + ", ".join(
                    f"{k} {sum(r['rule'] == r['gold'] for r in rules if r['q'] == k)}/"
                    f"{sum(r['q'] == k for r in rules)} right" for k in sorted({r["q"] for r in rules})))
        if by:
            base = read(res / m / "base.jsonl")
            print(f"\n{m} base by genre (s1 / check):")
            for g in sorted({r["genre"] for r in base}):
                s = metrics([r for r in base if r["genre"] == g and column(r) == "s1"])
                c = metrics([r for r in base if r["genre"] == g and column(r) == "check"])
                print(f"  {g}: s1 {s['acc']:.3f} ({s['n']})" + (f"  check {c['acc']:.3f}" if c else ""))
        if against:
            compare(read(res / m / "base.jsonl"), against, m)


def compare(rows, against: Path, model: str):
    """Paired by item and question: this run's base against another run's."""
    other = {}
    for d in [against / "results" / model, *sorted((against / "results").glob(f"{model}*"))]:
        if (d / "base.jsonl").exists():
            other = {(r["id"], r["q"]): r for r in read(d / "base.jsonl")}
            break
    if not other:
        print(f"\n(no base for {model} under {against})")
        return
    print(f"\n{model}: this base vs {against.name} base, paired on the questions both asked\n")
    print("| question | pairs | this | that | +/− | p | only here | only there |")
    print("|---|---|---|---|---|---|---|---|")
    mine = {(r["id"], r["q"]): r for r in rows if column(r)}
    theirs = {k: r for k, r in other.items() if "probs" in r and r["family"] != "rely"}
    for c in COLUMNS:
        here = {k for k, r in mine.items() if column(r) == c}
        there = {k for k, r in theirs.items() if (r["q"] if r["family"] in ("step", "check") else r["family"]) == c}
        both = sorted(here & there)
        if not both and not here:
            continue
        up = sum(ok(mine[k]) and not ok(theirs[k]) for k in both)
        down = sum(ok(theirs[k]) and not ok(mine[k]) for k in both)
        a = sum(ok(mine[k]) for k in both) / max(1, len(both))
        b = sum(ok(theirs[k]) for k in both) / max(1, len(both))
        print(f"| {c} | {len(both)} | {a:.3f} | {b:.3f} | +{up}/−{down} | {sign(up, down):.3g} | {len(here - there)} | "
              f"{len(there - here)} |")


def validate(only):
    bad = 0
    for it in load(only):
        if it["kind"] != "sentence":
            continue
        s, g, text = M.Scene(it["scene"]), it["gold"], it["text"]
        σ, d = g["steps"][0], g["detail"]
        probs = [f"unknown step {st}" for st in g["steps"] if st not in SAY]
        if σ not in s.have():
            probs.append(f"first step {σ} not possible here")
        else:
            key = (d.get("target"),) if σ == "try" else gold_intent(σ, d)
            if key not in s.slots(σ):
                probs.append(f"{key} not among {s.slots(σ)}")
            else:
                a = M.layer2(s, text, σ)
                keys = a.keys["target" if σ == "try" else "intent"]
                if key not in keys and key not in a.settled.values():
                    probs.append(f"{key} named away: the engine offers {list(keys)}")
        if probs:
            bad += 1
            print(it["id"], "|", text, "|", "; ".join(probs))
    print("problems:", bad)


def main():
    # common.py reads these from argv; they are declared so argparse accepts them
    shared = argparse.ArgumentParser(add_help=False)
    shared.add_argument("--root", help="another checkout's server and stories")
    shared.add_argument("--story", help="the story whose eval states parity checks against")
    ap = argparse.ArgumentParser(formatter_class=argparse.RawDescriptionHelpFormatter, description="""\
Decision-model bench: the engine's closed questions over story-agnostic genre items.

  python bench.py run MODEL --run RUN [--variants base,EXPERIMENT] [--url URL] [--only fantasy,...] [--prior]
  python bench.py score --run RUN [--against OTHER_RUN] [--models a,b] [--by]
  python bench.py validate [--only fantasy,...]
  python bench.py parity

`base` sends, for each item, what the engine would send (mirror.py builds it with interpret.py and locale/ko.py), and
`run` first checks that against the engine itself on the story's eval states (parity.py). An experiment replaces
locale strings on purpose and records only the requests that change. Recordings: qa_test/runs/RUN/results/MODEL/.
""")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run", parents=[shared])
    r.add_argument("model")
    r.add_argument("--run", required=True, help="recording name under qa_test/runs/")
    r.add_argument("--variants", default="base")
    r.add_argument("--url", default="http://127.0.0.1:8081")
    r.add_argument("--only", default="")
    r.add_argument("--prior", action="store_true")
    v = sub.add_parser("validate", parents=[shared])
    v.add_argument("--only", default="")
    s = sub.add_parser("score", parents=[shared])
    s.add_argument("--run", required=True)
    s.add_argument("--against", help="another recording to pair base answers with")
    s.add_argument("--models", default="")
    s.add_argument("--by", action="store_true")
    sub.add_parser("parity", parents=[shared])
    a = ap.parse_args()
    if a.cmd == "validate":
        validate(set(filter(None, a.only.split(","))))
    elif a.cmd == "parity":
        parity.check()
    elif a.cmd == "run":
        parity.check()
        asyncio.run(run(a.model, a.variants.split(","), a.url, set(filter(None, a.only.split(","))), a.prior,
                        common.RUNS / a.run))
    else:
        score(common.RUNS / a.run, list(filter(None, a.models.split(","))), a.by,
              common.RUNS / a.against if a.against else None)


if __name__ == "__main__":
    main()
