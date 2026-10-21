"""Narration bench: a fixed script played with the real models, every narration and its checks recorded.

  python run.py NAME [--games 3] [--seed S] [--root DIR]

Each line runs exactly one turn with exactly the scripted action, or the bench stops with the turn named: a script that
drifts no longer measures the turns it was written for.
"""
import argparse
import asyncio
import json
import random
import secrets
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import common
from run_api import local_settings
from src.interpret import Interpreter
from src.narrate import Narrator, messages
from src.service import GameService
from src.story.validate import load_all

ROOT = common.RUNS / "narr-3"
STORY = "lighthouse"
CREATION = {"approaches": {"force": 1, "finesse": 2, "wits": 1, "charm": 0}, "traits": ["sailor", "tinker"]}
DICE = 7        # rolls follow the dice seed and the turn, so every game gets the results noted below
# One line per turn: the action it must run, and the player's sentence, or None to press the action as a button.
# Talks keep their sentence, since what the player says is what the person answers; the rest are buttons, so a change
# in interpretation cannot change what is narrated.
SCRIPT = [
    ("look:dock", None),
    ("talk:yunseul:chat;tone=friendly", "윤슬에게 안녕, 오늘 바다는 어때? 하고 말을 건다"),
    ("talk:yunseul:chat", "윤슬에게 아버지 배는 언제 돌아오는지 묻는다"),
    ("talk:yunseul:t_wall", "윤슬에게 등대 뒤 담장에 대해 물어본다"),          # roll: success
    ("go:village", None),
    ("talk:dohae:chat", "도해 영감님께 정중하게 인사를 드린다"),                 # the hidden dog blocks it; sunset 1/3
    ("try:hound:wits", None),                                                    # roll: success, the dog gives way
    ("give:letter:dohae", None),
    ("talk:dohae:t_oil", "도해에게 등대 기름이 어디 있는지 묻는다"),
    ("talk:dohae:favor", "도해에게 등대 열쇠를 빌려 달라고 부탁한다"),
    ("go:yard", None),                                                           # the bridge threat appears
    ("look:door", None),                                                         # scene end: sunset 2/3, bridge 1/3
    ("try:door:finesse;rely=thing:key", None),                                   # roll: success, the door opens
    ("go:lamp_room", None),                                                      # chapter 1 ends: its recap
    ("choose:g_oil:all_in", None),                                               # the lamp 2/4
    ("try:lamp:wits", None),                                                     # roll: success, lamp 4/4, the ending
]


class ScriptError(Exception):
    pass


class Seeds:
    """The narrator's model, noting the seed each draft is sampled with."""

    def __init__(self, llm):
        self.llm, self.log = llm, []

    def stream(self, *a, seed=None, **kw):
        self.log.append(seed)
        return self.llm.stream(*a, seed=seed, **kw)


class Recording(Narrator):
    def __init__(self, llm, decision):
        super().__init__(Seeds(llm), decision)
        self.reset()

    def reset(self):
        self.log, self.prompts, self.llm.log = [], [], []

    async def write(self, job, draft=None, problems=None):
        self.prompts.append(messages(job, draft, problems))
        return await super().write(job, draft, problems)

    def rules(self, job, said):
        per, whole = super().rules(job, said)
        self.log.append({"said": said, "rules": {str(k): v for k, v in per.items()}, "whole": whole})
        return per, whole

    async def judge(self, job, said, skip):
        out = await super().judge(job, said, skip)
        self.log[-1]["kev"] = {str(k): v for k, v in out.items()}
        return out


async def run_line(svc, gid: str, view: dict, n: int, action: str, text: str | None) -> tuple[dict, list]:
    where = f"turn {n} ({text or 'button ' + action})"
    res = await svc.command(gid, {"request_id": f"t{n}", "revision": view["revision"],
                                  **({"text": text} if text else {"action": action})})
    steps = list(res["steps"])
    card = res["view"].get("card")
    if card:
        ids = [o["id"] for o in card["options"]]
        if action not in ids:
            raise ScriptError(f"{where}: the {card['kind']} card offers {ids}, not {action}")
        res = await svc.command(gid, {"request_id": f"c{n}", "revision": res["view"]["revision"], "card": card["id"],
                                      "pick": action})
        steps += res["steps"]
    if res["kind"] == "refused":
        raise ScriptError(f"{where}: refused: {res['reason']}")
    ran = [s["action"] for s in steps]
    if ran != [action] or res["turn"] != n or res["view"].get("card"):
        raise ScriptError(f"{where}: ran {ran} as turn {res['turn']}, the script says {action}")
    return res, steps


