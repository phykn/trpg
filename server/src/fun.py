"""Fun metrics F1–F11, F13, F14 from saved games, offline (fun.md 4). F12 is a survey and is not here.

python -m src.fun ../saves/engine [--stories ../scenarios] [--now 2026-10-19] [--json OUT]

Every metric reads the log (each event's action, roll, result, delta) and the presentation layer's
turn and request records. Saves written before request records existed have no sentence outcomes,
card origins or card openings, so F1, F2, F13 and F14 count only what was recorded.
"""

from __future__ import annotations

import argparse
import json
import math
import time
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

from .onto.atoms import PLAYER
from .onto.log import matches
from .onto.save import SaveError, rebuild
from .onto.universe import initial
from .rules.acts import parse
from .story.validate import load_all

QUIT_DAYS = 7
ROLLED = ("success", "mixed", "fail")
FORCED = ("pay", "grow")          # steps a card forces; neither a sentence nor a button chose them

# fun.md 4: the first hypotheses, as (low, high); None is open.
TARGETS = {
    "F1": (0.85, None), "F2": (0.50, None), "F3": (2, None), "F4": (0.45, 0.75), "F5": (4, 8),
    "F6": (0.30, 0.70), "F7": (0.50, None), "F8_people": (2, None), "F8_kept": (0.40, 0.80),
    "F9": (0.50, None), "F10_steps": (20, 40), "F10_deadline": (None, 0.50), "F11_chapter1": (None, 0.20),
    "F13_relied": (0.30, 0.70),
}


def ratio(n: int, d: int) -> float | None:
    return round(n / d, 3) if d else None


def mean(xs: list[float]) -> float | None:
    return round(sum(xs) / len(xs), 2) if xs else None


class Play:
    """One saved game: its universe, events, turn records and where each event's chapter is."""

    def __init__(self, u, data: dict, mtime: float):
        self.u, self.data, self.mtime = u, data, mtime
        self.g = rebuild(u, data)
        self.events = self.g.log.events
        self.p = data.get("presentation", {})
        self.turns = self.p.get("turns", [])
        self.requests = self.p.get("requests", [])
        self.steps = [s for t in self.turns for s in t["steps"]]
        self.chapter_at: dict[int, int] = {}
        k = 1
        for s in self.steps:
            self.chapter_at[s["t"]] = k
            k += sum(1 for c in s["changes"] if c["kind"] == "chapter")
        self.ending = self.p.get("ending") or next(
            (c["id"] for s in self.steps for c in s["changes"] if c["kind"] == "ending"), None)

    def rolled(self):
        return [e for e in self.events if e.roll is not None and e.result in ROLLED]


def f1(plays) -> dict:
    out = Counter()
    for pl in plays:
        for r in pl.requests:
            if r["kind"] == "text":
                out[r["outcome"]] += 1
            elif r["kind"] == "refused" and r.get("text"):
                out["refused"] += 1
    total = sum(out.values())
    return {"value": ratio(out["accepted"], total), "sentences": total, "outcomes": dict(out)}


def f2(plays) -> dict:
    by = Counter()
    for pl in plays:
        for t in pl.turns:
            origin = t.get("origin") or (t["kind"] if t["kind"] in ("text", "button") else None)
            if origin is None:
                continue
            by[origin] += sum(1 for s in t["steps"] if parse(s["action"]).schema not in FORCED)
    return {"value": ratio(by["text"], by["text"] + by["button"]), "steps": dict(by)}


def f3(plays) -> dict:
    ways: dict[str, set] = defaultdict(set)
    for pl in plays:
        for e in pl.events:
            a = parse(e.action)
            if a.schema == "try" and a.intent[0] != PLAYER and e.result != "blocked":
                ways[a.intent[0]].add(a.intent[1])
    per = {o: len(v) for o, v in sorted(ways.items())}
    return {"value": mean(list(per.values())), "approaches": per}


def f4(plays) -> dict:
    total, hard = 0, 0
    by_chapter: dict[int, list[int]] = defaultdict(lambda: [0, 0])
    for pl in plays:
        for e in pl.rolled():
            k = pl.chapter_at.get(e.t, 1)
            costly = e.result in ("mixed", "fail")
            total, hard = total + 1, hard + costly
            by_chapter[k][0] += costly
            by_chapter[k][1] += 1
    return {"value": ratio(hard, total), "rolls": total,
            "by_chapter": {k: ratio(h, n) for k, (h, n) in sorted(by_chapter.items())}}


