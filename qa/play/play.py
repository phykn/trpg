import argparse
import asyncio
import json
import random
import sys
import time
import traceback
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import common
from run_api import create_app, local_settings
from src.fun import measure, table
from src.locale import ko
from src.narrate import change_lines
from src.story.validate import load_all

# The client's own strings (client/locale/ko.ts), so the shell says what the web screen says.
WEB = {
    "hero": "주인공", "highRisk": "되돌릴 수 없는 대가가 걸려 있습니다", "crisis": "위기",
    "stuck": "응답을 받지 못했습니다.", "narrationFailed": "서술을 받지 못했습니다.",
    "conflict": "게임 상태가 바뀌어 새로 불러왔습니다.", "blocked": "이 판은 더 이어할 수 없습니다.",
    "placeholder": "무엇을 할까요?", "choose": "고른다", "whereTo": "어디로 갈까요?", "leave": "간다",
    "thanks": "덕분에", "because": "때문에", "guarded": "실패 대가 줄임", "forced": "무리해서", "tagLife": {"scene": "이번 장면", "chapter": "이번 장"},
}


def batchim(word: str) -> int | None:
    c = ord(word[-1]) - 0xAC00
    return c % 28 if 0 <= c <= 11171 else None


def eul(word: str) -> str:
    return word + ("을" if batchim(word) else "를")


def ro(word: str) -> str:
    b = batchim(word)
    return word + ("으로" if b and b != 8 else "로")


def signed(n: int) -> str:
    return f"+{n}" if n > 0 else f"−{-n}" if n < 0 else "±0"


def chip(m: dict) -> str:
    """A spent reliance lowers a fail's cost, not the total; the web says so instead of ±0."""
    return f"· {WEB['guarded']}" if m["kind"] == "guard" else signed(m["value"])


class Run:
    def __init__(self, name: str):
        self.dir = common.RUNS / name
        self.meta_path = self.dir / "play.json"
        self.meta = json.loads(self.meta_path.read_text()) if self.meta_path.exists() else {}

    def save(self):
        self.meta_path.write_text(json.dumps(self.meta, ensure_ascii=False, indent=1))

    def out(self, text: str, record: dict | None = None):
        print(text, flush=True)
        with (self.dir / "transcript.md").open("a") as f:
            f.write(text + "\n\n")
        if record is not None:
            with (self.dir / "log.jsonl").open("a") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")


class Api:
    """client/services/api.ts against the app `run_api.py --local` serves, run in this process."""

    def __init__(self, http: httpx.AsyncClient, stories: dict):
        self.http = http
        self.stories = stories      # only to word the change lines the web draws as icons

    async def call(self, path: str, body: dict | None = None) -> tuple[int, dict]:
        r = await (self.http.get(path) if body is None else self.http.post(path, json=body))
        try:
            return r.status_code, r.json()
        except ValueError:
            return r.status_code, {}

    async def stream(self, path: str) -> list[dict]:
        """The events of one NDJSON stream. As in the client, a failed request, a dropped stream or a line that is not
        JSON ends in an error without message, and so does a stream that ends without `done` or `error`."""
        events = []
        try:
            async with self.http.stream("GET", path) as r:
                if r.is_success:
                    async for line in r.aiter_lines():
                        if line.strip():
                            events.append(json.loads(line))
        except (httpx.HTTPError, ValueError):
            pass
        if not any(e.get("type") in ("done", "error") for e in events):
            events.append({"type": "error"})
        return events


@asynccontextmanager
async def connect(run: Run):
    app, _, _ = create_app(local=True)
    # The server run_api builds, but with this run's saves and dice seed so a game can be replayed.
    app.state.service.save_dir = run.dir / "saves"
    app.state.service.seeds = lambda: run.meta["seed"]

    async def served(scope, receive, send):
        try:
            await app(scope, receive, send)
        except Exception:
            traceback.print_exc()           # what uvicorn would log; the client only sees the 500
            raise

    cfg = local_settings()
    transport = httpx.ASGITransport(app=served, raise_app_exceptions=False)
    async with app.router.lifespan_context(app), httpx.AsyncClient(
            transport=transport, base_url="http://api", auth=(cfg.basic_auth_user, cfg.basic_auth_pass)) as http:
        yield Api(http, app.state.service.stories)


