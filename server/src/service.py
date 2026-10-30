from __future__ import annotations

import asyncio
import hashlib
import json
import re
import secrets
import time
from pathlib import Path

from .cards import (
    clarify_card,
    confirm_card,
    joiners,
    left_behind,
    move_card,
    rely_options,
    roll_card,
    ways,
)
from .interpret import names_way, says, unreachable
from .jobs import recap_job, turn_job
from .locale import ko
from .narrate import Job
from .onto.atoms import PLAYER
from .onto.save import Game, SaveError, new_game, rebuild, save
from .onto.universe import CreationError, Universe, check_creation
from .onto.view import observe, record
from .rules.acts import parse
from .rules.candidates import admits
from .rules.resolve import event_of, resolve
from .rules.roll import risk, roll, rolls
from .rules.triggers import ended
from .story.load import StoryError
from .view import (
    action_label,
    chapter_k,
    default_tag_name,
    game_view,
    step_record,
)

GAME_ID = re.compile(r"g_[a-f0-9]{32}")
RECEIPTS = 50


class Missing(LookupError):
    pass


class Incompatible(RuntimeError):
    """A save of another schema or story digest."""


class Conflict(RuntimeError):
    """A stale revision or a request id reused with another body."""

    def __init__(self, view: dict):
        super().__init__("conflict")
        self.view = view


class Invalid(ValueError):
    pass


class Stream:
    """Every request for one narration reads the same events (api.md 4)."""

    def __init__(self):
        self.events: list[dict] = []
        self.done = False
        self.cond = asyncio.Condition()
        self.task: asyncio.Task | None = None    # held so the running narration is not garbage-collected

    async def push(self, *events: dict, done: bool = False) -> None:
        async with self.cond:
            self.events += events
            self.done = self.done or done
            self.cond.notify_all()

    async def read(self):
        i = 0
        while True:
            async with self.cond:
                await self.cond.wait_for(lambda i=i: len(self.events) > i or self.done)
                batch, done = self.events[i:], self.done
            for e in batch:
                yield e
            i += len(batch)
            if done and i >= len(self.events):
                return


async def _cached(entry: dict):
    yield {"type": "text", "text": entry["text"]}
    yield {"type": "done", "tags": [{k: t[k] for k in ("slot", "owner", "name")} for t in entry.get("tags", [])]}


