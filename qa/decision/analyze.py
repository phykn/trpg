import argparse
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bench as B
import mirror as M
from src.interpret import STEP_THETA, THETA
from src.narrate import THETA_N

LAYER2 = ("intent", "target", "approach", "strain", "tone", "claim")


def gate(c):
    return B.GATE.get(c, THETA)


def table_base(data):
    print("## base: accuracy / share at the engine's gate / accuracy there\n")
    print("| question | gate | " + " | ".join(data) + " |")
    print("|---|---|" + "---|" * len(data))
    for c in B.COLUMNS:
        cells = []
        for rs in data.values():
            x = B.metrics([r for r in rs if B.column(r) == c], gate(c))
            cells.append(f"{x['acc']:.3f} / {x['sure']:.2f} / {x['sure_acc']:.3f} (n{x['n']})" if x else "-")
        print(f"| {c} | {gate(c)} | " + " | ".join(cells) + " |")
    cells = []
    for rs in data.values():
        ms = list({(r["id"], r.get("req")): r["ms"] for r in rs if r.get("ms")}.values())
        cells.append(f"median {statistics.median(ms):.0f} / p90 {sorted(ms)[int(len(ms) * .9)]:.0f}" if ms else "-")
    print("| ms per call | | " + " | ".join(cells) + " |")


def table_genre(data):
    print("\n## base by genre: s1 / layer 2 / check accuracy\n")
    genres = sorted({r["genre"] for rs in data.values() for r in rs})
    print("| genre | " + " | ".join(data) + " |")
    print("|---|" + "---|" * len(data))
    for g in genres:
        cells = []
        for rs in data.values():
            part = [r for r in rs if r["genre"] == g]
            xs = [B.metrics([r for r in part if B.column(r) in cols]) for cols in (("s1",), LAYER2, ("check",))]
            cells.append(" / ".join(f"{x['acc']:.2f}" if x else "-" for x in xs))
        print(f"| {g} | " + " | ".join(cells) + " |")


def table_experiments(run, models):
    for m in models:
        base = {(r["id"], r["q"]): r for r in B.read(run / "results" / m / "base.jsonl") if B.column(r)}
        for f in sorted((run / "results" / m).glob("*.jsonl")):
            if f.stem == "base" or "." in f.stem:
                continue
            print(f"\n## {m} · {f.stem} minus base (paired; p = exact sign test)\n")
            print("| question | pairs | base | variant | +/− | p |")
            print("|---|---|---|---|---|---|")
            rs = [r for r in B.read(f) if B.column(r) and (r["id"], r["q"]) in base]
            for c in B.COLUMNS:
                vr = [r for r in rs if B.column(r) == c]
                if not vr:
                    continue
                br = [base[(r["id"], r["q"])] for r in vr]
                up = sum(B.ok(x) and not B.ok(y) for x, y in zip(vr, br))
                down = sum(B.ok(y) and not B.ok(x) for x, y in zip(vr, br))
                print(f"| {c} | {len(vr)} | {sum(map(B.ok, br)) / len(br):.3f} | {sum(map(B.ok, vr)) / len(vr):.3f} | "
                      f"+{up}/−{down} | {B.sign(up, down):.3g} |")


def confusions(data):
    for m, rs in data.items():
        cnt = Counter((r["gold"], B.top(r)) for r in rs if B.column(r) == "s1" and not B.ok(r))
        print(f"\n## {m}: s1 confusions (gold → picked)\n")
        print(", ".join(f"{g}→{p} {n}" for (g, p), n in cnt.most_common()))


def rely_shares(data):
    print("\n## rely exact by share cut: the card / the asked options alone\n")
    for m, rs in data.items():
        rr = [r for r in rs if r["family"] == "rely"]
        if rr:
            print(m, " ".join(f"{s}: {B.rely_metrics(rr, s)['exact']:.2f}/{B.rely_metrics(rr, s, True)['exact']:.2f}"
                              for s in (0.05, 0.1, 0.15, 0.2, 0.3)))