def tags(items: list[dict]) -> str:
    """Tags of one kind, life and name once, with when they end, as the web screen draws them (Row.tsx TagItems)."""
    names = dict.fromkeys((t["kind"], t["life"], t["name"]) for t in items)
    life = WEB["tagLife"]
    return ", ".join(name + (f" · {life[x]}" if x in life else "") for _, x, name in names)


def rename(v: dict, named: list[dict]) -> dict:
    """client/logic/useGame.ts renameTags: tag names the narration's `done` gave."""
    if not named:
        return v
    by = {(t["owner"], t["slot"]): t["name"] for t in named}
    return {**v,
            "player": {**v["player"], "tags": [{**t, "name": by.get(("player", t["slot"]), t["name"])}
                                               for t in v["player"]["tags"]]},
            "scene": {**v["scene"], "tags": [{**t, "name": by.get((t.get("owner", ""), t["slot"]), t["name"])}
                                             for t in v["scene"]["tags"]]}}


def state(v: dict) -> list[str]:
    """What the screen's rows and the hero panel show (Header, Clocks, Scene, Self)."""
    s, me, j = v["scene"], v["player"], v["journal"]
    lines = [f"[{v['chapter']['k']}장 {v['chapter']['title']}] 목표: {v['chapter']['aim']}"]
    if v["ending"]:
        return lines + [hero(me)]
    lines.append(f"장소: {s['place']['name']}")
    if s["people"]:
        lines.append("사람: " + ", ".join(p["name"] + (" (동행)" if p["with"] else "") for p in s["people"]))
    if s["things"]:
        lines.append("물건: " + ", ".join(t["name"] for t in s["things"]))
    for o in s["obstacles"]:
        # A single box is never drawn; an overcome obstacle stays, checked (ui.md 2.1).
        boxes = " ✓" if o["fill"] >= o["boxes"] else f" {o['fill']}/{o['boxes']}" if o["boxes"] > 1 else ""
        lines.append(f"장애물: {o['name']}{boxes}")
    if s["exits"]:
        lines.append("길: " + ", ".join(e["name"] + (" (막힘)" if e["blocked"] else "") for e in s["exits"]))
    if s["tags"]:
        lines.append("표시: " + tags(s["tags"]))
    crisis = {c["id"] for r in (v["last"] or {}).get("steps", []) for c in r["changes"] if c["kind"] == "crisis"}
    for c in v["clocks"]:
        # The next box of a deadline, threat or fork fills by the scene's time spent (ui.md 2.1).
        part = f", 다음 칸 {me['beats']}/{me['beats_max']}" if c["kind"] != "clock" and c["fill"] < c["boxes"] else ""
        lines.append(f"시계: {c['name']} {c['fill']}/{c['boxes']}{part}"
                     + (f" {WEB['crisis']}" if c["id"] in crisis else ""))
    lines.append(hero(me))
    for o in j["owes"]:
        lines.append(f"빚: {o['name']}에게 " + (o["promise"] if o["kind"] == "promise" else "신세"))
    here = [b for b in j["beliefs"] if b["here"]]
    if here:
        lines.append("아는 것: " + " / ".join(b["text"] + ("(씀)" if b["spent"] else "") for b in here))
    return lines


def hero(me: dict) -> str:
    return (f"나: {me['name'] or WEB['hero']}, 체력 {me['wound_boxes'] - me['wounds']}/{me['wound_boxes']}, "
            + ", ".join(f"{a['name']} {a['value']}" for a in me["approaches"])
            + "".join(f", {t['name']}" + ("(씀)" if t["spent"] else "") for t in me["traits"])
            + (", 가진 것: " + ", ".join(t["name"] + ("(씀)" if t["spent"] else "") for t in me["things"])
               if me["things"] else "")
            + (", 표시: " + tags(me["tags"]) if me["tags"] else ""))


