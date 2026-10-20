"""Play one game turn by turn from the shell, with the real models and the real service, and keep its transcript.

  python play.py new RUN [--seed N] [--approaches force=1,finesse=2,wits=1,charm=0] [--traits a,b] [--story ID]
  python play.py say RUN "문장"        # a sentence, as typed into the game
  python play.py pick RUN N            # card option N (1 = first)
  python play.py cancel RUN            # close the card
  python play.py press RUN N           # recommended button N; gN for growth
  python play.py look RUN              # the screen again
  python play.py report RUN            # fun.md metrics for this game

Each run lives in qa_test/runs/RUN/: saves/ (the game), transcript.md (what the player saw), log.jsonl (responses).
"""
import argparse
import asyncio
import json
import random
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import common  # noqa: E402
from src.fun import measure, table  # noqa: E402
from src.interpret import Interpreter  # noqa: E402
from src.locale import ko  # noqa: E402
from src.narrate import Narrator, change_lines  # noqa: E402
from src.onto.atoms import APPROACHES  # noqa: E402
from src.service import GameService  # noqa: E402
from src.story.validate import load_all  # noqa: E402


class Run:
    def __init__(self, name: str):
        self.dir = common.RUNS / name
        self.meta_path = self.dir / "play.json"
        self.meta = json.loads(self.meta_path.read_text()) if self.meta_path.exists() else {}

    def save(self):
        self.meta_path.write_text(json.dumps(self.meta, ensure_ascii=False, indent=1))

    def service(self) -> GameService:
        decision, llm = common.models()
        stories = load_all(common.checkout() / "scenarios")
        return GameService(stories, self.dir / "saves", Interpreter(decision, llm), Narrator(llm, decision),
                           seeds=lambda: self.meta["seed"])

    def out(self, text: str, response: dict | None = None):
        print(text, flush=True)
        with (self.dir / "transcript.md").open("a") as f:
            f.write(text + "\n\n")
        if response is not None:
            with (self.dir / "log.jsonl").open("a") as f:
                f.write(json.dumps(response, ensure_ascii=False) + "\n")


LIFE = {"scene": "이번 장면", "chapter": "이번 장"}      # client/locale/ko.ts tagLife


def tags(items: list[dict]) -> str:
    """Tags of one kind, life and name once, with when they end, as the web screen draws them (Row.tsx TagItems)."""
    names = dict.fromkeys((t["kind"], t["life"], t["name"]) for t in items)
    return ", ".join(name + (f" · {LIFE[life]}" if life in LIFE else "") for _, life, name in names)


def screen(v: dict, before: list[str] | None = None) -> str:
    """The state lines marked `+` when new and `-` when gone since `before`, then what can be done."""
    now = state(v)
    lines = now if before is None else \
        [("+ " if x not in before else "") + x for x in now] + [f"- {x}" for x in before if x not in now]
    return "\n".join(lines + options(v))


def state(v: dict) -> list[str]:
    s, me = v["scene"], v["player"]
    lines = [f"[{v['chapter']['k']}장 {v['chapter']['title']}] 목표: {v['chapter']['aim']}",
             f"장소: {s['place']['name']}" + (f" ({' / '.join(s['place']['senses'])})" if s["place"]["senses"] else "")]
    if s["people"]:
        lines.append("사람: " + ", ".join(f"{p['name']}({p['attitude']}{', 동행' if p['with'] else ''})"
                                          for p in s["people"]))
    if s["things"]:
        lines.append("물건: " + ", ".join(t["name"] for t in s["things"]))
    for o in s["obstacles"]:
        # An overcome obstacle stays in the scene, checked and blocking nothing, as on the web screen (ui.md 2).
        done = o["fill"] >= o["boxes"]
        lines.append(f"장애물: {o['name']} {o['fill']}/{o['boxes']}" + (" ✓" if done else "")
                     + (f" (막음: {', '.join(o['blocks'])})" if o["blocks"] and not done else ""))
    if s["exits"]:
        lines.append("길: " + ", ".join(e["name"] + (" (막힘)" if e["blocked"] else "") for e in s["exits"]))
    if s["tags"]:
        lines.append("표시: " + tags(s["tags"]))
    for c in v["clocks"]:
        # The web screen fills the next box of a deadline, threat or fork by the scene's time spent (ui.md 2).
        part = f", 다음 칸 {me['beats']}/{me['beats_max']}" if c["kind"] != "clock" and c["fill"] < c["boxes"] else ""
        lines.append(f"시계: {c['name']} {c['fill']}/{c['boxes']}{part}")
    lines.append(f"나: 상처 {me['wounds']}/{me['wound_boxes']}, 성장 {me['growth']}, "
                 + ", ".join(f"{a['name']} {a['value']}" for a in me["approaches"])
                 + "".join(f", {t['name']}" + ("(씀)" if t["spent"] else "") for t in me["traits"])
                 + (", 가진 것: " + ", ".join(t["name"] + ("(씀)" if t["spent"] else "") for t in me["things"])
                    if me["things"] else "")
                 + (", 표시: " + tags(me["tags"]) if me["tags"] else ""))
    j = v["journal"]
    if j["beliefs"]:
        lines.append("아는 것: " + " / ".join(b["text"] + ("(씀)" if b["spent"] else "") for b in j["beliefs"]))
    for o in j["owes"]:      # client/locale/ko.ts promise, kindness
        lines.append(f"빚: {o['name']}에게 " + (o["promise"] if o["kind"] == "promise" else "신세"))
    return lines


