import argparse
import json
import os
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[2]
RUNS = ROOT / "qa_test" / "runs"
sys.path.insert(0, str(ROOT / "server"))

from run_api import local_settings

MAX_TEXT = 200   # client/components/game/InputBar.tsx maxLength
GROUPS = {"places": "곳", "people": "사람", "items": "물건", "seen": "본 것", "heard": "들은 말"}
VERDICTS = {"solved": "다 밝혔다", "who_only": "누구인지는 밝혔다", "wrong": "엉뚱한 사람을 짚었다", "unsolved": "밝히지 못했다"}
ANSWERS = {"hit": "맞힘", "miss": "틀림", "blank": "비움"}
MISSED = {"lies": "깨지 못한 거짓말", "held": "풀지 못한 꺼림", "locks": "열지 못한 잠김"}


class Run:
    def __init__(self, name):
        self.dir = RUNS / name
        self.path = self.dir / "play.json"
        self.state = json.loads(self.path.read_text(encoding="utf-8")) if self.path.exists() else {}
        cfg = local_settings()
        base = os.environ.get("PLAY_API", f"http://{cfg.host}:{cfg.port}")   # the QA server (qa/tester/api.sh)
        self.http = httpx.Client(base_url=base, timeout=300, auth=(cfg.basic_auth_user, cfg.basic_auth_pass))
        self.out = []

    def show(self, text=""):
        self.out.append(text)
        print(text)

    def save(self, command):
        self.dir.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.state, ensure_ascii=False, indent=1), encoding="utf-8")
        with (self.dir / "transcript.md").open("a", encoding="utf-8") as f:
            f.write(f"## {command}\n\n```\n" + "\n".join(self.out) + "\n```\n\n")

    def create(self, story, request_id):
        r = self.http.post("/games", json={"request_id": request_id, "story": story}).raise_for_status()
        self.state = {"game": r.json()["game"], "view": r.json()["view"], "pending": None, "count": 0}

    def send(self, body):
        view = self.state["view"]
        if self.state.get("pending") or self.state.get("text"):
            raise SystemExit("retry first: a command or its text did not arrive")
        self.state["count"] += 1
        self.state["pending"] = {"request_id": f"play{self.state['count']}", "revision": view["revision"], **body}
        self.post()

    def post(self):
        body = self.state["pending"]
        try:
            r = self.http.post(f"/games/{self.state['game']}/commands", json=body)
        except httpx.HTTPError:
            r = None
        if r is None or r.status_code >= 500:   # kept: retry sends the same request id
            self.show("응답을 받지 못했습니다 → retry")
            return
        if r.status_code == 409 and "view" in r.json():
            self.state.update(view=r.json()["view"], pending=None)
            self.show("409: 판이 바뀌어 새로 불러옴")
            return
        if r.status_code >= 400:
            self.state["pending"] = None
            self.show(f"HTTP {r.status_code}: {r.text}")
            return
        result = r.json()
        self.state.update(view=result["view"], pending=None)
        if result["kind"] == "refused":
            self.show(f"거절: {result['code']}")
            return
        self.state["feed"] = {"turn": result["turn"], "said": result["said"], "feed": result["feed"]}
        if result["text"]:
            self.state["text"] = result["turn"]
            self.read_text()
        else:
            self.show_feed({})

    def read_text(self):
        turn, texts, done = self.state["text"], {}, False
        try:
            with self.http.stream("GET", f"/games/{self.state['game']}/turns/{turn}/text") as r:
                for line in r.iter_lines():
                    if not line.strip():
                        continue
                    e = json.loads(line)
                    if e["type"] == "start":
                        texts[e["slot"]] = ""
                    elif e["type"] == "delta":
                        texts[e["slot"]] += e["text"]
                    elif e["type"] == "replace":
                        texts[e["slot"]] = e["text"]
                    done = e["type"] == "done"
        except httpx.HTTPError:
            done = False
        if not done:
            self.show("서술을 받지 못했습니다 → retry")
            return
        self.state["text"] = None
        self.show_feed(texts)

    def show_feed(self, texts):
        turn = self.state["feed"]
        self.show(f"[턴 {turn['turn']}]" + (f" 당신: {turn['said']}" if turn["said"] else ""))
        for item in turn["feed"]:
            if "slot" in item:
                who = item.get("who")
                self.show((f"{who}: " if who else "" if item["kind"] == "text" else f"({item['kind']}) ")
                         + texts.get(item["slot"], ""))
            elif item["kind"] == "note":
                self.show(f"{item['text']}  [줄 {', '.join(map(str, item['lines']))}]")
            else:
                self.show(item["text"] + (" (성공)" if item.get("won") else " (실패)" if "won" in item else ""))

    def show_view(self):
        v = self.state["view"]
        if v["stage"] == "start":
            self.show(v["start"]["intro"])
            return
        if v["stage"] == "over":
            e = v["ending"]
            self.show(f"=== {VERDICTS[e['verdict']]} === " + " · ".join(
                f"{q} {ANSWERS[e['answers'][k]]}" for k, q in (("who", "누가"), ("how", "어떻게"), ("why", "왜"))))
            for key, label in MISSED.items():
                self.show(f"{label}: {' / '.join(e['missed'][key]) or '-'}")
            return
        self.show(f"\n[{v['place']['name']}] {v['time']['text']} · 수첩 {v['badge']}"
                 + (" · 마지막 턴들" if v["time"]["last"] else ""))
        if v["stage"] == "play" and v["place"]["look"]:
            self.show(f"둘러보기: {v['place']['look']['id']}" + ("" if v["place"]["looked"] else " 안 둘러봄"))
        if v["people"]:
            self.show("사람: " + "  ".join(f"{p['act'] or '-'} {p['name']}{'*' if p['partner'] else ''}"
                                         for p in v["people"]))
        if v["stage"] == "play" and v["place"]["moves"]:
            self.show("갈 곳: " + "  ".join(f"{m['id']} {m['name']} {m['cells']}턴{' 안 가 봄' if m['unvisited'] else ''}"
                                          for m in v["place"]["moves"]))
        new = {g: len([line for line in lines if line["new"]]) for g, lines in v["notebook"].items()}
        self.show("새 줄: " + ", ".join(f"{GROUPS[g]} {n}" for g, n in new.items() if n) if any(new.values()) else "새 줄: -")
        if v["stage"] == "closing":
            self.show(f"턴이 다 됐다. 결론: 누가 {v['conclude']['who']}, 단서 {v['conclude']['clues']}")

    def pick_lines(self, which):
        lines = [(g, line) for g, group in self.state["view"]["notebook"].items() for line in group]
        picked = [(g, line) for g, line in lines if (str(line["id"]) == which or GROUPS.get(g) == which)]
        if not picked and which in GROUPS.values():
            raise SystemExit(f"수첩에 아직 {which} 줄이 없습니다")
        if not picked:
            raise SystemExit(f"{which}: a line id or one of {', '.join(GROUPS.values())}")
        return picked

    def show_lines(self, which, new):
        for g, line in self.pick_lines(which):
            marks = f"  ({', '.join(line['marks'])})" if line["marks"] else ""
            struck = "~~" if line["struck"] else ""
            self.show(f"{line['id']}. [{GROUPS[g]}] {struck}{line['text']}{struck}{marks}{' 새' if line['id'] in new else ''}")
            for act in line["acts"]:
                self.show(f"     {act['id']} {act['label']}")