def hint(s: dict) -> str:
    """client/screens/Play.tsx hint: the empty input bar asks about the scene's first target."""
    open_ = next((o for o in s["obstacles"] if o["fill"] < o["boxes"]), None)
    if open_:
        return f"{eul(open_['name'])} 어떻게 할까요?"
    if s["people"]:
        return f"{s['people'][0]['name']}에게 무엇을 할까요?"
    if s["things"]:
        return f"{eul(s['things'][0]['name'])} 어떻게 할까요?"
    return WEB["placeholder"]


def screen(v: dict, before: list[str] | None = None) -> str:
    """The state lines marked `+` when new and `-` when gone since `before`, then what can be done."""
    now = state(v)
    lines = now if before is None or v["ending"] else \
        [("+ " if x not in before else "") + x for x in now] + [f"- {x}" for x in before if x not in now]
    if v["card"]:
        lines.append(card(v["card"]))
    elif v["growth"]:
        # GrowthCard tiles; closing it ("later") leaves the input bar, so a sentence can follow instead.
        lines.append("성장:")
        lines += [f"  g{i}) {g['name']}" + (f" — {g['text']}" if g.get("text") else "") for i, g in enumerate(v["growth"], 1)]
    if not v["card"] and not v["ending"]:
        lines.append(f"입력창: {hint(v['scene'])}")
    return "\n".join(lines)


def card(c: dict) -> str:
    if c["kind"] == "roll":
        return roll_card(c)
    if c["kind"] == "confirm":
        o = c["options"][0]
        return "\n".join([f"카드(confirm): ⚠ {o['label']}", *(f"  · {e}" for e in o.get("effects") or []),
                          f"  1) {WEB['choose']}"])
    if c["kind"] == "move" and len(c["options"]) == 1:
        o = c["options"][0]
        return "\n".join([f"카드(move): {ro(o['label'])} 갈까요?", *([f"  {' · '.join(o['effects'])}"] if o.get("effects") else []),
                          f"  1) {WEB['leave']}"])
    title = c.get("question") if c["kind"] == "clarify" else WEB["whereTo"]
    lines = [f"카드({c['kind']}): {title}"]
    for i, o in enumerate(c["options"], 1):
        # The move the sentence chose is the gold row (MoveCard primary).
        lines.append(f"  {i}) {o['label']}" + (f" — {' · '.join(o['effects'])}" if o.get("effects") else "")
                     + (" *" if c["kind"] == "move" and o["id"] == c.get("selected") else ""))
    return "\n".join(lines)


def roll_card(c: dict) -> str:
    """What RollCard.tsx draws before the roll: the step and its target's boxes, the target number from the chosen
    option's preview, the fixed modifiers, and one row per help with the chosen one marked `*`. The web draws no row
    for the server's "기대지 않음"; it is what rolls when no help is chosen."""
    plain = next((o for o in c["options"] if "rely=" not in o["id"]), c["options"][-1])
    chosen = next((o for o in c["options"] if o["id"] == c.get("selected")), plain)
    pv = chosen["preview"]
    step = c["plan"]["step"] or {}
    target = step.get("target") or {}
    boxes = f" {target['fill']}/{target['boxes']}" if (target.get("boxes") or 0) > 1 else ""
    fixed = "".join(f", {m['label']} {signed(m['value'])}" for m in pv["mods"] if m["value"] and m["kind"] != "help")
    lines = [f"카드(roll): {step.get('label', '')}{boxes}",
             f"  목표 {pv['dc']}" + (f" ⚠ {WEB['highRisk']}" if pv["risk"] == "high" else "") + fixed]
    for i, o in enumerate(c["options"], 1):
        rely = next((m for m in o["preview"]["mods"] if m["kind"] in ("help", "guard") and m["label"] == o["label"]), None)
        # the web draws the forced twins as one "무리해서" switch over the same list
        lines.append(f"  {i}) {o['label']}" + (f" · {WEB['forced']}" if o.get("forced") else "") + (f" {chip(rely)}" if rely else "")
                     + (f" · {o['note']}" if o.get("note") else "") + (" *" if o is chosen else ""))
    return "\n".join(lines)


