"""The turn protocol (engine.md 7): one lock per game, receipts, revision, plan, steps, one save."""

from __future__ import annotations

import asyncio
import hashlib
import json
import re
import secrets
from pathlib import Path

from .cards import confirm_card, roll_card
from .locale import ko
from .onto.atoms import PLAYER
from .onto.save import Game, SaveError, new_game, rebuild, save
from .onto.universe import Universe, check_creation
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
    complication_name,
    default_tag_name,
    game_view,
    step_record,
)

GAME_ID = re.compile(r"g_[a-f0-9]{32}")
RECEIPTS = 50


class Missing(LookupError):
    """No such game."""


class Incompatible(RuntimeError):
    """A save of another schema or story digest (api.md 1: 409 incompatible)."""


class Conflict(RuntimeError):
    """A stale revision or a request id reused with another body; carries the current view."""

    def __init__(self, view: dict):
        super().__init__("conflict")
        self.view = view


class Invalid(ValueError):
    """A malformed request (422)."""


def body_hash(body: dict) -> str:
    rest = {k: v for k, v in body.items() if k != "request_id"}
    return hashlib.sha256(json.dumps(rest, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def fresh_presentation(created: str) -> dict:
    return {"revision": 0, "turns": [], "requests": [], "card": None, "card_seq": 0, "narration": {},
            "recap": {}, "tags": [], "choices": [], "receipts": {}, "created": created, "ending": None}


class GameService:
    def __init__(self, stories: dict[str, Universe], save_dir: Path, interpreter=None,
                 seeds=lambda: secrets.randbits(63)):
        self.stories = stories
        self.seeds = seeds                      # a game's dice seed (rule.md 3.1); tests pin it
        self.save_dir = save_dir
        self.interpreter = interpreter          # engine.md 3; text is refused without it
        self.games: dict[str, tuple[Universe, Game]] = {}
        self.locks: dict[str, asyncio.Lock] = {}

    # -- storage --

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

    # -- routes --

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
            except StoryError as e:
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

    # -- one command --

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
            plan = [{"action": body["pick"], "accepted": True}, *card["rest"]]
            return await self._run(u, g, plan, card["public"]["echo"], "card", None)
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
        return await self._run(u, g, out["plan"], {"text": text, "slots": out.get("slots", [])}, "text", text)

    async def _run(self, u: Universe, g: Game, plan: list, echo: dict, kind: str, text: str | None) -> dict:
        p = g.presentation
        had_card = p.get("card") is not None
        p["card"] = None
        records, t0 = [], len(g.log)
        for i, st in enumerate(plan):
            o = observe(u, g.state, g.log)
            if "action" not in st:
                st = await self.interpreter.fill(u, g, st)
                if st.get("card"):
                    p["card"] = st["card"]
                    break
                if "action" not in st:
                    break
            a = parse(st["action"])
            if not admits(u, o, a):
                if i == 0 and not had_card and kind != "text":
                    return self._refused(u, g, "candidate")
                break
            rest = plan[i + 1:]
            labels = [self._label(u, o, p, s) for s in rest]
            if not st.get("accepted"):
                rolling = rolls(u, o.facts, o.hist, a)
                if rolling or risk(u, a) == "high":
                    p["card_seq"] += 1
                    cid = f"c{p['card_seq']}"
                    make = roll_card if rolling else confirm_card
                    extra = {"selected": a.get("rely")} if rolling else {}
                    p["card"] = make(u, o, p, a, rest, labels, echo, cid, **extra)
                    break
            records.append(self._step(u, g, a))
            s = g.state
            if ended(s) or records[-1]["result"] in ("fail", "blocked") or any(r[0] == PLAYER for r in s.rows("due")):
                break
        turn = None
        if records:
            turn = len(p["turns"]) + 1
            p["turns"].append({"n": turn, "kind": kind, "text": text, "t0": t0, "t1": len(g.log) - 1,
                               "steps": records})
        if records or p["card"] is not None or had_card:
            p["revision"] += 1
        if not records and p["card"] is None and not had_card:
            return self._refused(u, g, "candidate")
        return self._result(u, g, "card" if p["card"] else "turn", turn, records)

    def _label(self, u, o, p, st: dict) -> str:
        if "action" in st:
            try:
                return action_label(u, o, p, parse(st["action"]))
            except (ValueError, KeyError, StopIteration):
                return st["action"]
        return st.get("label", "")

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
                p["tags"].append([list(atom), t, default_tag_name(u, name, mark[0])])
        if a.schema == "pay":
            p["choices"].append({"kind": "cost", "name": complication_name(u, a.intent[0]), "chapter": k})
        elif a.schema == "choose":
            p["choices"].append({"kind": "fork", "name": label, "chapter": k})
        ending = step.after.flag("ending") if ended(step.after) and not ended(s) else None
        if ending:
            p["ending"] = ending
        return step_record(u, p, g.log.seen[PLAYER][-1], label, ending)
