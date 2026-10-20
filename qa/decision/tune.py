"""Offline search over prediction methods on recorded answers: contextual calibration, phrasing ensembles, thresholds."""
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))
import analyze as A  # noqa: E402

L2 = ("intent", "target", "approach", "strain", "tone", "claim")


def load(mm, v, prior=False):
    f = Path(__file__).resolve().parents[2] / "qa_test" / "runs" / "decision-1" / "results" / mm / f"{v}{'.prior' if prior else ''}.jsonl"
    if not f.exists():
        return {}
    return {A.key(r): r for r in map(json.loads, f.read_text().splitlines())}


def full(r):
    """Probabilities over every option, rebuilding the shares the recorder folded away."""
    p = dict(r["probs"])
    if r["family"] == "rely":
        p["none"] = max(0.0, 1 - sum(p.values()))
    return p


def norm(p):
    z = sum(p.values()) or 1.0
    return {k: v / z for k, v in p.items()}


def calibrate(rows, prior, alpha=1.0, eps=0.02):
    out = {}
    for k, r in rows.items():
        q = prior.get(k)
        if q is None or r["family"] == "check":
            out[k] = r
            continue
        p, p0 = full(r), full(q)
        c = norm({o: p[o] / (p0.get(o, 0.0) + eps) ** alpha for o in p})
        if r["family"] == "rely":
            c.pop("none", None)
        out[k] = {**r, "probs": c}
    return out


def ensemble(*sets, w=None):
    w = w or [1.0] * len(sets)
    out = {}
    for k, r in sets[0].items():
        ps = [(s[k], wi) for s, wi in zip(sets, w) if k in s and set(s[k]["probs"]) == set(r["probs"])]
        tot = sum(wi for _, wi in ps)
        out[k] = {**r, "probs": {o: sum(x["probs"][o] * wi for x, wi in ps) / tot for o in r["probs"]}}
    return out


def compose(base, **by_family):
    """by_family: family name ('step', 'intent', …) -> rows; the rest from base."""
    out = dict(base)
    for fam, rows in by_family.items():
        for k, r in rows.items():
            if r["family"] == fam:
                out[k] = r
    return out


def check_choice_rows(rows, prior=None, alpha=1.0, eps=0.02, theta=0.5):
    """Rewrite decision from a recorded 3-way check (fine / contradicts / invents), optionally calibrated."""
    by = defaultdict(dict)
    for (i, q), r in rows.items():
        by[i][q] = r
    pri = defaultdict(dict)
    for (i, q), r in (prior or {}).items():
        pri[i][q] = r
    res = []
    for i, qs in by.items():
        p = {"fine": 1 - qs["bad"]["probs"]["true"], "contradicts": qs["contradicts"]["probs"]["true"],
             "invents": qs["invents"]["probs"]["true"]}
        if prior:
            q0 = pri[i]
            p0 = {"fine": 1 - q0["bad"]["probs"]["true"], "contradicts": q0["contradicts"]["probs"]["true"],
                  "invents": q0["invents"]["probs"]["true"]}
            p = norm({o: p[o] / (p0[o] + eps) ** alpha for o in p})
        res.append((qs["bad"]["gold"] == "true", p["fine"] <= 1 - theta))
    return res


def flags_summary(f):
    bad = [p for g, p in f if g]
    fine = [p for g, p in f if not g]
    return f"acc {sum(g == p for g, p in f) / len(f):.3f} caught {sum(bad)}/{len(bad)} false {sum(fine)}/{len(fine)}"


def summary(rows, theta=None):
    if theta is not None:
        A.THETA = theta
    e = A.engine(rows.values())
    n = len(e)
    av = {k: sum(x[k] for x in e.values()) / n for k in ("plan", "slots", "clarify", "turn", "unsure_s1")}
    fams = {f: A.m([r for r in rows.values() if A.fam(r) == f]) for f in ("s1",) + L2[:-1]}
    A.THETA = 0.5
    cells = " ".join(f"{f} {m['acc']:.2f}" for f, m in fams.items() if m)
    return (f"turn {av['turn']:.3f} plan {av['plan']:.3f} l2 {av['slots']:.3f} clar {av['clarify']:.3f} "
            f"unsure {av['unsure_s1']:.3f} | {cells}")


def per_genre(rows):
    e = A.engine(rows.values())
    g = defaultdict(list)
    for i, x in e.items():
        g[i.split("-")[0]].append(x["turn"])
    return " ".join(f"{k} {sum(v) / len(v):.2f}" for k, v in sorted(g.items()))


def outcomes(rows, theta=0.5):
    """right / asked (second opinion or clarify card) / wrong (an action the player did not mean)."""
    A.THETA = theta
    e = A.engine(rows.values())
    A.THETA = 0.5
    c = {"right": 0, "asked": 0, "wrong": 0}
    for x in e.values():
        if x["turn"]:
            c["right"] += 1
        elif x["unsure_s1"] or (x["plan"] and x["clarify"]):
            c["asked"] += 1
        else:
            c["wrong"] += 1
    n = len(e)
    return f"right {c['right'] / n:.3f} asked {c['asked'] / n:.3f} wrong {c['wrong'] / n:.3f}"
