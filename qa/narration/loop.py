"""Loop bench: typed lines run one after another in one game, so each reply carries what the earlier turns left.

  python loop.py NAME [--repeat 2] [--script recall] [--root DIR]

typed.py starts every line in a fresh game and so cannot see what a cycle hands to the next one: a fact a quote made up,
a worry told twice, a phrase that comes back. Lines that refer back ("아까 어디 있다고 했지?") ask for exactly that.
A card that opens is taken with its default, since this bench measures the replies, not the choices.
"""
import argparse
import asyncio
import json
import shutil
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import common
from run import Recording, commit
from src.interpret import Interpreter
from src.service import GameService
from src.story.validate import load_all
from typed import outcome, sentences

ROOT = common.RUNS / "loop-1"
STORY = "lighthouse"
CREATION = {"approaches": {"force": 1, "finesse": 2, "wits": 1, "charm": 0}, "traits": ["sailor", "tinker"]}
SCRIPTS = {
    # the dock with 윤슬, then the village with 도해; 5 and 13 refer back
    "talker": ["안녕", "넌 이름이 뭐니", "아버지는 어디 가셨어?", "먹을거 어디 있어?", "아까 어디 있다고 했지?",
               "등대 얘기 좀 해줘", "무서워?", "아버지 배 걱정되지?", "마을로 가자", "안녕하세요", "등대지기세요?",
               "아들 소식은 있어요?", "아까 그 아이가 그러던데 먹을 거 있다고", "등대 기름 어디 있어요?", "열쇠 좀 빌려주세요"],
    # alone at the lighthouse, musing between acts
    "explorer": ["등대로 가", "여기 뭐가 있지?", "흠..", "문 열어", "아무도 없어요?", "문 발로 차", "와 바람 개쎄네",
                 "담장 쪽 살펴봐", "여기 좀 무섭네", "마을로 돌아가"],
    # 7 and 8 ask about answers that have left the 3-turn narration window
    "recall": ["아버지는 어디 가셨어?", "먹을거 어디 있어?", "넌 이름이 뭐니", "무서워?", "등대 얘기 좀 해줘",
               "날씨 진짜 별로다", "아까 먹을 거 어디 있다고 했지?", "아버지 언제 나가셨다고 했지?"],
}


async def turn(svc, narrator, gid: str, view: dict, k: int, text: str) -> tuple[dict, dict]:
    t0 = time.monotonic()
    res = await svc.command(gid, {"request_id": f"t{k}", "revision": view["revision"], "text": text})
    interp = time.monotonic() - t0
    steps, card = list(res["steps"]), res["view"].get("card")
    if card and card["kind"] != "clarify":
        pick = card.get("selected") or card["options"][0]["id"]
        res = await svc.command(gid, {"request_id": f"c{k}", "revision": res["view"]["revision"], "card": card["id"],
                                      "pick": pick})
        steps += res["steps"]
    row = {"k": k, "text": text, "steps": [s["action"] for s in steps], "card": card and card["kind"],
           "kind": res["kind"], "interp_s": round(interp, 2), "place": res["view"]["scene"]["place"]["name"],
           "beats": [view["player"]["beats"], res["view"]["player"]["beats"]]}
    row["outcome"] = outcome(row["steps"])
    if res.get("turn"):
        narrator.reset()
        t0 = time.monotonic()
        events = [e async for e in await svc.narration(gid, res["turn"])]
        row["narr_s"] = round(time.monotonic() - t0, 2)
        _, g = await svc.load(gid)
        entry = g.presentation["narration"].get(str(res["turn"]))
        if entry is None:
            row["error"] = events[-1].get("message") if events else "no events"
        else:
            row.update(text_out=entry["text"], attempts=entry["attempts"], dropped=entry["dropped"],
                       chars=len(entry["text"]), sentences=sentences(entry["text"]), prompt=narrator.prompts[-1:])
    return row, res["view"]


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("name")
    ap.add_argument("--repeat", type=int, default=2)
    ap.add_argument("--script", action="append", choices=list(SCRIPTS))
    ap.add_argument("--root")
    a = ap.parse_args()
    out = ROOT / f"{a.name}.json"
    if out.exists():
        raise SystemExit(f"{out} exists; recordings are evidence, so pick another name")
    decision, llm = common.models()
    narrator = Recording(llm, decision)
    stories = load_all(common.checkout() / "scenarios")
    tmp = Path(tempfile.mkdtemp())
    svc = GameService(stories, tmp, Interpreter(decision, llm), narrator, seeds=lambda: 7)
    rows = []
    for r in range(a.repeat):
        for name, lines in SCRIPTS.items():
            if a.script and name not in a.script:
                continue
            made = await svc.create(f"{name}-{r}", STORY, CREATION)
            gid, view = made["game_id"], made["view"]
            for k, text in enumerate(lines, 1):
                row, view = await turn(svc, narrator, gid, view, k, text)
                rows.append({"repeat": r, "script": name, **row})
                print(r, name, k, row["outcome"], row["place"], row["beats"], row.get("narr_s"),
                      f"{text} → {row.get('text_out')}", flush=True)
    shutil.rmtree(tmp, ignore_errors=True)
    ROOT.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"name": a.name, "commit": commit(), "rows": rows}, ensure_ascii=False, indent=1),
                   encoding="utf-8")
    print(f"→ {out}")


if __name__ == "__main__":
    asyncio.run(main())
