import json
import re
import sys
from collections import Counter

WEATHER = ("바람", "빗", "비가", "파도", "구름", "하늘", "물보라", "빗줄기")
QUOTE = re.compile(r"\"[^\"]+\"|“[^”]+”")


def grams(t, n=4):
    t = re.sub(r"\s+", "", t)
    return {t[i:i + n] for i in range(len(t) - n + 1)}


def stats(path):
    rows = [r for r in json.load(open(path)) if r["narration"] and r["narration"].get("text")]
    talk = [r for r in rows if any(s.startswith(("talk", "give")) for s in r["steps"])]
    out = Counter()
    prev = {}
    for r in rows:
        t, checks = r["narration"]["text"], r["narration"]["checks"]
        out["n"] += 1
        out["quote"] += bool(QUOTE.search(t))
        out["weather"] += sum(t.count(w) for w in WEATHER)
        out["chars"] += len(t)
        out["attempts"] += len(checks)
        last = checks[-1] if checks else {}
        out["dropped"] += bool(last.get("rules") or last.get("kev") or last.get("whole"))
        for c in checks:
            for v in list(c.get("rules", {}).values()) + list(c.get("kev", {}).values()):
                for why in v:
                    out["why:" + why[:12]] += 1
        p = prev.get(r["run"])
        if p:
            g, h = grams(t), grams(p)
            out["repeat"] += len(g & h) / max(1, len(g))
        prev[r["run"]] = t
    n = out["n"]
    tq = sum(bool(QUOTE.search(r["narration"]["text"])) for r in talk)
    print(f"{path}: n={n} quote={out['quote']/n:.2f} talk-quote={tq}/{len(talk)} weather/turn={out['weather']/n:.2f} "
          f"repeat={out['repeat']/n:.3f} chars={out['chars']/n:.0f} attempts={out['attempts']/n:.2f} dropped={out['dropped']}")
    for k, v in sorted(out.items()):
        if k.startswith("why:"):
            print("  ", k, v)


for p in sys.argv[1:]:
    stats(p)