def f5(plays) -> dict:
    gaps: list[int] = []
    for pl in plays:
        since = 0
        crises = {s["t"] for s in pl.steps if any(c["kind"] == "crisis" for c in s["changes"])}
        for e in pl.events:
            if e.roll is not None and e.result in ROLLED:
                since += 1
            if e.t in crises:
                gaps.append(since)
                since = 0
    return {"value": mean(gaps), "gaps": gaps}


def f6(plays) -> dict:
    answered = arrived = pending = 0
    for pl in plays:
        u = pl.u
        threats = {o for o, ob in u.obstacles.items() if ob.sub == "threat"}
        arrivals = {(c["id"], s["t"]) for s in pl.steps for c in s["changes"] if c["kind"] == "arrival"}
        for o in sorted(threats):
            seen, lowered, done = False, False, None
            for e in pl.events:
                if ("at", o, PLAYER) in e.delta.add:
                    seen = True
                if not seen or done:
                    continue
                before = next((at[2] for at in e.delta.remove if at[0] == "fill" and at[1] == o), None)
                after = next((at[2] for at in e.delta.add if at[0] == "fill" and at[1] == o), None)
                if before is not None and after is not None and after < before:
                    lowered = True
                if (o, e.t) in arrivals:
                    done = "arrived"
                elif ("at", o, PLAYER) in e.delta.remove:
                    done = "retired"
            if not seen:
                continue
            if done == "retired" or (done == "arrived" and lowered):
                answered += 1
            elif done == "arrived":
                arrived += 1
            else:
                pending += 1
    return {"value": ratio(answered, answered + arrived), "answered": answered, "arrived": arrived,
            "pending": pending}


def f7(plays) -> dict:
    read = total = 0
    for pl in plays:
        for e in pl.events:
            if parse(e.action).schema in ("pay", "declare", "choose"):
                total += 1
                read += any(matches(p, e.action, e.result) for p in pl.u.patterns)
    return {"value": ratio(read, total), "choices": total, "read": read}


def f8(plays) -> dict:
    people: list[int] = []
    kept = closed = 0
    for pl in plays:
        start = initial(pl.u, pl.data["creation"])
        def regard(s, h):
            return tuple(s.regards(h, PLAYER, axis) for axis in ("trust", "fear"))
        people.append(sum(1 for h in pl.u.agents if regard(start, h) != regard(pl.g.state, h)))
        for s in pl.steps:
            for c in s["changes"]:
                if c["kind"] == "promise" and c["owes"] == "promise" and c["state"] in ("kept", "broken"):
                    closed += 1
                    kept += c["state"] == "kept"
    return {"people": mean(people), "kept": ratio(kept, closed), "promises_closed": closed}


def f9(plays) -> dict:
    out = {}
    by_story: dict[str, Counter] = defaultdict(Counter)
    sizes = {}
    for pl in plays:
        sizes[pl.u.id] = len(pl.u.endings)
        if pl.ending:
            by_story[pl.u.id][pl.ending] += 1
    for sid, counts in sorted(by_story.items()):
        n = sum(counts.values())
        h = -sum(c / n * math.log(c / n) for c in counts.values())
        out[sid] = {"value": abs(round(h / math.log(sizes[sid]), 3)) if sizes[sid] > 1 else None,
                    "endings": dict(counts), "plays": n}
    return out


def f10(plays) -> dict:
    lengths: list[int] = []
    by_deadline = ended = 0
    for pl in plays:
        steps = 0
        for s in pl.steps:
            e = pl.events[s["t"]]
            rem = next((at[3] for at in e.delta.remove if at[:3] == ("stat", PLAYER, "beats")), None)
            add = next((at[3] for at in e.delta.add if at[:3] == ("stat", PLAYER, "beats")), None)
            steps += rem is not None and add is not None and add > rem
            kinds = [c["kind"] for c in s["changes"]]
            if "chapter" in kinds or "ending" in kinds:
                lengths.append(steps)
                steps = 0
                ended += 1
                by_deadline += any(c["kind"] == "arrival" and c["id"].startswith("deadline.") for c in s["changes"])
    return {"steps": mean(lengths), "lengths": lengths, "deadline": ratio(by_deadline, ended), "chapters": ended}


def f11(plays, now: float) -> dict:
    quit_at = Counter()
    for pl in plays:
        if not pl.ending and now - pl.mtime >= QUIT_DAYS * 86400:
            quit_at[max(pl.chapter_at.values(), default=1)] += 1
    n = len(plays)
    return {"quit": ratio(sum(quit_at.values()), n), "chapter1": ratio(quit_at[1], n),
            "by_chapter": dict(sorted(quit_at.items())), "games": n}


