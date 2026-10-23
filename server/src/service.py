from __future__ import annotations

import asyncio
import hashlib
import json
import re
import secrets
from pathlib import Path

from .cards import clarify_card, confirm_card, move_card, rely_options, roll_card, ways
from .interpret import names_way, unreachable
from .lang.context import pace
from .locale import ko
from .narrate import (
    GROWN_CHARS,
    GROWN_SENTENCES,
    RECAP_CHARS,
    RECAP_SENTENCES,
    REPLY_SIZE,
    SHORT_CHARS,
    Job,
    change_ids,
    step_lines,
)
from .onto.atoms import PLAYER
from .onto.save import Game, SaveError, new_game, rebuild, replay, save
from .onto.universe import CreationError, Universe, check_creation
from .onto.view import observe, record
from .rules.acts import parse
from .rules.candidates import admits
from .rules.recommend import recommend
from .rules.resolve import event_of, resolve
from .rules.roll import risk, roll, rolls
from .rules.schemas import small_talk
from .rules.triggers import ended
from .story.load import StoryError
from .view import (
    action_label,
    chapter_k,
    default_tag_name,
    game_view,
    rely_label,
    step_record,
)

GAME_ID = re.compile(r"g_[a-f0-9]{32}")
RECEIPTS = 50
PREVIOUS_TURNS = 3
SAID = 4                # earlier exchanges per speaker handed to narration (engine.md 5.1)
SHARED = 4              # events lived together per speaker (ontology.md 3.4)
RECAP_NOTABLE = 5


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
        out = await self.interpreter.plan(u, g, text)
        if out.get("refused"):
            p["requests"].append({"kind": "refused", "text": text})
            return self._refused(u, g, out["refused"])
        result = await self._run(u, g, out["plan"], {"text": text, "slots": out.get("slots", [])}, "text", text)
        if result["kind"] != "refused":
            # How the sentence ended, for the interpretation metric (fun.md F1).
            card = p.get("card")
            outcome = ("idle" if out["plan"][0].get("idle")
                       else "clarify" if card and card["kind"] == "clarify"
                       # a waiting card the sentence discarded and nothing done: refused, though the response is a turn
                       else "refused" if not result["steps"] and card is None else "accepted")
            p["requests"].append({"kind": "text", "text": text, "outcome": outcome})
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
                    p["card"] = clarify_card(rest, labels, echo, f"c{p['card_seq']}", st["clarify"])
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
                # (qa_test/runs/play-3-talker 3, play-4-talker 7).
                if rolling or risk(u, a) == "high" or a.schema == "give" and kind == "text":
                    p["card_seq"] += 1
                    cid = f"c{p['card_seq']}"
                    make = roll_card if rolling else confirm_card
                    named = a.get("rely") or st.get("rely")
                    extra = {"selected": named, "relies": await self._relies(u, o, p, a, named, text)} if rolling else {}
                    p["card"] = make(u, o, p, a, rest, labels, step_echo, cid, **extra)
                    self._opened(p, origin)
                    unfinished = p["card"]["public"]["plan"]["step"]["label"]
                    break
                # A sentence picks a way by meaning, so the player sees where and with whom before leaving (engine.md 4.4).
                if a.schema == "go" and kind == "text":
                    p["card_seq"] += 1
                    only = names_way(u, a.intent[0], ways(u, o), text)
                    p["card"] = move_card(u, o, p, a, rest, labels, step_echo, f"c{p['card_seq']}", only)
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
        return await self._narration(game_id, "narration", n, self._turn_job)

    async def recap(self, game_id: str, k: int):
        return await self._narration(game_id, "recap", k, self._recap_job)

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
        try:
            async for e in self.narrator.narrate(job):
                if e["type"] != "result":
                    await stream.push(e, done=e["type"] == "error")
                    continue
                entry = {k: e[k] for k in ("text", "attempts", "dropped", "tags")} | \
                    {k: e[k] for k in ("said", "hint") if e.get(k)}
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

    def _at(self, u: Universe, g: Game, t1: int):
        s, log = replay(u, g.creation, g.log.events[:t1 + 1])
        return observe(u, s, log)

    def _turn_job(self, u: Universe, g: Game, n: int) -> Job | None:
        p = g.presentation
        turn = next((x for x in p["turns"] if x["n"] == n), None)
        if turn is None:
            return None
        o = self._at(u, g, turn["t1"])
        changes = [c for r in turn["steps"] for c in r["changes"]]
        happened, delta, ids, named = [], [], set(), []
        for r in turn["steps"]:
            lines, told = step_lines(u, r)
            happened += lines
            delta += told
            ids |= change_ids(r)
            named += r["action"].split(";")[0].split(":")[1:]
            named += [c["id"] for c in r["changes"] if c["kind"] == "follow" or c.get("with")]
        here = o.facts.where(PLAYER)
        people = {x for x in o.seen if x in u.agents and o.facts.where(x) == here}
        speakers = [x for x in dict.fromkeys(named) if x in people]
        # A companion who stayed is out of sight once the player has gone, so where they stayed is where the player
        # left; reading it from the view gave None and broke the narration (qa_test/runs/play-3-talker 33).
        went = next((c["from"] for c in changes if c["kind"] == "move" and c["id"] == PLAYER), None)
        left = {c["id"]: q for c in changes
                if c["kind"] == "follow" and c["state"] == "stop" and (q := o.facts.where(c["id"]) or went) and q != here}
        joined = tuple(c["id"] for c in changes if c["kind"] == "follow" and c["state"] == "start")
        tags = [{"index": i, "slot": atom[4], "owner": atom[1], "name": name}
                for i, (atom, t, name) in enumerate(p["tags"])
                if turn["t0"] <= t <= turn["t1"] and o.facts.mark_.get((atom[1], atom[4])) == tuple(atom[2:4])]
        kinds = {c["kind"] for c in changes}
        paced = tuple(dict.fromkeys(c["id"] for c in changes if c["kind"] == "fill" and c["id"] in u.obstacles
                                    and u.obstacles[c["id"]].sub in ("clock", "deadline")
                                    and pace(c["from"], u.boxes(c["id"])) != pace(c["to"], u.boxes(c["id"]))))
        ending = next((c["id"] for c in changes if c["kind"] == "ending"), None)
        previous = [p["narration"][str(m)]["text"] for m in range(max(1, n - PREVIOUS_TURNS), n)
                    if str(m) in p["narration"]]
        grown = all(r["action"].startswith("grow:") for r in turn["steps"])
        progress = {c["id"]: c["to"] >= u.boxes(c["id"]) for c in changes
                    if c["kind"] == "fill" and c["to"] > c["from"]}
        blocked = tuple(r["label"] for r in turn["steps"] if r["result"] == "blocked")
        came = [c for c in changes if c["kind"] in ("crisis", "arrival")]
        struck = tuple(dict.fromkeys(c["name"] for c in came if not c["id"].startswith("deadline.")))
        missed = tuple(dict.fromkeys(c["name"] for c in came if c["id"].startswith("deadline.")))
        # A blocked step rolls nothing, so nothing was leaned on (rule.md 3.4).
        relied = tuple(dict.fromkeys(rely_label(u, p, o.facts, x) for r in turn["steps"]
                                     if r["result"] != "blocked" and (x := parse(r["action"]).get("rely"))))
        looked = tuple(dict.fromkeys(r["action"].split(":")[1] for r in turn["steps"]
                                     if r["action"].startswith("look:") and r["result"] != "blocked"))
        actions = [parse(r["action"]) for r in turn["steps"]]
        reply, hint = "act", None
        if all(small_talk(a) for a in actions) and not blocked:
            reply = "talk"
        elif all(a.schema == "try" and a.intent[0] == PLAYER for a in actions):
            # the idle label would leak ("말한 대로 행동을 이어갑니다"), and anyone here may answer (engine.md 5.2)
            reply, happened, speakers = "muse", [ko.HAPPENED_MUSE], sorted(people, key=u.rank)
            # a player who talks to themself mostly does not know what to do next (engine.md 5.2)
            hinted = {p["narration"].get(str(m), {}).get("hint") for m in range(max(1, n - PREVIOUS_TURNS), n)}
            forward = recommend(u, o)
            if way := next((a for a in forward if str(a) not in hinted), forward[0] if forward else None):
                hint = (str(way), action_label(u, o, p, way))
                ids |= {x for x in way.intent if x in u.places or x in u.agents or x in u.obstacles or x in u.things}
        # What each speaker said before the previous narration, which alone let an answer drift (engine.md 5.1).
        texts = {x["n"]: x.get("text") or "" for x in p["turns"]}
        said: dict[str, list] = {}
        for m in range(1, n - PREVIOUS_TURNS):
            for x, lines in p["narration"].get(str(m), {}).get("said", {}).items():
                if x in speakers:
                    said.setdefault(x, []).append((texts.get(m, ""), lines))
        said = {x: rows[-SAID:] for x, rows in said.items()}
        shared = lived(u, o, [m for m in p["turns"] if m["n"] < n - PREVIOUS_TURNS], speakers)
        size = {"sentences": GROWN_SENTENCES, "chars": GROWN_CHARS} if grown else \
            dict(zip(("sentences", "chars"), REPLY_SIZE[reply])) if reply != "act" and not kinds & {"chapter", "ending"} \
            else {"chars": SHORT_CHARS if kinds & {"chapter", "ending"} else Job.chars}
        return Job(u, o, p, happened, delta, {PLAYER, here, *people, *ids}, text=turn["text"], tags=tags,
                   previous=previous, ending=u.endings[ending].frame if ending else None, speakers=speakers, left=left,
                   joined=joined, unfinished=turn.get("unfinished"), grown=grown, progress=progress, blocked=blocked,
                   relied=relied, looked=looked, struck=struck, missed=missed, reply=reply, said=said, shared=shared,
                   hint=hint, arrived=went is not None, paced=paced, **size)

    def _recap_job(self, u: Universe, g: Game, k: int) -> Job | None:
        p = g.presentation
        chapter, notable, closing, closer = 1, [], None, None
        for turn in p["turns"]:
            for r in turn["steps"]:
                if chapter == k and notable_step(u, r):
                    notable.append(r)
                kinds = {c["kind"]: c for c in r["changes"]}
                if chapter == k and ("chapter" in kinds or "ending" in kinds):
                    closing, closer = turn, r
                if "chapter" in kinds:
                    chapter = kinds["chapter"]["to"]
        if closing is None:
            return None
        o = self._at(u, g, closing["t1"])
        # The step that closed the chapter goes last: without it a recap credited the oil, not the punch that lit
        # the lamp, and told the sky darkening at the ending (qa_test/runs/play-3-bold 21, ui-5).
        steps = [*[r for r in notable if r is not closer][1 - RECAP_NOTABLE:], closer]
        lines = [x for r in steps for x in step_lines(u, r)[0]]
        task = ko.fill(ko.RECAP_TASK, title=u.chapter_of(k).title, sentences=RECAP_SENTENCES, chars=RECAP_CHARS)
        return Job(u, o, p, lines, lines, {PLAYER, o.facts.where(PLAYER)}, chars=RECAP_CHARS,
                   sentences=RECAP_SENTENCES, task=task)