def options(v: dict) -> list[str]:
    lines = [f"  {i}) {b['label']}" + (" [굴림]" if b["rolls"] else "") for i, b in enumerate(v["buttons"], 1)]
    # The web UI offers growth only once no card is open (client/logic/useGame.ts destination).
    lines += [f"  g{i}) {g['label']}" for i, g in enumerate(v["growth"], 1) if not v["card"]]
    if v["card"]:
        lines.append(card(v["card"]))
    if v["ending"]:
        lines.append(f"=== 결말: {v['ending']['title']}. 게임이 끝났습니다. 이제 report를 돌리세요 ===")
    return lines


def card(c: dict) -> str:
    head = c.get("question") or (c["plan"]["step"] or {}).get("label", "")
    rest = c["plan"]["rest"]
    lines = [f"카드({c['kind']}): {head}" + (f" → 다음: {' → '.join(rest)}" if rest else "")]
    if c["kind"] == "roll":
        # What the web roll card shows: the target number, high risk, the fixed modifiers (ui.md 4.2).
        pv = c["options"][-1]["preview"]
        fixed = "".join(f", {m['label']} {m['value']:+d}" for m in pv["mods"] if m["value"] and m["kind"] != "help")
        lines.append(f"  목표 {pv['dc']}" + (" ⚠ 되돌릴 수 없는 대가" if pv["risk"] == "high" else "") + fixed)
    for i, o in enumerate(c["options"], 1):
        extra = []
        if "preview" in o:
            extra += [f"{m['value']:+d}" for m in o["preview"]["mods"] if m["kind"] == "help" and m["value"]]
        if o.get("effects"):
            extra.append(" · ".join(o["effects"]))
        if o.get("note"):
            extra.append(o["note"])
        mark = " *" if o["id"] == c.get("selected") else ""
        lines.append(f"  {i}) {o['label']}{mark}" + (f" — {', '.join(extra)}" if extra else ""))
    return "\n".join(lines)


def steps(u, res: dict) -> list[str]:
    lines = []
    for r in res.get("steps", []):
        head = f"- {r['label']}"
        if r["roll"]:
            mods = "".join(f" {c['value']:+d}" for c in r["mods"] if c["value"])
            head += f" — 2d6 {r['roll']['d1']}+{r['roll']['d2']}{mods} = {r['total']} / {r['dc']}"
        if r["result"] not in ("none", None):
            head += f" → {ko.RESULTS[r['result']]}"
        lines.append(head)
        lines += [f"    {x}" for x in change_lines(u, r["changes"])]
    return lines


def recap_of(res: dict, v: dict) -> int | None:
    """client/logic/useGame.ts recapChapter: the chapter that just closed."""
    for r in res.get("steps", []):
        for c in r["changes"]:
            if c["kind"] == "chapter":
                return c["from"]
            if c["kind"] == "ending":
                return v["chapter"]["k"]
    return None


async def text_of(events) -> str:
    out, result = [], None
    async for e in events:
        if e["type"] == "result":
            result = e["text"]
        elif e["type"] == "error":
            return f"(서술 오류: {e.get('message', e)})"
        elif "text" in e:
            out.append(e["text"])
    return result if result is not None else "".join(out)