def f13_14(plays) -> dict:
    could = relied = decisive_help = 0
    opened = closed = 0
    for pl in plays:
        cards = {r["card"]: r for r in pl.requests if r["kind"] == "card"}
        for r in cards.values():
            if r["card_kind"] == "roll":
                opened += 1
        closed += sum(1 for r in pl.requests if r["kind"] in ("cancel", "discard")
                      and cards.get(r["card"], {}).get("card_kind") == "roll")
        for t in pl.turns:
            card = cards.get(t.get("card"))
            if not card or card["card_kind"] != "roll" or card["options"] < 2 or not t["steps"]:
                continue
            s = t["steps"][0]
            if s["roll"] is None:
                continue
            could += 1
            if ";rely=" in s["action"]:
                relied += 1
                decisive_help += any(s["mods"][i]["kind"] == "help" for i in s["decisive"])
    return {"F13": {"relied": ratio(relied, could), "decisive": ratio(decisive_help, relied), "rolls": could},
            "F14": {"value": ratio(closed, opened), "roll_cards": opened, "closed": closed}}


def measure(saves: list[Path], stories: dict, now: float) -> dict:
    plays, skipped = [], []
    for path in saves:
        data = json.loads(path.read_text(encoding="utf-8"))
        u = stories.get(data.get("story", {}).get("id"))
        try:
            if u is None:
                raise SaveError("unknown story")
            plays.append(Play(u, data, path.stat().st_mtime))
        except SaveError as e:
            skipped.append(f"{path.name}: {e}")
    rest = f13_14(plays)
    return {"games": len(plays), "skipped": skipped,
            "F1": f1(plays), "F2": f2(plays), "F3": f3(plays), "F4": f4(plays), "F5": f5(plays),
            "F6": f6(plays), "F7": f7(plays), "F8": f8(plays), "F9": f9(plays), "F10": f10(plays),
            "F11": f11(plays, now), **rest}


def verdict(value, key: str) -> str:
    if value is None:
        return "-"
    lo, hi = TARGETS[key]
    return "ok" if (lo is None or value >= lo) and (hi is None or value <= hi) else "out"


def table(m: dict) -> str:
    rows = [
        ("F1 해석 수용", m["F1"]["value"], "F1"), ("F2 자유 문장", m["F2"]["value"], "F2"),
        ("F3 해법의 다양성", m["F3"]["value"], "F3"), ("F4 굴림의 결과", m["F4"]["value"], "F4"),
        ("F5 위기의 간격", m["F5"]["value"], "F5"), ("F6 위협 반응", m["F6"]["value"], "F6"),
        ("F7 결과의 재사용", m["F7"]["value"], "F7"), ("F8 관계의 변화(인물)", m["F8"]["people"], "F8_people"),
        ("F8 약속 지킴", m["F8"]["kept"], "F8_kept"),
        *[(f"F9 결말의 분산({sid})", v["value"], "F9") for sid, v in m["F9"].items()],
        ("F10 장의 길이", m["F10"]["steps"], "F10_steps"), ("F10 마감으로 끝난 장", m["F10"]["deadline"], "F10_deadline"),
        ("F11 장 1 이탈", m["F11"]["chapter1"], "F11_chapter1"), ("F13 기대기", m["F13"]["relied"], "F13_relied"),
    ]
    lines = [f"games {m['games']}, skipped {len(m['skipped'])}", "| metric | value | target |", "|---|---|---|"]
    lines += [f"| {name} | {'-' if v is None else v} | {verdict(v, key)} |" for name, v, key in rows]
    lines.append(f"| F13 결정적 칩이 기댄 것 | {m['F13']['decisive'] if m['F13']['decisive'] is not None else '-'} | recorded |")
    f14 = m["F14"]["value"]
    lines.append(f"| F14 카드 이탈 | {'-' if f14 is None else f14} | {'-' if f14 is None else 'ok' if f14 <= 0.2 else 'out'} |")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("saves", type=Path, help="a save directory or file")
    ap.add_argument("--stories", type=Path, default=Path(__file__).resolve().parents[2] / "scenarios")
    ap.add_argument("--now", help="ISO date for F11 (default: now)")
    ap.add_argument("--json", type=Path, help="write the full measurement here")
    args = ap.parse_args()
    saves = sorted(args.saves.glob("*.json")) if args.saves.is_dir() else [args.saves]
    now = datetime.fromisoformat(args.now).timestamp() if args.now else time.time()
    m = measure(saves, load_all(args.stories), now)
    print(table(m))
    for line in m["skipped"]:
        print("skipped", line)
    if args.json:
        args.json.write_text(json.dumps(m, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