def lived(u, o, turns: list[dict], speakers: list[str]) -> dict[str, list[str]]:
    """Each speaker's events of shared(g), older than the previous narration, as step lines (ontology.md 3.4)."""
    witnessed = {s.t: s.witnesses for s in o.memory}
    out: dict[str, list[str]] = {}
    for turn in turns:
        for r in turn["steps"]:
            for x in speakers:
                if x in witnessed.get(r["t"], ()) and marks(u, r):
                    out.setdefault(x, []).append(". ".join(step_lines(u, r)[0]))
    return {x: lines[-SHARED:] for x, lines in out.items()}


def marks(u, r: dict) -> bool:
    """An event that marks its witnesses: notable, done to a person with a change or a roll, or the player hurt
    (ontology.md 3.4). A refused favor changes nothing, yet left out, 윤슬 later told of the key being lent
    (qa_test/runs/loop-1/long-after r0 t21)."""
    kinds = {c["kind"] for c in r["changes"]}
    person = any(a in u.agents for a in r["action"].split(";")[0].split(":")[1:])
    acted = person and (kinds & {"move", "follow", "promise", "regards", "reveal"} or r["roll"] is not None)
    return notable_step(u, r) or bool(acted) or "wound" in kinds


def notable_step(u, r: dict) -> bool:
    schema = r["action"].split(":")[0]
    if schema in ("declare", "choose", "pay") or ";claim=" in r["action"]:
        return True
    # An obstacle overcome is the chapter's work; left out, a recap skipped the door the player broke (play-3-bold 6).
    return any(c["kind"] in ("promise", "scar", "arrival")
               or (c["kind"] == "fill" and (c["to"] - c["from"] >= 2 or c["to"] >= u.boxes(c["id"]) > c["from"]))
               for c in r["changes"])