def steps(u, res: dict) -> list[str]:
    """Each step and what it changed. A rolled step reads as the roll card's reveal: the dice, the modifiers with the
    decisive ones marked, the total against the target and the result; a blocked step rolls no dice."""
    lines = []
    for r in res["steps"]:
        head = f"- {r['label']}"
        if r["roll"] and r["result"] != "blocked":
            mods = "".join(f", {m['label']} {chip(m)}"
                           + (f" {WEB['because'] if m['kind'] == 'hinder' else WEB['thanks']}" if i in r["decisive"] else "")
                           for i, m in enumerate(r["mods"]))
            head += f" — 2d6 {r['roll']['d1']}+{r['roll']['d2']}{mods} = {r['total']} / {r['dc']}"
        if r["result"] not in ("none", None):
            head += f" → {ko.RESULTS[r['result']]}"
        lines.append(head)
        lines += [f"    {x}" for x in change_lines(u, r["changes"])]
    return lines


def recap_of(steps_: list[dict], v: dict) -> int | None:
    """client/logic/useGame.ts recapChapter: the chapter that just closed."""
    for r in steps_:
        for c in r["changes"]:
            if c["kind"] == "chapter":
                return c["from"]
            if c["kind"] == "ending":
                return v["chapter"]["k"]
    return None


def told(events: list[dict]) -> tuple[str | None, list[dict], dict | None]:
    """The accepted text, the tag names of `done`, and the error, if any."""
    text = next((e["text"] for e in reversed(events) if e["type"] == "text"), None)
    named = next((e.get("tags", []) for e in events if e["type"] == "done"), [])
    return text, named, next((e for e in events if e["type"] == "error"), None)


async def narrate(api: Api, run: Run, n: int, k: int | None, v: dict, lines: list[str], log: dict) -> dict:
    """useGame.ts narrate: the turn's narration, then the closed chapter's recap. A failure locks commands until
    `retry` asks again."""
    gid = run.meta["game_id"]
    t0 = time.monotonic()
    events = log["narration"] = await api.stream(f"/games/{gid}/turns/{n}/narration")
    text, named, error = told(events)
    if text is not None:
        lines.append(f"서술: {text}")
    lines.append(f"(서술 {int((time.monotonic() - t0) * 1000)}ms)")
    v = rename(v, named)
    if error is None and k is not None:
        events = log["recap"] = await api.stream(f"/games/{gid}/chapters/{k}/recap")
        text, _, error = told(events)
        if text is not None:
            lines.append(f"장 요약({k}장): {text}")
            run.meta.setdefault("recaps", {})[str(k)] = text
    if error is not None:
        lines.append(f"서술 오류: {WEB['narrationFailed']}" + (f" ({error['message']})" if error.get("message") else "")
                     + " `retry`로 다시 받습니다.")
    run.meta["unnarrated"] = None if error is None else {"turn": n, "recap": k}
    return v


async def ending(api: Api, run: Run, v: dict) -> list[str]:
    """Ending.tsx: the ending's title, a recap per chapter, and the fork choices."""
    lines = [f"=== 결말: {v['ending']['title']} ==="]
    known = run.meta.get("recaps", {})
    for k in sorted({*v["recaps"], *map(int, known)}):
        if str(k) not in known:
            text, _, _ = told(await api.stream(f"/games/{run.meta['game_id']}/chapters/{k}/recap"))
            if text is not None:
                known[str(k)] = text
        lines.append(f"{k}장: {known.get(str(k), '')}")
    lines += [f"{c['chapter']}장 {c['name']}" for c in v["journal"]["choices"]]
    run.meta["recaps"] = known
    return lines + ["게임이 끝났습니다. 이제 report를 돌리세요."]


async def adopt(api: Api, run: Run) -> dict:
    """A reload: the saved game as the server has it."""
    status, v = await api.call(f"/games/{run.meta['game_id']}")
    if status != 200:
        raise SystemExit(f"HTTP {status}: {v.get('reason') or WEB['blocked']}")
    run.meta["view"] = v
    return v


async def send(api: Api, run: Run, body: dict, said: str):
    """useGame.ts command: a fresh request id and the revision of the view on screen."""
    v = run.meta["view"]
    run.meta["commands"] = run.meta.get("commands", 0) + 1
    run.meta["pending"] = {"n": run.meta["commands"], "said": said,
                           "body": {"request_id": uuid.uuid4().hex, "revision": v["revision"], **body}}
    run.save()                          # a command that gets no answer is resent as it was (`retry`)
    await dispatch(api, run)


