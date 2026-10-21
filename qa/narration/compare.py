import json
import re
import sys
from collections import Counter, defaultdict
from itertools import pairwise
from pathlib import Path
from statistics import mean

WEATHER = ("바람", "빗", "비가", "파도", "구름", "하늘", "물보라", "빗줄기")
QUOTE = re.compile(r"\"[^\"]+\"|“[^”]+”")
SENTENCE = re.compile(r"(?:\"[^\"]*\"|“[^”]*”|[^.?!…])+(?:[.?!…]+[\"'”’]?|$)")
WORD = re.compile(r"[가-힣]+")
PARTICLES = ("에게서", "에서", "에게", "으로", "까지", "부터", "처럼", "보다", "은", "는", "이", "가", "을", "를", "에", "의",
             "로", "와", "과", "도", "만")
# Bound nouns and adverbs pair with anything; a phrase of two of them is grammar, not a tic.
SLIGHT = {"것", "수", "듯", "때", "곳", "채", "중", "뿐", "더", "또", "좀", "잘", "다", "안", "못", "그", "저", "한", "몇", "온"}
# A quote's opening word ("글쎄요,") or a short cry anywhere in it ("컥!"): play-4-talker 24–33 coughed in every line.
CRY = re.compile(r"^\s*([가-힣]{1,3})[!?,.…~]|(?:^|[\s.…,!?~*\\])([가-힣]{1,2})!")
AUX = {"있습니다", "없습니다", "합니다", "입니다", "됩니다", "않습니다", "같습니다", "보입니다", "시작합니다"}

# The checks below are heuristics over the recorded turn facts, tuned to the skeleton story the script plays.
# Time words: the sky darkening, wind, rain or waves rising, in a clause about the sky or the weather. With no clock
# moving this turn there is no time to tell (play-3-explorer 13–19, play-5-talker 4–24).
PROGRESS = re.compile(r"(어두워|어둑해|짙어|거세|거칠어|높아|굵어|사나워)(지|집|져|졌)|저물|저무|땅거미")
SKY = ("하늘", "바람", "파도", "빗", "비가", "구름", "물보라", "어둠", "어스름", "해가", "노을", "폭풍", "날이")
# Words that tell an obstacle overcome or a clock come to pass, by the story's ids. Told while it is short of full, the
# narration runs ahead of the screen (play-2-bold 6–7, play-4-odd 28, play-4-bold 11, play-4-explorer 29).
DONE = {
    "door": ("문이 열리", "문이 열립", "문이 열렸", "문이 활짝", "문이 벌컥", "문을 열어젖", "문이 스르르", "자물쇠가 풀",
             "자물쇠가 열", "자물쇠가 돌아"),
    "hound": ("꼬리를 흔들", "얌전해", "잠잠해", "순해", "누렁이가 물러", "누렁이는 물러", "길을 비키", "길을 비켜"),
    "lamp": ("불이 붙", "불이 켜", "불을 켜", "불이 밝혀", "불을 밝혔", "불이 들어", "불꽃이 피어", "불꽃이 타오", "불꽃이 일",
             "불길이", "불빛이 퍼", "불빛이 번", "빛이 바다", "타오릅니다", "타오르기"),
    # Nightfall only: "어둠이 내려앉은 등대 안쪽" and "열린 문 사이로 칠흑 같은 어둠" are the dark inside, not the
    # sunset (narr-3/head-a games 0 and 1, turn 13).
    "deadline.1": ("해가 졌", "해가 지고", "해가 저물었", "해가 넘어갔", "날이 저물었", "밤이 되", "밤이 찾아", "밤이 내려"),
    "deadline.2": ("암초에 부딪", "암초에 걸", "암초에 닿", "좌초", "배가 부서", "배가 뒤집"),
    "t_bridge_fall": ("다리가 무너", "다리가 끊어", "다리가 끊겼", "다리가 휩쓸", "다리가 부서", "다리가 내려앉"),
    "clock.1": ("폭풍이 덮쳤", "폭풍이 몰아닥", "폭풍이 들이닥", "폭풍이 휘몰아쳤"),
}
NEGATED = re.compile(r"^[가-힣]*\s?(지 않|지 못|려|듯|전)")      # not, cannot, about to, as if, before

METRICS = [         # name, what one game's value is
    ("quote", "turns with a quoted line (share)"),
    ("talk_quote", "talk/give turns, not blocked, with a quote"),
    ("weather", "weather words per turn"),
    ("chars", "characters per turn"),
    ("attempts", "attempts per narration, recaps included"),
    ("dropped", "narrations that dropped sentences (share)"),
    ("phrase3", "phrases in 3+ turns"),
    ("speaker", "a speaker's cries and phrases in 2+ turns"),
    ("ending", "turns ending on a word that ends 3+ turns"),
    ("ahead_time", "turns telling time pass, no clock moved"),
    ("ahead_done", "narrations telling done what is not full"),
]