def turns(rs, items):
    """Each sentence as the engine takes it with the decision model's answers alone: right, wrong, or handed to the
    narration model (a first step not sure at STEP_THETA or counted as several, an unsure intent, a target or an
    approach, which the narration model picks first)."""
    by = defaultdict(dict)
    for r in rs:
        if r["family"] not in ("rely", "check"):
            by[r["id"]][r["q"]] = r
    out = {}
    for i, qs in by.items():
        it = items[i]
        s, text, gold = M.Scene(it["scene"]), it["text"], it["gold"]["steps"]
        top, p = B.top(qs["s1"]), max(qs["s1"]["probs"].values())
        if not (p >= STEP_THETA and top in s.have() and B.top(qs["n"]) == "1"):
            out[i] = "reader"
            continue
        if [top] != gold:
            out[i] = "wrong"
            continue
        a = M.layer2(s, text, top)
        verdict = "right"
        for k in ("intent", "target", "approach", "strain", "tone"):
            r = qs.get(k)
            if r is None:
                continue
            if "rule" in r:
                verdict = verdict if r["rule"] == r["gold"] else "wrong"
                continue
            t, pk = B.top(r), max(r["probs"].values())
            if k == "intent" and (pk < THETA or top == "go" and t == a.keys["intent"].get((s.here,))) \
                    or k in ("target", "approach"):
                verdict = "reader" if verdict == "right" else verdict
                continue
            pick = t if k == "intent" or pk >= THETA else {"strain": "natural", "tone": "polite"}[k]
            if pick != r["gold"]:
                verdict = "wrong"
        claims = [r for r in qs.values() if r["family"] == "claim"]
        if claims:
            yes = max(claims, key=lambda r: r["probs"]["true"])
            said = yes["q"] if yes["probs"]["true"] >= THETA else None
            verdict = verdict if said == next((r["q"] for r in claims if r["gold"] == "true"), None) else "wrong"
        out[i] = verdict
    return out


def table_turns(data, items):
    print("\n## as the engine takes each sentence, the decision model alone\n")
    print("| model | right | wrong | to the narration model |")
    print("|---|---|---|---|")
    for m, rs in data.items():
        c = Counter(turns(rs, items).values())
        n = sum(c.values())
        print(f"| {m} | {c['right'] / n:.3f} | {c['wrong'] / n:.3f} | {c['reader'] / n:.3f} |")


def calibration(data):
    print(f"\n## s1 by threshold (the engine's is {STEP_THETA}): share sure / accuracy there\n")
    cuts = (0.5, 0.6, 0.7, 0.8, 0.9)
    print("| model | " + " | ".join(f"θ {t}" for t in cuts) + " |")
    print("|---|" + "---|" * len(cuts))
    for m, rs in data.items():
        s1 = [r for r in rs if B.column(r) == "s1"]
        cells = []
        for t in cuts:
            x = B.metrics(s1, t)
            cells.append(f"{x['sure']:.2f} / {x['sure_acc']:.3f}")
        print(f"| {m} | " + " | ".join(cells) + " |")


def table_check(data):
    print(f"\n## narration check as a rewrite (bad = contradicts or invents; rewritten when fine ≤ 1 − {THETA_N})\n")
    print("| model | acc | caught bad | flagged fine |")
    print("|---|---|---|---|")
    for m, rs in data.items():
        bad = [r for r in rs if r["family"] == "check" and r["q"] == "bad"]
        if not bad:
            continue
        flagged = [(r["gold"] == "true", r["probs"]["true"] >= THETA_N) for r in bad]
        caught = sum(f for g, f in flagged if g)
        wrong = sum(f for g, f in flagged if not g)
        print(f"| {m} | {sum(g == f for g, f in flagged) / len(flagged):.3f} | {caught}/{sum(g for g, _ in flagged)} | "
              f"{wrong}/{sum(not g for g, _ in flagged)} |")


def main():
    ap = argparse.ArgumentParser(description="Tables from a decision bench recording; no model calls.")
    ap.add_argument("--run", required=True)
    ap.add_argument("--models", default="")
    ap.add_argument("--root")
    a = ap.parse_args()
    run = B.common.RUNS / a.run
    models = list(filter(None, a.models.split(","))) or sorted(p.name for p in (run / "results").iterdir() if p.is_dir())
    data = {m: B.read(run / "results" / m / "base.jsonl") for m in models}
    items = {it["id"]: it for it in B.load()}
    table_base(data)
    table_genre(data)
    table_experiments(run, models)
    confusions(data)
    rely_shares(data)
    table_turns(data, items)
    calibration(data)
    table_check(data)


if __name__ == "__main__":
    main()
