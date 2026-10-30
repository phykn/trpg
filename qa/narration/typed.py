import argparse
import asyncio
import json
import re
import shutil
import sys
import tempfile
import time
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import common
from run import Recording, commit
from src.interpret import Interpreter
from src.service import GameService
from src.story.evals import replay
from src.story.validate import _creation, load_all

ROOT = common.RUNS / "typed-1"
STORY = "lighthouse"
FIRST = "하이"          # the first line of the evals' typed section
# More small talk and musing, at the evals' states: path 0 step 0 the dock (윤슬), step 2 the yard (no one).
EXTRA = [
    ({"path": 0, "step": 0}, "응 그래"),
    ({"path": 0, "step": 0}, "아버지 배 걱정되지?"),
    ({"path": 0, "step": 0}, "아 배고파"),
    ({"path": 0, "step": 0}, "날씨 진짜 별로다"),
    ({"path": 0, "step": 2}, "흠.."),
    ({"path": 0, "step": 2}, "여기 좀 무섭네"),
]


def lines(u) -> list[tuple[dict, str, object]]:
    cases = yaml.safe_load((common.checkout() / "scenarios" / "skeleton" / "evals.yaml").read_text(encoding="utf-8"))
    start = next(i for i, c in enumerate(cases) if c["text"] == FIRST)
    return [(c["at"], c["text"], c["expect"]) for c in cases[start:]] + [(at, t, None) for at, t in EXTRA]


def outcome(steps: list[str]) -> str:
    if not steps:
        return "refused"
    a = steps[0]
    if a.startswith("try:player:"):
        return "idle"
    if a.startswith("talk:") and a.split(";")[0].endswith(":chat"):
        return "chat"
    return "act"


def sentences(text: str) -> int:
    return len([s for s in re.split(r"(?<=[.?!…])\s+", text.strip()) if s])


async def one(svc, narrator, u, k: int, at: dict, text: str) -> dict:
    run = replay(u, at)
    made = await svc.create(f"typed-{k}", STORY, _creation(u, u.witnesses["paths"][at["path"]]))
    gid = made["game_id"]
    _, g = await svc.load(gid)
    g.state, g.log = run.s, run.log
    await svc.store(u, g)
    view = (await svc.view(gid))
    t0 = time.monotonic()
    res = await svc.command(gid, {"request_id": "t", "revision": view["revision"], "text": text})
    interp = time.monotonic() - t0
    steps, card = list(res["steps"]), res["view"].get("card")
    if card and card["kind"] != "clarify":
        pick = card.get("selected") or card["options"][0]["id"]
        res = await svc.command(gid, {"request_id": "c", "revision": res["view"]["revision"], "card": card["id"],
                                      "pick": pick})
        steps += res["steps"]
    row = {"at": at, "text": text, "steps": [s["action"] for s in steps], "card": card and card["kind"],
           "kind": res["kind"], "reason": res.get("reason"), "interp_s": round(interp, 2),
           "beats": [view["player"]["beats"], res["view"]["player"]["beats"]]}
    row["outcome"] = outcome(row["steps"])
    if res.get("turn"):
        row.update(await narrated(svc, narrator, gid, res["turn"]))
        if text_out := row.get("text_out"):
            senses = u.places[run.s.where("player")].senses
            row.update(quote='"' in text_out, senses=[s for s in senses if sum(w in text_out for w in s.split()) >= 2])
    return row


async def narrated(svc, narrator, gid: str, turn: int) -> dict:
    """One turn's narration as the bench records it, with the prompt of its last attempt."""
    narrator.reset()
    t0 = time.monotonic()
    events = [e async for e in await svc.narration(gid, turn)]
    out = {"narr_s": round(time.monotonic() - t0, 2)}
    _, g = await svc.load(gid)
    entry = g.presentation["narration"].get(str(turn))
    if entry is None:
        return {**out, "error": events[-1].get("message") if events else "no events"}
    return {**out, "text_out": entry["text"], "attempts": entry["attempts"], "dropped": entry["dropped"],
            "chars": len(entry["text"]), "sentences": sentences(entry["text"]), "prompt": narrator.prompts[-1:]}


async def main():
    ap = argparse.ArgumentParser(formatter_class=argparse.RawDescriptionHelpFormatter, description="""\
Typed-line bench: lines as players type them, each run as one turn from its state, with what the narration wrote.

The lines are the typed section of the story's evals (and EXTRA), so the reply is measured on what interpretation is
gated on. Each line starts from its eval state in a fresh game; a card that opens is taken with its default, since this
bench measures the reply, not the choice.
""")
    ap.add_argument("name")
    ap.add_argument("--repeat", type=int, default=2)
    ap.add_argument("--root")
    a = ap.parse_args()
    out = ROOT / f"{a.name}.json"
    if out.exists():
        raise SystemExit(f"{out} exists; recordings are evidence, so pick another name")
    decision, llm = common.models()
    narrator = Recording(llm, decision)
    stories = load_all(common.checkout() / "scenarios")
    u = stories[STORY]
    tmp = Path(tempfile.mkdtemp())
    svc = GameService(stories, tmp, Interpreter(decision, llm), narrator, seeds=lambda: 7)
    rows, k = [], 0
    for r in range(a.repeat):
        for at, text, expect in lines(u):
            k += 1
            row = {"repeat": r, "expect": expect, **await one(svc, narrator, u, k, at, text)}
            rows.append(row)
            print(r, row["outcome"], row["beats"], row.get("narr_s"), f"{row['text']} → {row.get('text_out')}",
                  flush=True)
    shutil.rmtree(tmp, ignore_errors=True)
    ROOT.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"name": a.name, "commit": commit(), "rows": rows}, ensure_ascii=False, indent=1),
                   encoding="utf-8")
    print(f"→ {out}")


if __name__ == "__main__":
    asyncio.run(main())