def stem(w: str) -> str:
    return next((w[:-len(p)] for p in PARTICLES if w.endswith(p) and len(w) > len(p)), w)


def outside(text: str) -> str:
    return QUOTE.sub(", ", text)


def sentences(text: str) -> list[str]:
    out: list[str] = []
    for s in SENTENCE.findall(" ".join(text.split())):
        s = s.strip()
        if out and QUOTE.fullmatch(s):
            out[-1] += " " + s          # a bare quoted line belongs to the sentence that says who speaks it
        elif s:
            out.append(s)
    return out


def phrases(text: str, names: set) -> dict:
    """Two-word phrases within a clause, keyed by stems so 젖은 손을 and 젖은 손이 are one phrase."""
    out = {}
    for part in re.split(r"[.?!…,]", text):
        for a, b in pairwise(WORD.findall(part)):
            key = (stem(a), stem(b))
            if key[0] in SLIGHT and key[1] in SLIGHT or key[0] in names and key[1] in names or len(a + b) < 3:
                continue
            out.setdefault(key, f"{a} {b}")
    return out


def quotes(text: str, people: dict, addressed: str | None):
    """(speaker, quoted text). The speaker is the last person named before the quote, as in "도해가 말합니다. "…"",
    else the first named after it, else whom the turn addressed."""
    for m in QUOTE.finditer(text):
        before, after = outside(text[:m.start()]), outside(text[m.end():])
        last = max(((before.rfind(n), x) for x, ns in people.items() for n in ns if n in before), default=None)
        first = min(((after.find(n), x) for x, ns in people.items() for n in ns if n in after), default=None)
        if who := (last or first or (0, addressed))[1]:
            yield who, m[0][1:-1]


def ending(text: str) -> str | None:
    said = sentences(text)
    ws = WORD.findall(outside(said[-1])) if said else []
    if not ws:
        return None
    return " ".join(ws[-2:]) if ws[-1] in AUX and len(ws) > 1 else ws[-1]


def ahead_time(text: str) -> str | None:
    for s in sentences(outside(text)):
        if (m := PROGRESS.search(s)) and any(w in s for w in SKY):
            return m[0]
    return None


def ahead_done(text: str, known: dict) -> list[str]:
    bare, out = outside(text), []
    for x, words in DONE.items():
        fill, boxes = known.get(x, (0, 1))
        if fill >= boxes:
            continue
        for w in words:
            i = bare.find(w)
            if i >= 0 and not NEGATED.match(bare[i + len(w):]):
                out.append(f"{w}… ({x} {fill}/{boxes})")
                break
    return out


def addressed(steps: list[str]) -> str | None:
    for s in steps:
        parts = s.split(";")[0].split(":")
        if parts[0] in ("talk", "give"):
            return parts[1] if parts[0] == "talk" else parts[2]
    return None


def game(meta: dict, rows: list) -> tuple[dict, dict]:
    """One game's metric values and the items behind the counted ones."""
    names = {stem(w) for w in meta["names"]}
    turns = [r for r in rows if "n" in r]
    texts = {r["n"]: r["narration"]["text"] for r in turns}
    talk = [r for r in turns if any(s.startswith(("talk", "give")) for s in r["steps"]) and "blocked" not in r["results"]]
    v, items = {}, defaultdict(list)
    v["quote"] = mean(bool(QUOTE.search(t)) for t in texts.values())
    v["talk_quote"] = mean(bool(QUOTE.search(r["narration"]["text"])) for r in talk) if talk else 0
    v["weather"] = mean(sum(t.count(w) for w in WEATHER) for t in texts.values())
    v["chars"] = mean(len(t) for t in texts.values())
    v["attempts"] = mean(r["narration"]["attempts"] for r in rows)
    v["dropped"] = mean(r["narration"]["dropped"] > 0 for r in rows)

    seen, surface = defaultdict(set), {}
    for n, t in texts.items():
        for key, s in phrases(outside(t), names).items():
            seen[key].add(n)
            surface.setdefault(key, s)
    for key, ns in seen.items():
        if len(ns) >= 3:
            items["phrase3"].append(f"{surface[key]} {sorted(ns)}")

    spoken, surface = defaultdict(set), {}
    for r in turns:
        for who, q in quotes(r["narration"]["text"], meta["people"], addressed(r["steps"])):
            found = {(who, key): s for key, s in phrases(q, names).items()}
            for m in CRY.finditer(q):
                found[(who, ("cry", m[1] or m[2]))] = (m[1] or m[2]) + "…"
            for key, s in found.items():
                spoken[key].add(r["n"])
                surface.setdefault(key, s)
    for key, ns in spoken.items():
        if len(ns) >= 2:
            items["speaker"].append(f"{key[0]}: {surface[key]} {sorted(ns)}")

    ends = {n: e for n, t in texts.items() if (e := ending(t))}
    worn = {e for e, c in Counter(ends.values()).items() if c >= 3}
    items["ending"] = [f"{e} {sorted(n for n in ends if ends[n] == e)}" for e in sorted(worn)]
    v["ending"] = sum(e in worn for e in ends.values())

    for r in turns:
        if not r["facts"]["moved"] and (w := ahead_time(r["narration"]["text"])):
            items["ahead_time"].append(f"{r['n']}: {w}…")
    for r in rows:
        for hit in ahead_done(r["narration"]["text"], r["facts"]["known"]):
            items["ahead_done"].append(f"{r['n'] if 'n' in r else 'recap ' + str(r['recap'])}: {hit}")
    for k in ("phrase3", "speaker", "ahead_time", "ahead_done"):
        v[k] = len(items[k])
    return v, items


