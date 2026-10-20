import json
import math
import statistics
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))
from bench import RELY_SHARE, RUNS, THETA, VARIANTS, rely_metrics  # noqa: E402
from src.interpret import approach_cue  # noqa: E402

FAMS = ("s1", "s2", "s3", "intent", "target", "approach", "strain", "tone", "claim", "contradicts", "invents")


def rows(model, variant):
    f = RUNS / "results" / model / f"{variant}.jsonl"
    return [json.loads(x) for x in f.read_text().splitlines()] if f.exists() else []


def fam(r):
    return r["q"] if r["family"] in ("step", "check") else r["family"]


def top(r):
    return max(r["probs"], key=r["probs"].get)


def ok(r):
    return top(r) == r["gold"]


def m(rs):
    if not rs:
        return None
    n = len(rs)
    acc = sum(map(ok, rs)) / n
    kept = [r for r in rs if max(r["probs"].values()) >= THETA]
    err = sum(not ok(r) for r in kept) / max(1, len(kept))
    return {"n": n, "acc": acc, "cover": len(kept) / n, "err": err}


def mcnemar(b, c):
    """Exact two-sided sign test on discordant pairs."""
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    p = sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n
    return min(1.0, 2 * p)


def key(r):
    return (r["id"], r["q"])


def models():
    return sorted(p.name for p in (RUNS / "results").iterdir() if p.is_dir())


def calls_ms(rs):
    seen = {}
    for r in rs:
        seen[(r["id"], r["family"] == "step", r["family"])] = r["ms"]
    return list(seen.values())


def table_base():
    print("## base: accuracy / coverage at θ / error among accepted\n")
    print("| family | " + " | ".join(models()) + " |")
    print("|---|" + "---|" * len(models()))
    data = {mm: rows(mm, "base") for mm in models()}
    for f in FAMS:
        cells = []
        for mm in models():
            x = m([r for r in data[mm] if fam(r) == f])
            cells.append(f"{x['acc']:.3f} / {x['cover']:.2f} / {x['err']:.3f} (n{x['n']})" if x else "-")
        print(f"| {f} | " + " | ".join(cells) + " |")
    cells = []
    for mm in models():
        rr = [r for r in data[mm] if r["family"] == "rely"]
        x = rely_metrics(rr) if rr else None
        cells.append(f"exact {x['exact']:.3f} P {x['precision']:.2f} R {x['recall']:.2f}" if x else "-")
    print("| rely | " + " | ".join(cells) + " |")
    # every question about one sentence right: what a turn needs
    cells = []
    for mm in models():
        by = defaultdict(list)
        for r in data[mm]:
            if r["family"] not in ("rely", "check"):
                by[r["id"]].append(ok(r))
        cells.append(f"{sum(all(v) for v in by.values()) / max(1, len(by)):.3f} (n{len(by)})")
    print("| whole sentence | " + " | ".join(cells) + " |")
    cells = []
    for mm in models():
        ms = calls_ms(data[mm])
        cells.append(f"median {statistics.median(ms):.0f} / p90 {sorted(ms)[int(len(ms) * .9)]:.0f}" if ms else "-")
    print("| ms per call | " + " | ".join(cells) + " |")


def table_genre():
    print("\n## base by genre: s1 / layer-2 / check accuracy\n")
    genres = sorted({r["genre"] for mm in models() for r in rows(mm, "base")})
    print("| genre | " + " | ".join(models()) + " |")
    print("|---|" + "---|" * len(models()))
    for g in genres:
        cells = []
        for mm in models():
            rs = [r for r in rows(mm, "base") if r["genre"] == g]
            s1 = m([r for r in rs if fam(r) == "s1"])
            l2 = m([r for r in rs if fam(r) in ("intent", "target", "approach", "strain", "tone", "claim")])
            ck = m([r for r in rs if r["family"] == "check"])
            cells.append(" / ".join(f"{x['acc']:.2f}" if x else "-" for x in (s1, l2, ck)))
        print(f"| {g} | " + " | ".join(cells) + " |")