async def send(run: Run, body: dict, said: str):
    svc = run.service()
    gid = run.meta["game_id"]
    view = await svc.view(gid)
    run.meta["seq"] += 1
    t0 = time.monotonic()
    res = await svc.command(gid, {"request_id": f"q{run.meta['seq']}", "revision": view["revision"], **body})
    ms = int((time.monotonic() - t0) * 1000)
    run.meta["commands"] = run.meta.get("commands", 0) + 1
    u = svc.stories[run.meta["story"]]
    v = res["view"]
    lines = [f"## {run.meta['commands']}. {said}", f"(해석 {ms}ms)"]
    if res["kind"] == "refused":
        lines.append(f"거절: {res['reason']}")
    lines += steps(u, res)
    if res.get("turn") is not None:
        t0 = time.monotonic()
        lines.append("서술: " + await text_of(await svc.narration(gid, res["turn"])))
        lines.append(f"(서술 {int((time.monotonic() - t0) * 1000)}ms)")
        k = recap_of(res, v)
        if k is not None:
            lines.append(f"장 요약({k}장): " + await text_of(await svc.recap(gid, k)))
    v = await svc.view(gid)
    lines.append(screen(v, run.meta.get("state")))
    run.meta["state"] = state(v)
    run.save()
    run.out("\n".join(lines), {"command": run.meta["commands"], "said": said, "ms": ms, **res})


def creation_of(u, a) -> dict:
    if a.approaches:
        ap = {k: int(x) for k, x in (kv.split("=") for kv in a.approaches.split(","))}
    else:
        ap = dict(zip(APPROACHES, sorted(u.approaches, reverse=True), strict=True))
    traits = a.traits.split(",") if a.traits else list(u.traits)[:u.pick]
    return {"approaches": ap, "traits": traits}


async def new(a):
    run = Run(a.run)
    if run.meta:
        raise SystemExit(f"{run.dir} exists; pick another RUN")
    run.dir.mkdir(parents=True)
    run.meta = {"seed": a.seed if a.seed is not None else random.randrange(10**6), "seq": 0}
    svc = run.service()
    u = common.story(svc.stories)
    creation = creation_of(u, a)
    made = await svc.create(a.run, u.id, creation)
    run.meta |= {"game_id": made["game_id"], "story": u.id, "creation": creation, "state": state(made["view"])}
    run.save()
    v = made["view"]
    traits = ", ".join(f"{n}({t})" for t, (n, _) in u.traits.items())
    run.out(f"# {v['story']['title']}\n{v['story']['premise']}\n\n(seed {run.meta['seed']}, 고를 수 있는 기술: {traits})\n\n"
            + screen(v))


async def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    n = sub.add_parser("new")
    n.add_argument("run")
    n.add_argument("--seed", type=int)
    n.add_argument("--approaches")
    n.add_argument("--traits")
    n.add_argument("--story")
    for name in ("say", "pick", "press"):
        p = sub.add_parser(name)
        p.add_argument("run")
        p.add_argument("arg")
    for name in ("cancel", "look", "report"):
        sub.add_parser(name).add_argument("run")
    a = ap.parse_args()
    if a.cmd == "new":
        return await new(a)
    run = Run(a.run)
    if not run.meta:
        raise SystemExit(f"no game in {run.dir}; start one with `new`")
    if a.cmd == "look":
        print(screen(await run.service().view(run.meta["game_id"])))
    elif a.cmd == "report":
        m = measure(sorted((run.dir / "saves").glob("*.json")), load_all(common.checkout() / "scenarios"), time.time())
        run.out("## 지표 (docs/fun.md 4)\n" + table(m))
    elif (await run.service().view(run.meta["game_id"]))["ending"]:
        raise SystemExit("the game is over; run `report`")
    elif a.cmd == "say":
        await send(run, {"text": a.arg}, a.arg)
    elif a.cmd in ("pick", "cancel"):
        c = (await run.service().view(run.meta["game_id"]))["card"]
        if c is None:
            raise SystemExit("no card is open")
        if a.cmd == "cancel":
            await send(run, {"card": c["id"], "cancel": True}, "(카드 닫기)")
        else:
            o = c["options"][int(a.arg) - 1]
            await send(run, {"card": c["id"], "pick": o["id"]}, f"(고름: {o['label']})")
    elif a.cmd == "press":
        v = await run.service().view(run.meta["game_id"])
        if a.arg.startswith("g") and v["card"]:
            sys.exit("성장은 열린 카드를 고르거나 닫은 뒤에 고를 수 있습니다.")
        b = v["growth"][int(a.arg[1:]) - 1] if a.arg.startswith("g") else v["buttons"][int(a.arg) - 1]
        await send(run, {"action": b["action"]}, f"(버튼: {b['label']})")


if __name__ == "__main__":
    asyncio.run(main())