def main():
    parser = argparse.ArgumentParser(description="Play a game from the shell through the API of a running "
                                                 "`run_api.py --local`; everything goes to qa_test/runs/<run>/.")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("new", help="a new game; picks +2 and +1 and shows the opening")
    p.add_argument("run")
    p.add_argument("--story", default="dawn")
    p.add_argument("--plus2", default="charm")
    p.add_argument("--plus1", default="wit")
    p = sub.add_parser("say", help="ask the partner, or say something with no one chosen")
    p.add_argument("run")
    p.add_argument("text")
    p = sub.add_parser("do", help="an act id from the screen or a line, with an optional sentence")
    p.add_argument("run")
    p.add_argument("act")
    p.add_argument("text", nargs="?")
    p = sub.add_parser("read", help="open a notebook group (곳, 사람, 물건, 본 것, 들은 말) or one line by id")
    p.add_argument("run")
    p.add_argument("which")
    p = sub.add_parser("conclude", help="hand in the conclusion; a question left out stays blank")
    p.add_argument("run")
    for q in ("who", "how", "why"):
        p.add_argument(f"--{q}", type=int)
    p.add_argument("--blank", action="store_true", help="hand in with all three blank")
    sub.add_parser("retry", help="send again the command or ask again for the text that did not arrive").add_argument("run")
    sub.add_parser("screen", help="reload the game and show the screen").add_argument("run")
    args = parser.parse_args()
    run = Run(args.run)
    if args.cmd != "new" and "game" not in run.state:
        raise SystemExit(f"no game in {run.dir}: start with `new {args.run}`")
    if args.cmd == "new":
        if run.path.exists():
            raise SystemExit(f"{run.dir} already has a game")
        run.create(args.story, f"{args.run}-new")
        act = next(a for a in run.state["view"]["start"]["acts"] if (a["plus2"], a["plus1"]) == (args.plus2, args.plus1))
        run.show_view()
        run.send({"do": act["id"]})
    elif args.cmd == "say":
        run.send({"text": args.text[:MAX_TEXT]})   # the input box takes no more
    elif args.cmd == "do":
        person = next((p for p in run.state["view"]["people"] if p["act"] == args.act), None)
        if person:   # the phone's people row takes no text: face, then say it
            run.send({"do": args.act})
            run.show(f"({'마주하기 풀림' if person['partner'] else '마주함'}: {person['name']})")
            if args.text:
                run.send({"text": args.text[:MAX_TEXT]})
        else:
            run.send({"do": args.act, **({"text": args.text[:MAX_TEXT]} if args.text else {})})
    elif args.cmd == "read":   # read first: the act ids belong to the view after it
        new = [line["id"] for _, line in run.pick_lines(args.which) if line["new"]]
        if new and run.state["view"]["stage"] in ("play", "closing"):
            run.send({"read": new})
        run.show_lines(args.which, new)
    elif args.cmd == "conclude":
        if not args.blank and all(getattr(args, q) is None for q in ("who", "how", "why")):
            raise SystemExit("누가, 어떻게, 왜가 모두 비어 있습니다. 이대로 내려면 --blank")   # the phone asks twice too
        run.send({"conclude": {q: getattr(args, q) for q in ("who", "how", "why")}})
    elif args.cmd == "retry":
        if run.state.get("pending"):
            run.post()
        elif run.state.get("text"):
            run.read_text()
        else:
            run.show("nothing to retry")
    else:
        run.state["view"] = run.http.get(f"/games/{run.state['game']}").raise_for_status().json()
    if args.cmd != "read":
        run.show_view()
    run.save(" ".join(sys.argv[1:]))


if __name__ == "__main__":
    main()