def load(path: str) -> dict:
    data = json.loads(Path(path).read_text())
    if not isinstance(data, dict) or "meta" not in data:
        raise SystemExit(f"{path}: not a narration bench recording of this format (narr-3)")
    by = defaultdict(list)
    for r in data["rows"]:
        by[r["game"]].append(r)
    games = [game(data["meta"], rows) for _, rows in sorted(by.items())]
    why = Counter(w[:16] for r in data["rows"] for c in r["narration"]["checks"]
                  for v in (*c.get("rules", {}).values(), *c.get("kev", {}).values()) for w in v)
    return {"path": path, "meta": data["meta"], "games": games, "why": why,
            "turns": sum("n" in r for r in by[0]), "recaps": sum("recap" in r for r in by[0])}


def verdict(a: list, b: list) -> str:
    """Beyond noise when no game of one side falls inside the other's range and the means differ by more than either
    side's range. Two identical sides pass by chance about 1 time in 20 per metric with 3 games each, 1 in 100 with 4."""
    if min(len(a), len(b)) < 3:
        return "needs 3+ games per side"
    lo, hi = sorted((a, b), key=mean)
    spread = max(max(a) - min(a), max(b) - min(b))
    if max(lo) < min(hi) and mean(hi) - mean(lo) > spread:
        return f"beyond noise ({'A' if hi is a else 'B'} higher)"
    return "within noise"


def cell(xs: list) -> str:
    f = (lambda x: f"{x:.0f}") if max(xs) >= 20 else (lambda x: f"{x:.2f}")
    return f"{f(mean(xs))} [{f(min(xs))}–{f(max(xs))}]"


def main(paths: list[str]):
    sides = [load(p) for p in paths]
    if len(sides) == 2:
        a, b = (s["meta"] for s in sides)
        same = ("script", "dice", "creation")
        if any(a[k] != b[k] for k in same):
            raise SystemExit(f"A and B ran different scripts ({', '.join(k for k in same if a[k] != b[k])} differ)")
    for label, s in zip("AB", sides):
        m = s["meta"]
        print(f"{label}  {s['path']}  {len(s['games'])} games × {s['turns']} turns + {s['recaps']} recaps  "
              f"seeds {', '.join(map(str, m['seeds']))}  {m['commit']}  {m['llm']}/{m['decision']}")
    print()
    print(f"{'metric':<11} {'per game':<43} " + " ".join(f"{x + ' mean [min–max]':<22}" for x in "AB"[:len(sides)])
          + (" verdict" if len(sides) == 2 else ""))
    for name, what in METRICS:
        vals = [[v[name] for v, _ in s["games"]] for s in sides]
        line = f"{name:<11} {what:<43} " + " ".join(f"{cell(xs):<22}" for xs in vals)
        print(line + (" " + verdict(*vals) if len(sides) == 2 else ""))
    for label, s in zip("AB", sides):
        print(f"\n{label} rejections: " + ", ".join(f"{k} {n}" for k, n in s["why"].most_common()))
        for g, (_, items) in enumerate(s["games"]):
            for name, _ in METRICS:
                if items.get(name):
                    print(f"  {label} game {g} {name}: " + "; ".join(items[name]))


if __name__ == "__main__":
    main(sys.argv[1:])