async def dispatch(api: Api, run: Run):
    """useGame.ts handle and fail: adopt what the server answered, reveal and narrate the steps."""
    p = run.meta["pending"]
    t0 = time.monotonic()
    status, res = await api.call(f"/games/{run.meta['game_id']}/commands", p["body"])
    ms = int((time.monotonic() - t0) * 1000)
    run.meta["pending"] = None
    lines = [f"## {p['n']}. {p['said']}"]
    log = {"command": p["n"], "said": p["said"], "ms": ms, "status": status, "request": p["body"], **res}
    v = run.meta["view"]
    if status == 200:
        lines.append(f"(해석 {ms}ms)")
        if res["kind"] == "refused":
            lines.append(f"거절: {res['reason']}")
        v = res["view"]
        lines += steps(api.stories[run.meta["story"]], res)
        if res["steps"] and res["turn"] is not None:
            v = await narrate(api, run, res["turn"], recap_of(res["steps"], v), v, lines, log)
    else:
        lines.append(f"(HTTP {status})")
        if status == 409 and "view" in res:
            v = res["view"]
            lines.append(f"알림: {WEB['conflict']}")
        elif status == 409:
            lines.append(WEB["blocked"])
        elif res.get("reason"):
            lines.append(f"알림: {res['reason']}")
    run.meta["view"] = v
    lines.append(await panel(api, run, v))
    run.meta["state"] = state(v)
    run.save()
    run.out("\n".join(lines), log)


async def panel(api: Api, run: Run, v: dict, before: bool = True) -> str:
    text = screen(v, run.meta.get("state") if before else None)
    if v["ending"] and not run.meta.get("unnarrated"):
        text += "\n" + "\n".join(await ending(api, run, v))
    return text


async def retry(api: Api, run: Run):
    if run.meta.get("pending"):
        run.meta["pending"]["said"] += " (다시 보냄)"
        return await dispatch(api, run)
    u = run.meta.get("unnarrated")
    if not u:
        raise SystemExit("nothing to retry")
    lines, log = [f"## {run.meta['commands']}. (서술 다시 받기)"], {"command": run.meta["commands"], "retry": u}
    v = await narrate(api, run, u["turn"], u["recap"], run.meta["view"], lines, log)
    run.meta["view"] = v
    lines.append(await panel(api, run, v))
    run.meta["state"] = state(v)
    run.save()
    run.out("\n".join(lines), log)


def creation_of(story: dict, a) -> dict:
    """Start.tsx: an empty name is the hero."""
    if a.approaches:
        ap = {k: int(x) for k, x in (kv.split("=") for kv in a.approaches.split(","))}
    else:
        ap = dict(zip((x["id"] for x in story["approach_names"]), sorted(story["approaches"], reverse=True), strict=True))
    traits = a.traits.split(",") if a.traits else [t["id"] for t in story["traits"]][:story["pick"]]
    return {"name": a.name.strip() or WEB["hero"], "approaches": ap, "traits": traits}


async def new(a):
    run = Run(a.run)
    if run.meta:
        raise SystemExit(f"{run.dir} exists; pick another RUN")
    run.dir.mkdir(parents=True, exist_ok=True)
    run.meta = {"seed": a.seed if a.seed is not None else random.randrange(10**6)}
    async with connect(run) as api:
        _, catalog = await api.call("/stories")
        story = common.story({s["id"]: s for s in catalog})
        creation = creation_of(story, a)
        status, made = await api.call("/games", {"request_id": uuid.uuid4().hex, "story": story["id"], "creation": creation})
        if status != 200:
            raise SystemExit(f"HTTP {status}: {made}")
        v = made["view"]
        run.meta |= {"game_id": made["game_id"], "story": story["id"], "creation": creation, "view": v, "state": state(v)}
        run.save()
        traits = ", ".join(f"{t['name']}({t['id']})" for t in story["traits"])
        run.out(f"# {v['story']['title']}\n{v['story']['premise']}\n\n(seed {run.meta['seed']}, 고를 수 있는 기술: {traits})\n\n"
                + screen(v))


