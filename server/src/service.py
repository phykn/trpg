import asyncio
import hashlib
import re
from datetime import UTC, datetime
from pathlib import Path

from .guide import make_guide
from .models import ModelUnavailable
from .narrate import make_jobs
from .rules.act import Refused, act
from .rules.state import apply_turn, start_state
from .save import SaveError, make_save, read_save, write_save
from .view import make_feed, make_view


class Missing(LookupError):
    pass


class Conflict(ValueError):
    def __init__(self, view):
        super().__init__("conflict")
        self.view = view


class Broken(ValueError):
    def __init__(self, reason):
        super().__init__(reason)
        self.reason = reason


class TextJob:
    def __init__(self):
        self.events = []
        self.changed = asyncio.Condition()

    async def add(self, event):
        async with self.changed:
            self.events.append(event)
            self.changed.notify_all()

    async def follow(self):
        seen = 0
        while True:
            async with self.changed:
                await self.changed.wait_for(lambda seen=seen: len(self.events) > seen)
                new = self.events[seen:]
            seen += len(new)
            for event in new:
                yield event
            if new[-1]["type"] in ("done", "error"):
                return


class GameService:
    def __init__(self, stories, save_dir, interpreter, narrator):
        self.stories = stories
        self.save_dir = Path(save_dir)
        self.interpreter = interpreter
        self.narrator = narrator
        self.games = {}
        self.locks = {}
        self.texts = {}
        self.tasks = set()

    def list_stories(self):
        return [{"story": name, "title": s.head.title, "intro": s.head.intro} for name, s in self.stories.items()]

    def create(self, request_id, story_name):
        digest = hashlib.sha256(request_id.encode()).hexdigest()
        game = digest[:16]
        if (self.save_dir / f"{game}.json").exists():
            data, story, state = self.load(game)
            if data["head"]["story"] != story_name:
                raise Conflict(make_view(story, state)[0])
            return game, make_view(story, state)[0]
        if story_name not in self.stories:
            raise Missing(f"no story {story_name!r}")
        story = self.stories[story_name]
        data = make_save(game, story, int(digest[16:24], 16), datetime.now(UTC).isoformat(timespec="seconds"))
        write_save(self.save_dir / f"{game}.json", data)
        self.games[game] = (data, story, data["state"])
        return game, make_view(story, data["state"])[0]

    def load(self, game):
        if game not in self.games:
            path = self.save_dir / f"{game}.json"
            if not re.fullmatch(r"[0-9a-f]{16}", game) or not path.is_file():
                raise Missing(f"no game {game!r}")
            try:
                self.games[game] = read_save(path)
            except SaveError as exc:
                raise Broken(exc.reason) from None
        return self.games[game]

    def show(self, game):
        _, story, state = self.load(game)
        return make_view(story, state)[0]

    def list_turns(self, game, start):
        data, story, state = self.load(game)
        return [self.make_result(story, state, turn, False) for turn in data["turns"] if turn["turn"] >= start]

    def stream_text(self, game, n):
        data, _, _ = self.load(game)
        if not 1 <= n <= len(data["turns"]):
            raise Missing(f"no turn {n}")
        return self.follow_text(game, n)

    async def follow_text(self, game, n):
        texts = self.load(game)[0]["turns"][n - 1]["text"]
        if texts is not None:
            for slot, text in enumerate(texts):
                yield {"type": "start", "slot": slot}
                yield {"type": "delta", "slot": slot, "text": text["text"]}
                yield {"type": "end", "slot": slot}
            yield {"type": "done"}
            return
        if (game, n) not in self.texts:
            self.texts[game, n] = TextJob()
            task = asyncio.create_task(self.write_text(game, n, self.texts[game, n]))
            self.tasks.add(task)
            task.add_done_callback(self.tasks.discard)
        async for event in self.texts[game, n].follow():
            yield event

    async def write_text(self, game, n, job):
        try:
            data, story, _ = self.load(game)
            state = start_state(story, data["head"]["seed"])
            for turn in data["turns"][:n - 1]:
                state = apply_turn(story, state, turn["changes"])
            turn = data["turns"][n - 1]
            texts = []
            for slot, spec in enumerate(make_jobs(story, state, apply_turn(story, state, turn["changes"]), turn)):
                await job.add({"type": "start", "slot": slot})
                async for event in self.narrator.write(spec):
                    if event["type"] == "result":
                        texts.append({"text": event["text"], "checks": event["checks"]})
                    else:
                        await job.add({**event, "slot": slot})
                await job.add({"type": "end", "slot": slot})
            async with self.locks.setdefault(game, asyncio.Lock()):
                data, story, state = self.load(game)
                turns = [*data["turns"][:n - 1], {**data["turns"][n - 1], "text": texts}, *data["turns"][n:]]
                data = {**data, "turns": turns}
                write_save(self.save_dir / f"{game}.json", data)
                self.games[game] = (data, story, state)
            await job.add({"type": "done"})
        except ModelUnavailable:
            await job.add({"type": "error"})
        finally:
            self.texts.pop((game, n), None)

    async def command(self, game, body):
        self.load(game)
        async with self.locks.setdefault(game, asyncio.Lock()):
            return await self.run_command(game, body)

    async def run_command(self, game, body):
        data, story, state = self.load(game)
        request = {k: v for k, v in body.items() if k != "request_id"}
        view, acts = make_view(story, state)
        for turn in data["turns"]:
            if turn["receipt"] == body["request_id"]:
                if turn["request"] != request:
                    raise Conflict(view)
                return self.make_result(story, state, turn)
        if body["revision"] != state["turn"]:
            raise Conflict(view)
        try:
            action = self.read_request(story, state, acts, body)
            heard = await self.interpret(story, state, action)
            result = act(story, state, action, heard)
        except Refused as exc:
            return {"kind": "refused", "code": exc.code, "turn": None, "said": None, "feed": [], "text": False,
                    "view": view}
        turn = {"turn": result["state"]["turn"], "receipt": body["request_id"], "request": request, "action": action,
                "heard": heard, "dice": result["dice"], "changes": result["changes"], "happened": result["happened"],
                "talk": result["talk"], "text": None}
        past = [{**t["guide"], "turn": t["turn"]} for t in data["turns"] if t.get("guide")]
        turn["guide"] = make_guide(story, state, result["state"], turn, past)
        data = {**data, "turns": data["turns"] + [turn], "state": result["state"]}
        write_save(self.save_dir / f"{game}.json", data)
        self.games[game] = (data, story, result["state"])
        return self.make_result(story, result["state"], turn)

    def read_request(self, story, state, acts, body):
        book = list(state["notebook"])

        def find_line(line_id):
            if not 1 <= line_id <= len(book):
                raise Refused(f"no line {line_id}", "unknown_line")
            return book[line_id - 1]

        if body.get("do") is not None:
            if body["do"] not in acts:
                raise Refused(f"no act {body['do']!r}", "unknown_act")
            return {**acts[body["do"]], **({"text": body["text"]} if body.get("text") else {})}
        if body.get("text") is not None:
            return {"do": "ask", "text": body["text"]}
        if body.get("read") is not None:
            return {"do": "read", "lines": [find_line(i) for i in body["read"]]}
        answer = {k: None if body["conclude"].get(k) is None else find_line(body["conclude"][k])
                  for k in ("who", "how", "why")}
        if answer["who"] is not None and story.lines[answer["who"]].kind != "사람":
            raise Refused("who is a person", "unknown_line")
        return {"do": "conclude", **answer, "who": answer["who"] and story.lines[answer["who"]].name}

    async def interpret(self, story, state, action):
        playing = state["stats"] is not None and state["conclusion"] is None and state["spent"] < story.head.cells
        if action["do"] != "ask" or not playing:
            return None
        return await self.interpreter.read(story, state, action["text"])

    def make_result(self, story, state, turn, with_view=True):
        ids = {addr: i for i, addr in enumerate(state["notebook"], 1)}
        feed = make_feed(story, turn, ids, [a for a, t in state["notebook"].items() if t == 0])
        result = {"kind": "turn", "turn": turn["turn"], "said": turn["action"].get("text"), "feed": feed,
                  "text": any("slot" in f for f in feed)}
        return {**result, "view": make_view(story, state)[0]} if with_view else result