def facts(before: dict, after: dict, steps: list, known: dict) -> dict:
    """What the screen showed after the turn, for checking that the narration does not run ahead of it. `known` carries
    every obstacle and clock seen so far, since the narration may name one out of sight."""
    b, a = ({c["id"]: c for c in v["clocks"]} for v in (before, after))
    came = {c["id"] for s in steps for c in s["changes"] if c["kind"] in ("crisis", "arrival")}
    for x in [*after["clocks"], *after["scene"]["obstacles"]]:
        known[x["id"]] = [x["fill"], x["boxes"]]
    for x in came:
        boxes = (b.get(x) or a.get(x) or {}).get("boxes")
        if boxes:
            known[x] = [boxes, boxes]           # a clock that came to pass is retired in the same step
    return {"place": after["scene"]["place"]["id"], "chapter": after["chapter"]["k"],
            "moved": sorted({x for x in a if x in b and a[x]["fill"] != b[x]["fill"]} | came),
            "known": {x: list(v) for x, v in known.items()}}


async def narrate(svc, narrator: Recording, gid: str, kind: str, k: int) -> dict:
    for _ in range(2):          # the models are shared, so a call times out now and then; a new request starts over
        narrator.reset()
        stream = await (svc.narration(gid, k) if kind == "turn" else svc.recap(gid, k))
        events = [e async for e in stream]
        if events and events[-1]["type"] != "error":
            break
    else:
        raise ScriptError(f"{kind} {k}: narration failed twice: {events[-1].get('message') if events else 'no events'}")
    _, g = await svc.load(gid)
    entry = g.presentation["narration" if kind == "turn" else "recap"][str(k)]
    return {**entry, "checks": narrator.log, "prompts": narrator.prompts, "seeds": narrator.llm.log}


async def play(game: int, seed: int, rows: list):
    # Every draft seed of this game follows from it. The mlx server did not replay a draft from its seed (2026-10-21:
    # one seed, two texts), so seeds are a record, and the spread across games is the noise.
    random.seed(seed)
    decision, llm = common.models()
    narrator = Recording(llm, decision)
    tmp = Path(tempfile.mkdtemp())
    svc = GameService(load_all(common.checkout() / "scenarios"), tmp, Interpreter(decision, llm), narrator,
                      seeds=lambda: DICE)
    made = await svc.create(f"bench-{game}", STORY, CREATION)
    gid, view, known = made["game_id"], made["view"], {}
    for n, (action, text) in enumerate(SCRIPT, 1):
        res, steps = await run_line(svc, gid, view, n, action, text)
        turn = {"game": game, "n": n, "action": action, "text": text, "steps": [s["action"] for s in steps],
                "results": [s["result"] for s in steps], "facts": facts(view, res["view"], steps, known)}
        view = res["view"]
        turn["narration"] = await narrate(svc, narrator, gid, "turn", n)
        rows.append(turn)
        print(game, n, turn["steps"], turn["results"], turn["narration"]["text"], flush=True)
        changes = {c["kind"]: c for s in steps for c in s["changes"]}
        if "chapter" in changes or "ending" in changes:
            k = changes["chapter"]["from"] if "chapter" in changes else view["chapter"]["k"]
            recap = {"game": game, "recap": k, "after": n, "facts": turn["facts"],
                     "narration": await narrate(svc, narrator, gid, "recap", k)}
            rows.append(recap)
            print(game, f"recap {k}", recap["narration"]["text"], flush=True)
    if not any("recap" in r for r in rows if r["game"] == game):
        raise ScriptError("the script ended no chapter, so no recap was narrated")
    shutil.rmtree(tmp, ignore_errors=True)


def story_words(u) -> dict:
    """Names the repetition metrics should not count as a tic: a thing the turn is about is named again and again."""
    names = [n for t in (u.places, u.agents, u.things, u.obstacles) for x in t for n in (u.name(x), *u.aliases(x))]
    names += [tp.title for a in u.agents.values() for tp in a.topics]
    return {"names": sorted({w for n in names for w in n.split()}),
            "people": {x: [a.name, *a.aliases] for x, a in u.agents.items()}}


def commit() -> str:
    out = subprocess.run(["git", "-C", str(common.checkout()), "describe", "--always", "--dirty"],
                         check=False, capture_output=True, text=True)
    return out.stdout.strip()


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("name")
    ap.add_argument("--games", type=int, default=3)
    ap.add_argument("--seed", type=int, help="narration seed of game 0 (default: random); game g uses SEED + g")
    ap.add_argument("--root")
    a = ap.parse_args()
    out = ROOT / f"{a.name}.json"
    if out.exists():
        raise ScriptError(f"{out} exists; recordings are evidence, so pick another name")
    base = secrets.randbelow(10**6) if a.seed is None else a.seed
    s = local_settings()
    meta = {"name": a.name, "root": str(common.checkout()), "commit": commit(), "decision": s.decision_model,
            "llm": s.llm_model, "dice": DICE, "creation": CREATION, "script": SCRIPT,
            **story_words(load_all(common.checkout() / "scenarios")[STORY]), "seeds": []}
    rows = []
    ROOT.mkdir(parents=True, exist_ok=True)
    for g in range(a.games):
        await play(g, base + g, rows)
        meta["seeds"].append(base + g)
        out.write_text(json.dumps({"meta": meta, "rows": rows}, ensure_ascii=False, indent=1))
    print(out)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except ScriptError as e:
        sys.exit(f"narration bench: {e}")