def table_variants():
    for mm in models():
        base = {key(r): r for r in rows(mm, "base")}
        print(f"\n## {mm}: variant minus base (paired; p = exact sign test)\n")
        print("| variant | family | base | variant | Δ | +/− | p |")
        print("|---|---|---|---|---|---|---|")
        for v, changed in VARIANTS.items():
            if v == "base":
                continue
            rs = rows(mm, v)
            if not rs:
                continue
            for f in FAMS:
                vr = [r for r in rs if fam(r) == f and key(r) in base]
                if not vr or (changed is not None and r_family(f) not in changed):
                    continue
                br = [base[key(r)] for r in vr]
                b = sum(ok(x) and not ok(y) for x, y in zip(vr, br))
                c = sum(ok(y) and not ok(x) for x, y in zip(vr, br))
                a0, a1 = sum(map(ok, br)) / len(br), sum(map(ok, vr)) / len(vr)
                mark = " **" if mcnemar(b, c) < 0.05 else ""
                print(f"| {v} | {f} | {a0:.3f} | {a1:.3f} | {a1 - a0:+.3f}{mark} | +{b}/−{c} | {mcnemar(b, c):.3f} |")
            if changed is None or "rely" in changed:
                rr = [r for r in rs if r["family"] == "rely"]
                if rr:
                    x, y = rely_metrics(rr), rely_metrics([r for r in rows(mm, "base") if r["family"] == "rely"])
                    print(f"| {v} | rely exact | {y['exact']:.3f} | {x['exact']:.3f} | {x['exact'] - y['exact']:+.3f} "
                          f"| P {x['precision']:.2f} R {x['recall']:.2f} | |")
            ms = calls_ms(rs)
            if ms:
                print(f"| {v} | ms median | | {statistics.median(ms):.0f} | | | |")


def r_family(f):
    return "step" if f in ("s1", "s2", "s3") else "check" if f in ("contradicts", "invents") else f


def confusions():
    for mm in models():
        print(f"\n## {mm}: base s1 confusions (gold → picked)\n")
        cnt = defaultdict(int)
        for r in rows(mm, "base"):
            if fam(r) == "s1" and not ok(r):
                cnt[(r["gold"], top(r))] += 1
        print(", ".join(f"{g}→{p} {n}" for (g, p), n in sorted(cnt.items(), key=lambda x: -x[1])))


ITEMS = None
DEDUPE = False
CUES = False
GATE_LATER = False   # a later step joins the plan only when its own answer passes θ
GATE_N = False       # the count counts only when it passes θ, else one step


def items():
    global ITEMS
    if ITEMS is None:
        from bench import load
        ITEMS = {it["id"]: it for it in load()}
    return ITEMS


def engine(rs):
    """Each sentence as the engine would take it (interpret.py): θ gates, neutral fallbacks, clarify cards."""
    by = defaultdict(dict)
    for r in rs:
        if r["family"] not in ("rely", "check"):
            by[r["id"]][fam(r)] = r
    out = {}
    for i, qs in by.items():
        it = items()[i]
        gold = it["gold"]["steps"]
        s1 = qs["s1"]
        unsure = max(s1["probs"].values()) < THETA   # the engine asks the narration model next; not settled here
        # golds are in each variant's own keys, so compare per position: steps match, then the next one stops
        plan_ok = ok(s1) and not unsure
        if "n" in qs:
            # the count question sets the length; each later step is the top schema, no end option
            want = {"one": 1, "two": 2, "three": 3, "1": 1, "2": 2, "3": 3}[top(qs["n"])]
            if GATE_N and max(qs["n"]["probs"].values()) < THETA:
                want = 1
            if DEDUPE:
                # a step repeating the one before it is the same action told in two clauses
                steps = [top(s1)]
                for j in range(2, want + 1):
                    r = qs.get(f"s{j}")
                    t = top(r) if r else "?"
                    if GATE_LATER and (r is None or max(r["probs"].values()) < THETA):
                        break
                    if t != steps[-1]:
                        steps.append(t)
                plan_ok = plan_ok and steps == gold[:3]
            else:
                plan_ok = plan_ok and want == min(len(gold), 3) and all(ok(qs[f"s{j}"]) for j in range(2, want + 1))
        for n, k in enumerate(("s2", "s3") if "n" not in qs else (), start=2):
            r = qs.get(k)
            if r is None or not plan_ok:
                break
            t, p = top(r), max(r["probs"].values())
            if n > len(gold):
                plan_ok = p < THETA or t == r["gold"]
                break
            plan_ok = t == r["gold"] and p >= THETA
        ok_slots, clar = True, False
        stats = it["scene"].get("player", {}).get("stats", {})
        for f in ("intent", "target", "approach", "strain", "tone", "claim"):
            r = qs.get(f)
            if r is None:
                continue
            t, p = top(r), max(r["probs"].values())
            if f in ("intent", "target"):
                if p < THETA:
                    clar = True
                    continue
                pick = t
            elif f == "strain":
                pick = t if p >= THETA else "natural"
            elif f == "tone":
                pick = t if p >= THETA else "polite"
            elif f == "approach":
                cue = approach_cue(it["text"]) if CUES else None
                pick = cue or (t if p >= THETA else max(("force", "finesse", "wits", "charm"), key=lambda a: stats.get(a, 0)))
            else:
                pick = t if p >= THETA else "none"
            ok_slots &= pick == r["gold"]
        out[i] = {"plan": plan_ok, "unsure_s1": unsure, "slots": ok_slots and not clar, "clarify": clar,
                  "turn": plan_ok and ok_slots and not clar, "multi": len(gold) > 1}
    return out