async def main():
    ap = argparse.ArgumentParser(formatter_class=argparse.RawDescriptionHelpFormatter, description="""\
Play one game turn by turn from the shell, through the same API and on the same screen as the web client.

  python play.py new RUN [--seed N] [--approaches force=1,finesse=2,wits=1,charm=0] [--traits a,b] [--name 이름] [--story ID]
  python play.py say RUN "문장"        # a sentence, as typed into the game
  python play.py pick RUN N            # card option N (1 = first)
  python play.py cancel RUN            # close the card
  python play.py press RUN gN          # growth N
  python play.py retry RUN             # resend a command that got no answer, or ask again for narration that failed
  python play.py look RUN              # the screen again
  python play.py report RUN            # fun.md metrics for this game

Each run lives in qa_test/runs/RUN/: saves/ (the game), transcript.md (what the player saw), log.jsonl (responses).
""")
    sub = ap.add_subparsers(dest="cmd", required=True)
    n = sub.add_parser("new")
    n.add_argument("run")
    n.add_argument("--seed", type=int)
    n.add_argument("--approaches")
    n.add_argument("--traits")
    n.add_argument("--name", default="")
    n.add_argument("--story")
    for name in ("say", "pick", "press"):
        p = sub.add_parser(name)
        p.add_argument("run")
        p.add_argument("arg")
    for name in ("cancel", "retry", "look", "report"):
        sub.add_parser(name).add_argument("run")
    a = ap.parse_args()
    if a.cmd == "new":
        return await new(a)
    run = Run(a.run)
    if not run.meta:
        raise SystemExit(f"no game in {run.dir}; start one with `new`")
    if a.cmd == "report":
        m = measure(sorted((run.dir / "saves").glob("*.json")), load_all(common.checkout() / "scenarios"), time.time())
        return run.out("## 지표 (docs/fun.md 4)\n" + table(m))
    async with connect(run) as api:
        if a.cmd == "look":
            text = await panel(api, run, await adopt(api, run), before=False)
            run.save()
            locked = f"{WEB['stuck']} `retry`로 같은 명령을 다시 보냅니다." if run.meta.get("pending") else \
                f"{WEB['narrationFailed']} `retry`로 다시 받습니다." if run.meta.get("unnarrated") else ""
            return print(text + (f"\n{locked}" if locked else ""))
        if a.cmd == "retry":
            return await retry(api, run)
        # What the web locks: a command with no answer waits for the same command, a failed narration for its retry.
        if run.meta.get("pending"):
            raise SystemExit(f"{WEB['stuck']} `retry` sends the same command again.")
        if run.meta.get("unnarrated"):
            raise SystemExit(f"{WEB['narrationFailed']} `retry` asks for it again.")
        v = run.meta.get("view") or await adopt(api, run)
        if v["ending"]:
            raise SystemExit("the game is over; run `report`")
        if a.cmd == "say":
            await send(api, run, {"text": a.arg}, a.arg)
        elif a.cmd in ("pick", "cancel"):
            c = v["card"]
            if c is None:
                raise SystemExit("no card is open")
            if a.cmd == "cancel":
                await send(api, run, {"card": c["id"], "cancel": True}, "(카드 닫기)")
            else:
                o = c["options"][int(a.arg) - 1]
                await send(api, run, {"card": c["id"], "pick": o["id"]}, f"(고름: {o['label']})")
        elif a.cmd == "press":
            # The web screen has no suggested buttons (ui.md 2.1: it does not use `view.buttons`); growth is its only one.
            if not a.arg.startswith("g"):
                raise SystemExit("the web screen has no suggested buttons; type a sentence, or press gN for growth")
            if v["card"]:
                raise SystemExit("성장은 열린 카드를 고르거나 닫은 뒤에 고를 수 있습니다.")
            g = v["growth"][int(a.arg[1:]) - 1]
            await send(api, run, {"action": g["action"]}, f"(성장: {g['name']})")


if __name__ == "__main__":
    asyncio.run(main())