def body_hash(body: dict) -> str:
    rest = {k: v for k, v in body.items() if k != "request_id"}
    return hashlib.sha256(json.dumps(rest, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def fresh_presentation(created: str) -> dict:
    return {"revision": 0, "turns": [], "requests": [], "card": None, "card_seq": 0, "narration": {},
            "recap": {}, "tags": [], "choices": [], "receipts": {}, "created": created, "ending": None,
            "relevance": {}}


class GameService:
    def __init__(self, stories: dict[str, Universe], save_dir: Path, interpreter=None, narrator=None,
                 seeds=lambda: secrets.randbits(63)):
        self.stories = stories
        self.seeds = seeds                      # a game's dice seed (rule.md 3.1); tests pin it
        self.save_dir = save_dir
        self.interpreter = interpreter          # engine.md 3; text is refused without it
        self.narrator = narrator
        self.streams: dict[tuple, Stream] = {}
        self.games: dict[str, tuple[Universe, Game]] = {}
        self.locks: dict[str, asyncio.Lock] = {}

    def path(self, game_id: str) -> Path:
        if not isinstance(game_id, str) or not GAME_ID.fullmatch(game_id):
            raise Missing(game_id)
        return self.save_dir / f"{game_id}.json"

    def lock(self, game_id: str) -> asyncio.Lock:
        self.path(game_id)
        return self.locks.setdefault(game_id, asyncio.Lock())

    async def load(self, game_id: str) -> tuple[Universe, Game]:
        if game_id in self.games:
            return self.games[game_id]
        path = self.path(game_id)
        try:
            text = await asyncio.to_thread(path.read_text, encoding="utf-8")
        except FileNotFoundError:
            raise Missing(game_id) from None
        try:
            data = json.loads(text)
            u = self.stories.get(data.get("story", {}).get("id"))
            if u is None:
                raise SaveError("unknown story")
            g = rebuild(u, data)
        except (SaveError, StoryError, ValueError, KeyError, TypeError, AttributeError) as e:
            raise Incompatible(str(e)) from None
        self.games[game_id] = (u, g)
        return u, g

    async def store(self, u: Universe, g: Game) -> None:
        write = asyncio.create_task(asyncio.to_thread(save, u, g, self.path(g.id)))
        cancelled = False
        while not write.done():
            try:
                await asyncio.shield(write)
            except asyncio.CancelledError:
                cancelled = True            # never release the lock during file I/O
        write.result()
        if cancelled:
            raise asyncio.CancelledError

    def catalog(self) -> list[dict]:
        return [{"id": u.id, "title": u.title, "premise": u.premise, "approaches": list(u.approaches),
                 "approach_names": [{"id": ap, "name": ko.APPROACHES[ap], "hint": ko.APPROACH_HINT[ap]}
                                    for ap in ko.APPROACHES],
                 "traits": [{"id": t, "name": n, "text": x} for t, (n, x) in u.traits.items()], "pick": u.pick}
                for u in self.stories.values()]

    async def create(self, request_id: str, story: str, creation: dict) -> dict:
        game_id = "g_" + hashlib.sha256(request_id.encode()).hexdigest()[:32]
        h = body_hash({"story": story, "creation": creation})
        async with self.lock(game_id):
            try:
                u, g = await self.load(game_id)
            except Missing:
                pass
            else:
                if g.presentation.get("created") != h:
                    raise Conflict(game_view(u, g))
                return {"game_id": game_id, "view": game_view(u, g)}
            u = self.stories.get(story)
            if u is None:
                raise Invalid("unknown story")
            try:
                check_creation(u, creation)
            except CreationError as e:
                raise Invalid(str(e)) from None
            g = new_game(u, game_id, self.seeds(), creation)
            g.presentation = fresh_presentation(h)
            await self.store(u, g)
            self.games[game_id] = (u, g)
            return {"game_id": game_id, "view": game_view(u, g)}

    async def view(self, game_id: str) -> dict:
        async with self.lock(game_id):
            u, g = await self.load(game_id)
            return game_view(u, g)

    async def command(self, game_id: str, body: dict) -> dict:
        async with self.lock(game_id):
            u, g = await self.load(game_id)
            p = g.presentation
            h = body_hash(body)
            receipt = p["receipts"].get(body["request_id"])
            if receipt is not None:
                if receipt["hash"] != h:
                    raise Conflict(game_view(u, g))
                return receipt["response"]
            if body["revision"] != p["revision"]:
                raise Conflict(game_view(u, g))
            try:
                response = await self._command(u, g, body)
                p["receipts"][body["request_id"]] = {"hash": h, "response": response}
                p["receipts"] = dict(list(p["receipts"].items())[-RECEIPTS:])
                await self.store(u, g)
            except BaseException:
                self.games.pop(game_id, None)       # the copy on disk is the truth
                raise
            return response

    def _result(self, u, g, kind, turn=None, steps=(), reason=None) -> dict:
        return {"kind": kind, "turn": turn, "steps": list(steps), "reason": reason, "view": game_view(u, g)}

    def _refused(self, u, g, why: str) -> dict:
        return self._result(u, g, "refused", reason=ko.REFUSED.get(why, why))

    async def _command(self, u: Universe, g: Game, body: dict) -> dict:
        p = g.presentation
        if p.get("ending"):
            return self._refused(u, g, "ended")
        card = p.get("card")
        if "card" in body:
            if card is None or body["card"] != card["id"]:
                return self._refused(u, g, "card")
            if body.get("cancel"):
                p["card"] = None
                p["requests"].append({"kind": "cancel", "card": card["id"]})
                p["revision"] += 1
                return self._result(u, g, "turn")
            if body.get("pick") not in card["options"]:
                return self._refused(u, g, "card")
            if card["kind"] == "clarify":
                plan = [card["resume"][body["pick"]], *card["rest"]]
            elif body["pick"] in card.get("plans", {}):
                plan = [*card["plans"][body["pick"]], *card["rest"]]
            else:
                plan = [{"action": body["pick"], "accepted": True}, *card["rest"]]
            echo = card["public"]["echo"]
            # A card a sentence opened still carries that sentence to the narrator (engine.md 5.1).
            return await self._run(u, g, plan, echo, "card", echo["text"] if card.get("origin") == "text" else None)
        if "action" in body:
            try:
                a = parse(body["action"])
            except ValueError:
                return self._refused(u, g, "candidate")
            if not admits(u, observe(u, g.state, g.log), a):
                return self._refused(u, g, "candidate")
            echo = {"text": action_label(u, observe(u, g.state, g.log), p, a), "slots": []}
            return await self._run(u, g, [{"action": str(a)}], echo, "button", None)
        text = body.get("text")
        if self.interpreter is None:
            return self._refused(u, g, "text")
        start = time.monotonic()
        out = await self.interpreter.plan(u, g, text)
        secs = round(time.monotonic() - start, 2)     # the wait before a card or a reveal (fun.md F15)
        if out.get("refused"):
            p["requests"].append({"kind": "refused", "text": text, "secs": secs})
            return self._refused(u, g, out["refused"])
        n = len(p["requests"])
        result = await self._run(u, g, out["plan"], {"text": text, "slots": out.get("slots", [])}, "text", text)
        for r in p["requests"][n:]:
            r.setdefault("secs", secs)          # a refusal _run wrote for this sentence
        if result["kind"] != "refused":
            # How the sentence ended, for the interpretation metric (fun.md F1).
            card = p.get("card")
            outcome = ("idle" if out["plan"][0].get("idle")
                       else "clarify" if card and card["kind"] == "clarify"
                       # a waiting card the sentence discarded and nothing done: refused, though the response is a turn
                       else "refused" if not result["steps"] and card is None else "accepted")
            p["requests"].append({"kind": "text", "text": text, "outcome": outcome, "secs": secs})
        return result

    async def _run(self, u: Universe, g: Game, plan: list, echo: dict, kind: str, text: str | None) -> dict:
        p = g.presentation
        prev = p.get("card")
        had_card = prev is not None
        # Whether a sentence or a button chose these steps; an answered card keeps its own (fun.md F2).
        origin = (prev or {}).get("origin", "button") if kind == "card" else kind
        if had_card and kind != "card":
            p["requests"].append({"kind": "discard", "card": prev["id"]})
        p["card"] = None
        records, t0, already = [], len(g.log), None
        unfinished = ""             # what of the sentence a turn that stops early has not done ("" when unnamed)
        for i, st in enumerate(plan):
            o = observe(u, g.state, g.log)
            rest = plan[i + 1:]
            labels = [self._label(u, o, p, s) for s in rest]
            if "action" not in st:
                st = await self.interpreter.fill(u, g, st)
                if st.get("already"):
                    already = st["already"]     # going where the player is: done, on to the next step
                    continue
                if st.get("refused"):
                    if not records:
                        p["requests"].append({"kind": "refused", "text": text})
                        p["revision"] += had_card       # the waiting card is gone either way
                        return self._refused(u, g, st["refused"])
                    break
                if st.get("clarify"):
                    p["card_seq"] += 1
                    p["card"] = clarify_card(u, o, rest, labels, echo, f"c{p['card_seq']}", st["clarify"])
                    self._opened(p, origin)
                    break
                if "action" not in st:
                    break
            if kind == "text" and records and records[-1]["action"] == st["action"]:
                unfinished = None
                break                       # a sentence's later step that repeats the one before is the same act
            a = parse(st["action"])
            if not admits(u, o, a):
                if i == 0 and not had_card and kind != "text":
                    return self._refused(u, g, "candidate")
                break
            step_echo = {**echo, "slots": st.get("slots", echo.get("slots", []))}
            if not st.get("accepted"):
                rolling = rolls(u, o.facts, o.hist, a)
                # A thing handed over does not come back, and a sentence that only showed it was read as giving
                # (qa_test/runs/play-3-talker 3, play-4-talker 7); a sentence read as waiting spent the scene with no
                # card (qa/findings.md).
                if rolling or risk(u, a) == "high" or a.schema in ("give", "cut") and kind == "text":
                    p["card_seq"] += 1
                    cid = f"c{p['card_seq']}"
                    make = roll_card if rolling else confirm_card
                    named = a.get("rely") or st.get("rely")
                    extra = {"selected": named, "relies": await self._relies(u, o, p, a, named, text)} if rolling else {}
                    p["card"] = make(u, o, p, a, rest, labels, step_echo, cid, **extra)
                    self._opened(p, origin)
                    unfinished = p["card"]["public"]["plan"]["step"]["label"]
                    break
                # A sentence picks a way by meaning, so the player sees where and with whom before leaving; one that
                # names its way alone leaves at once unless someone stays behind (engine.md 4.4).
                if a.schema == "go" and kind == "text":
                    only = names_way(u, a.intent[0], ways(u, o), text)
                    asked = tuple(h for h in joiners(u, o) if says(u, h, text))
                    if not only or left_behind(u, o, a.intent[0]) or asked:
                        p["card_seq"] += 1
                        p["card"] = move_card(u, o, p, a, rest, labels, step_echo, f"c{p['card_seq']}", only, asked)
                        self._opened(p, origin)
                        unfinished = p["card"]["public"]["plan"]["step"]["label"]
                        break
            records.append(self._step(u, g, a))
            s = g.state
            if ended(s) or records[-1]["result"] in ("fail", "blocked"):
                unfinished = None if ended(s) or not rest else labels[0] if "action" in rest[0] else ""
                break
        else:
            unfinished = None
        turn = None
        if records:
            turn = len(p["turns"]) + 1
            p["turns"].append({"n": turn, "kind": kind, "text": text, "t0": t0, "t1": len(g.log) - 1,
                               "steps": records, "origin": origin, "card": prev["id"] if kind == "card" else None})
            if unfinished is not None:
                p["turns"][-1]["unfinished"] = unfinished
        if records or p["card"] is not None or had_card:
            p["revision"] += 1
        if not records and p["card"] is None and not had_card:
            if kind == "text":
                p["requests"].append({"kind": "refused", "text": text})
            why = unreachable(u, observe(u, g.state, g.log), text, "") if text else None
            return self._refused(u, g, already or why or "candidate")
        return self._result(u, g, "card" if p["card"] else "turn", turn, records)

    async def _relies(self, u, o, p, a, named: str | None, text: str | None) -> list[str]:
        values = rely_options(u, o, a.with_(rely=None))
        if self.interpreter is None or not values:
            return values
        return await self.interpreter.relevant(u, o, p, a.with_(rely=None), values, named, text)

    @staticmethod
    def _opened(p: dict, origin: str) -> None:
        card = p["card"]
        card["origin"] = origin
        p["requests"].append({"kind": "card", "card": card["id"], "card_kind": card["kind"],
                              "options": len(card["options"])})

    def _label(self, u, o, p, st: dict) -> str:
        if "action" in st:
            try:
                return action_label(u, o, p, parse(st["action"]))
            except (ValueError, KeyError, StopIteration):
                return st["action"]
        return ko.SCHEMA_DESC.get(st.get("schema"), "")

    def _step(self, u: Universe, g: Game, a) -> dict:
        p = g.presentation
        s, t = g.state, len(g.log)
        o = observe(u, s, g.log)
        label = action_label(u, o, p, a)
        k = chapter_k(u, o.facts)
        step = resolve(u, s, g.log.hist, a, roll(g.seed, t))
        e = event_of(u, s, t, a, step)
        record(u, g.log, s, step.after, e)
        g.state = step.after
        for x, slot, name in step.names:
            mark = step.after.mark_.get((x, slot))
            atom = ("mark", x, *mark, slot) if mark else None
            if atom and atom in step.delta.add:
                p["tags"].append([list(atom), t, default_tag_name(name, mark[0])])
        if a.schema == "choose":
            p["choices"].append({"kind": "fork", "name": label, "chapter": k})
        ending = step.after.flag("ending") if ended(step.after) and not ended(s) else None
        if ending:
            p["ending"] = ending
        return step_record(u, p, g.log.seen[PLAYER][-1], label, ending)

    async def narration(self, game_id: str, n: int):
        return await self._narration(game_id, "narration", n, turn_job)

    async def recap(self, game_id: str, k: int):
        return await self._narration(game_id, "recap", k, recap_job)

    async def _narration(self, game_id: str, store: str, n: int, job_of):
        async with self.lock(game_id):
            u, g = await self.load(game_id)
            key = str(n)
            entry = g.presentation.get(store, {}).get(key)
            if entry is not None:
                return _cached(entry)
            job = job_of(u, g, n)
            if job is None:
                raise Missing(f"{store} {n}")
            sid = (game_id, store, n)
            if sid not in self.streams:
                stream = self.streams[sid] = Stream()
                stream.task = asyncio.create_task(self._make(game_id, sid, store, key, job))
            return self.streams[sid].read()

    async def _make(self, game_id: str, sid: tuple, store: str, key: str, job: Job) -> None:
        stream = self.streams[sid]
        start = time.monotonic()
        try:
            async for e in self.narrator.narrate(job):
                if e["type"] != "result":
                    await stream.push(e, done=e["type"] == "error")
                    continue
                entry = {k: e[k] for k in ("text", "attempts", "dropped", "tags")} | \
                    {k: e[k] for k in ("said", "hint") if e.get(k)} | {"secs": round(time.monotonic() - start, 2)}
                async with self.lock(game_id):
                    u, g = await self.load(game_id)
                    p = g.presentation
                    p.setdefault(store, {})[key] = entry
                    for t in entry["tags"]:
                        p["tags"][t["index"]][2] = t["name"]
                    try:
                        await self.store(u, g)
                    except BaseException:
                        self.games.pop(game_id, None)       # an unsaved narration is not served from memory
                        raise
                await stream.push(*[x async for x in _cached(entry)], done=True)
        except Exception as exc:  # noqa: BLE001 -- a stream must end; the next request starts over
            await stream.push({"type": "error", "message": f"{type(exc).__name__}"}, done=True)
        finally:
            self.streams.pop(sid, None)