def mixed(mm, v):
    """A variant changes only its families; borrow base answers for the rest."""
    out = {key(r): r for r in rows(mm, "base")}
    changed = VARIANTS[v]
    for r in rows(mm, v):
        if changed is None or r["family"] in changed:
            out[key(r)] = r
    return list(out.values())


def table_engine():
    print("\n## as the engine takes it (per sentence; Δ vs base, p = sign test)\n")
    print("| model · variant | plan right | single / multi | s1 unsure | layer-2 right | clarify | whole turn | Δ turn (p) |")
    print("|---|---|---|---|---|---|---|---|")
    for mm in models():
        b = engine(rows(mm, "base"))
        for v in VARIANTS:
            if not rows(mm, v):
                continue
            e = b if v == "base" else engine(mixed(mm, v))
            if v != "base" and e == b:
                continue
            n = len(e)
            avg = {k: sum(x[k] for x in e.values()) / n for k in ("plan", "unsure_s1", "slots", "clarify", "turn")}
            single = [x["plan"] for x in e.values() if not x["multi"]]
            multi = [x["plan"] for x in e.values() if x["multi"]]
            up = sum(e[i]["turn"] and not b[i]["turn"] for i in e)
            down = sum(b[i]["turn"] and not e[i]["turn"] for i in e)
            d = f"{avg['turn'] - sum(x['turn'] for x in b.values()) / n:+.3f} ({mcnemar(up, down):.2f})"
            print(f"| {mm} · {v} | {avg['plan']:.3f} | {sum(single) / len(single):.2f} / {sum(multi) / len(multi):.2f} | "
                  f"{avg['unsure_s1']:.3f} | {avg['slots']:.3f} | {avg['clarify']:.3f} | {avg['turn']:.3f} | {d} |")


def calibration():
    print("\n## s1 by threshold: share accepted / accuracy among accepted\n")
    print("| model | " + " | ".join(f"θ {t}" for t in (0.3, 0.4, 0.5, 0.6, 0.7)) + " |")
    print("|---|" + "---|" * 5)
    for mm in models():
        rs = [r for r in rows(mm, "base") if fam(r) == "s1"]
        cells = []
        for t in (0.3, 0.4, 0.5, 0.6, 0.7):
            kept = [r for r in rs if max(r["probs"].values()) >= t]
            cells.append(f"{len(kept) / len(rs):.2f} / {sum(map(ok, kept)) / max(1, len(kept)):.3f}")
        print(f"| {mm} | " + " | ".join(cells) + " |")


def flags(rs):
    """The rewrite the engine makes: a sentence is bad when either check passes θ."""
    by = defaultdict(dict)
    for r in rs:
        if r["family"] == "check":
            by[r["id"]][r["q"]] = r
    out = []
    for qs in by.values():
        if "bad" in qs:
            out.append((qs["bad"]["gold"] == "true", qs["bad"]["probs"]["true"] >= THETA))
        else:
            gold = qs["contradicts"]["gold"] == "true" or qs["invents"]["gold"] == "true"
            out.append((gold, max(qs[k]["probs"]["true"] for k in ("contradicts", "invents")) >= THETA))
    return out


def table_check():
    print("\n## narration check as a rewrite decision (bad = contradicts or invents)\n")
    print("| model · variant | acc | caught bad | flagged fine |")
    print("|---|---|---|---|")
    for mm in models():
        for v in ("base", "en", "sent_state", "check_choice"):
            f = flags(rows(mm, v))
            if not f:
                continue
            bad = [x for x in f if x[0]]
            fine = [x for x in f if not x[0]]
            print(f"| {mm} · {v} | {sum(g == p for g, p in f) / len(f):.3f} | {sum(p for _, p in bad)}/{len(bad)} | "
                  f"{sum(p for _, p in fine)}/{len(fine)} |")


def rely_shares():
    print(f"\n## rely exact by share cut (RELY_SHARE {RELY_SHARE})\n")
    for mm in models():
        rr = [r for r in rows(mm, "base") if r["family"] == "rely"]
        if rr:
            print(mm, " ".join(f"{s}: {rely_metrics(rr, s)['exact']:.2f}" for s in (0.05, 0.1, 0.15, 0.2, 0.3)))


if __name__ == "__main__":
    table_base()
    table_genre()
    table_variants()
    confusions()
    rely_shares()
    table_engine()
    calibration()
    table_check()
