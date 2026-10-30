from __future__ import annotations

import re
from dataclasses import replace as _replace

from ..locale import ko
from ..onto.atoms import APPROACHES, AXES, KINDS, PLAYER
from ..onto.cond import TRUE, Cond, compile_cond, conj
from ..onto.log import compile_pattern
from ..onto.universe import (
    Agent,
    Chapter,
    Complication,
    Effect,
    Ending,
    Favor,
    Latent,
    Obstacle,
    Place,
    Prop,
    Solution,
    Thing,
    Topic,
    Trigger,
    Universe,
)
from .load import StoryError

ID = re.compile(r"[a-z0-9_]+")
RESERVED = {"player", "chat", "favor", "come", "stay", "pass", "rest", "chapter", "ending", "collapse", "promise",
            "kindness", "full", "beats", "wounds", "growth", *APPROACHES}
WEIGHTS = ("light", "heavy")
STORY_RISKS = ("low", "normal")   # only a clash or forced strain makes a step high
KNOWS = 4                         # a person's told-freely sentences (story.md 3.4)
WOUND = ("tag", PLAYER, "snag", "wound", "@wound")


class _Builder:
    """The structural part of story.md V1; validate.py checks the rest."""

    def __init__(self, raw: dict, digest: str):
        self.raw = raw
        self.digest = digest
        self.ids: dict[str, str] = {}             # every story id → its section
        self.kinds: dict[str, str] = {PLAYER: "agent"}
        self.u: Universe | None = None
        self.pattern_keys: dict[tuple, int] = {}
        self.pending: list = []

    def fail(self, msg: str):
        raise StoryError(msg)

    def map(self, v, where, allowed=None, required=()) -> dict:
        if v is None:
            v = {}
        if not isinstance(v, dict):
            self.fail(f"{where}: expected a map")
        if allowed is not None:
            extra = [k for k in v if k not in allowed]
            if extra:
                self.fail(f"{where}: unknown field {extra[0]}")
        for k in required:
            if k not in v or v[k] is None:
                self.fail(f"{where}: missing field {k}")
        return v

    def list(self, v, where) -> list:
        if v is None:
            return []
        if not isinstance(v, list):
            self.fail(f"{where}: expected a list")
        return v

    def text(self, v, where) -> str:
        if not isinstance(v, str) or not v.strip():
            self.fail(f"{where}: expected text")
        return v

    def int(self, v, where, lo=None, hi=None) -> int:
        if not isinstance(v, int) or isinstance(v, bool):
            self.fail(f"{where}: expected an integer")
        if (lo is not None and v < lo) or (hi is not None and v > hi):
            self.fail(f"{where}: {v} is out of range {lo}…{hi}")
        return v

    def texts(self, v, where) -> tuple[str, ...]:
        return tuple(self.text(x, f"{where}[{i}]") for i, x in enumerate(self.list(v, where)))

    def choice(self, v, options, where) -> str:
        if v not in options:
            self.fail(f"{where}: {v!r} is not one of {', '.join(options)}")
        return v

    def new_id(self, i, section: str, kind: str | None = None, where: str = "") -> str:
        if not isinstance(i, str) or not ID.fullmatch(i):
            self.fail(f"{where or section}: id {i!r} must be lowercase letters, digits and _")
        if i in RESERVED and not (i == "collapse" and section == "endings"):
            self.fail(f"{where or section}: id {i} is reserved")
        if i.startswith("fired_"):
            self.fail(f"{where or section}: id {i} is reserved")
        if i in self.ids:
            self.fail(f"{where or section}: id {i} is already used in {self.ids[i]}")
        self.ids[i] = section
        if kind:
            self.kinds[i] = kind
        return i

    def ref(self, x, kinds, where) -> str:
        k = self.kinds.get(x) if isinstance(x, str) else None
        if k not in kinds:
            self.fail(f"{where}: {x!r} is not a known {'/'.join(kinds)}")
        return x

    def boxes(self, o):
        return self.u.obstacles[o].boxes

    def flag_value(self, name, v, where):
        dom = self.u.flags.get(name)
        if dom is None or name == "ending":
            self.fail(f"{where}: unknown flag {name}")
        if v not in dom:
            self.fail(f"{where}: {v!r} is not a value of flag {name}")
        return v

    def pattern(self, prefix, result, where) -> int:
        key = (prefix, result)
        if key not in self.pattern_keys:
            self.pattern_keys[key] = len(self.u.patterns)
            self.u.patterns.append(compile_pattern(prefix, (result,) if result else None))
        return self.pattern_keys[key]

    def cond(self, raw, where) -> Cond:
        return compile_cond(raw, self, where)

    def opt_cond(self, raw, where) -> Cond | None:
        return None if raw is None else self.cond(raw, where)

    def effects(self, raw, where) -> tuple[Effect, ...]:
        return tuple(self.effect(e, f"{where}[{i}]") for i, e in enumerate(self.list(raw, where)))

    def effect(self, raw, where) -> Effect:
        if not isinstance(raw, dict) or len(raw) != 1:
            self.fail(f"{where}: an effect is a map with one key")
        (key, a), = raw.items()
        if key == "retire":
            o = self.ref(a, ("obstacle",), where)
            self.engine_owned(o, where)
            return ("retire", o)
        a = self.list(a, where)
        if key == "move":
            if len(a) != 2:
                self.fail(f"{where}: move takes [x, y]")
            x = self.ref(a[0], ("agent", "thing"), where)
            y = self.ref(a[1], ("place",) if x == PLAYER else ("place", "agent"), where)
            return ("move", x, y)
        if key == "set":
            if not a:
                self.fail(f"{where}: set takes [what, …]")
            what = a[0]
            if what == "fill" and len(a) == 3:
                o = self.ref(a[1], ("obstacle",), where)
                self.engine_owned(o, where)
                return ("set", "fill", (o,), self.number(a[2], where))
            if what == "regards" and len(a) == 5:
                g, h = self.ref(a[1], ("agent",), where), self.ref(a[2], ("agent",), where)
                if h != PLAYER:
                    self.fail(f"{where}: regards are toward the player; no rule reads them between people")
                return ("set", "regards", (g, h, self.choice(a[3], AXES, where)), self.number(a[4], where))
            if what == "flag" and len(a) == 3:
                if a[1] not in self.u.flags or a[1] == "chapter" or a[1].startswith(("fired_", "uses.")):
                    self.fail(f"{where}: flag {a[1]} cannot be set by a story")
                v, dom = self.value(a[2], where), self.u.flags[a[1]]
                # A step (+1) must land on numbers; anything else must already be a value of the flag.
                step = isinstance(v, str) and re.fullmatch(r"[+-]\d+", v)
                if not (all(isinstance(d, int) for d in dom) if step else v in dom):
                    self.fail(f"{where}: {v!r} is not a value of flag {a[1]}")
                return ("set", "flag", (a[1],), v)
            self.fail(f"{where}: set takes [fill, o, v], [regards, g, h, axis, v] or [flag, name, v]")
        if key in ("reveal", "forget"):
            if len(a) != 2:
                self.fail(f"{where}: {key} takes [g, p]")
            g = self.ref(a[0], ("agent",), where)
            if key == "forget" and g == PLAYER:
                self.fail(f"{where}: the player's beliefs are what they found; forget takes a person")
            return (key, g, self.ref(a[1], ("prop",), where))
        if key == "consume":
            if len(a) != 1:
                self.fail(f"{where}: consume takes [x]")
            return ("consume", self.ref(a[0], ("thing",), where))
        if key == "tag":
            if len(a) != 4:
                self.fail(f"{where}: tag takes [x, kind, life, name]")
            x = self.ref(a[0], ("agent", "thing", "obstacle", "place"), where)
            return ("tag", x, self.choice(a[1], KINDS, where), self.choice(a[2], ("scene", "chapter"), where),
                    self.text(a[3], where))
        if key in ("link", "unlink"):
            if len(a) != 2:
                self.fail(f"{where}: {key} takes [p, q]")
            return (key, self.ref(a[0], ("place",), where), self.ref(a[1], ("place",), where))
        self.fail(f"{where}: unknown effect {key}")

    def engine_owned(self, o, where):
        if self.u.obstacles[o].sub in ("clock", "deadline"):
            self.fail(f"{where}: clocks and deadlines cannot be targeted")

    def value(self, v, where):
        if isinstance(v, (int, str)) and not isinstance(v, bool):
            return v
        self.fail(f"{where}: bad value {v!r}")

    def number(self, v, where):
        """A count or a step such as "+1"; a word here failed only when the effect ran."""
        if isinstance(v, int) and not isinstance(v, bool) or isinstance(v, str) and re.fullmatch(r"[+-]\d+", v):
            return v
        self.fail(f"{where}: {v!r} is not a number or a step like +1")

    def build(self) -> Universe:
        r = self.map(self.raw, "story", allowed={
            "id", "version", "title", "premise", "beats", "flags", "style", "impossible",
            "player", "places", "characters", "things", "obstacles", "chapters", "threats", "forks",
            "claims", "latents", "triggers", "endings", "witnesses"},
            required=("id", "version", "title", "premise", "beats", "style", "player",
                      "places", "characters", "things", "obstacles", "chapters", "endings", "witnesses"))
        if not isinstance(r["id"], str) or not ID.fullmatch(r["id"]):
            self.fail("story.id: must be lowercase letters, digits and _")
        p = self.map(r["player"], "player", {"start", "approaches", "traits"}, ("start", "approaches"))
        approaches = tuple(self.int(v, "player.approaches", 0, 3) for v in self.list(p["approaches"], "player"))
        if len(approaches) != 4:
            self.fail("player.approaches: needs four values")
        traits, pick = {}, 0
        if p.get("traits") is not None:
            t = self.map(p["traits"], "player.traits", {"pick", "options"}, ("pick", "options"))
            pick = self.int(t["pick"], "player.traits.pick", 1)
            for tid, tv in self.map(t["options"], "player.traits.options").items():
                w = f"player.traits.{tid}"
                self.new_id(tid, "traits", None, w)
                tv = self.map(tv, w, {"name", "text"}, ("name", "text"))
                traits[tid] = (self.text(tv["name"], w), self.text(tv["text"], w))
            if len(traits) <= pick:
                self.fail("player.traits: needs more options than pick")
        u = self.u = Universe(
            id=r["id"], version=self.int(r["version"], "version", 1), title=self.text(r["title"], "title"),
            premise=self.text(r["premise"], "premise"), style=self.text(r["style"], "style"),
            digest=self.digest, beats=self.int(r["beats"], "beats", 2),
            impossible=self.texts(r.get("impossible"), "impossible"), start="",
            approaches=approaches, pick=pick, traits=traits, raw=self.raw)

        sections = {k: self.map(r.get(k), k) for k in
                    ("places", "characters", "things", "obstacles", "threats", "forks", "claims",
                     "latents", "triggers", "endings")}
        chapters = self.list(r["chapters"], "chapters")
        if not chapters:
            self.fail("chapters: needs at least one chapter")

        # Ids first, so references can point forward.
        for i in sections["places"]:
            self.new_id(i, "places", "place", f"places.{i}")
        for i in sections["characters"]:
            self.new_id(i, "characters", "agent", f"characters.{i}")
        for i in sections["things"]:
            self.new_id(i, "things", "thing", f"things.{i}")
        for sec in ("obstacles", "threats", "forks"):
            for i in sections[sec]:
                self.new_id(i, sec, "obstacle", f"{sec}.{i}")
        for k in range(1, len(chapters) + 1):
            self.kinds[f"clock.{k}"] = self.kinds[f"deadline.{k}"] = "obstacle"
        for lid, lv in sections["latents"].items():
            self.new_id(lid, "latents", "prop", f"latents.{lid}")
            brings = self.map(self.map(lv, f"latents.{lid}").get("brings"), f"latents.{lid}.brings")
            for bid, bv in brings.items():
                kind = "thing" if isinstance(bv, dict) and "look" in bv else "agent"
                self.new_id(bid, f"latents.{lid}", kind, f"latents.{lid}.brings.{bid}")
        for i in sections["claims"]:
            self.new_id(i, "claims", "prop", f"claims.{i}")
        for i in sections["endings"]:
            self.new_id(i, "endings", None, f"endings.{i}")
        if "collapse" not in sections["endings"]:
            self.fail("endings: collapse is required")
        for i in sections["triggers"]:
            self.new_id(i, "triggers", None, f"triggers.{i}")
        for cid, cv in sections["characters"].items():
            cv = self.map(cv, f"characters.{cid}")
            for b in self.map(cv.get("beliefs"), f"characters.{cid}.beliefs"):
                self.new_id(b, "beliefs", "prop", f"characters.{cid}.beliefs.{b}")
            for t, tv in self.map(cv.get("topics"), f"characters.{cid}.topics").items():
                self.new_id(t, "topics", "prop" if "text" in self.map(tv, t) else None, f"characters.{cid}.topics.{t}")
        for sec in ("places", "characters", "things", "obstacles"):
            for i, v in sections[sec].items():
                v = self.map(v, f"{sec}.{i}")
                if v.get("hidden") is not None:
                    self.kinds[f"{i}.hidden"] = "prop"
                if v.get("clue") is not None:
                    self.kinds[f"{i}.clue"] = "prop"

        u.flags["chapter"] = tuple(range(1, len(chapters) + 1))
        u.flags["ending"] = tuple(sections["endings"])
        for name, vals in self.map(r.get("flags"), "flags").items():
            self.new_id(name, "flags", None, f"flags.{name}")
            if isinstance(vals, dict):
                # value → the line the narrator reads while the flag holds it ("" for none)
                # map keys load as text, so a numeric flag's values come back as numbers
                vals = {int(v) if re.fullmatch(r"-?\d+", str(v)) else v: t for v, t in vals.items()}
                texts = {v: self.text(t, f"flags.{name}.{v}") for v, t in vals.items() if t not in ("", None)}
                vals = list(vals)
                if texts:
                    u.texts[name] = texts
            vals = self.list(vals, f"flags.{name}")
            if not vals or len(set(map(str, vals))) != len(vals):
                self.fail(f"flags.{name}: needs distinct values")
            if all(isinstance(v, int) and not isinstance(v, bool) for v in vals):
                if sorted(vals) != list(range(min(vals), max(vals) + 1)):
                    self.fail(f"flags.{name}: integer values must be a contiguous range")
            elif not all(isinstance(v, str) for v in vals):
                self.fail(f"flags.{name}: values are all integers or all text")
            u.flags[name] = tuple(vals)

        # Obstacle shells first: `full` needs their boxes before conditions compile.
        for oid, ov in sections["obstacles"].items():
            ov = self.map(ov, f"obstacles.{oid}")
            u.obstacles[oid] = Obstacle(id=oid, sub="plain", name="",
                                        boxes=self.int(ov.get("boxes", 1), f"obstacles.{oid}.boxes", 1, 6))
        for sec, sub in (("threats", "threat"), ("forks", "fork")):
            for oid, ov in sections[sec].items():
                ov = self.map(ov, f"{sec}.{oid}")
                u.obstacles[oid] = Obstacle(id=oid, sub=sub, name="",
                                            boxes=self.int(ov.get("boxes"), f"{sec}.{oid}.boxes", 1, 6))
        for k, cv in enumerate(chapters, 1):
            w = f"chapters[{k}]"
            cv = self.map(cv, w, {"title", "aim", "goal", "goal_effects", "clock", "deadline"},
                         ("title", "aim", "clock", "deadline"))
            ck = self.map(cv["clock"], f"{w}.clock", {"name", "boxes", "crisis"}, ("name", "boxes", "crisis"))
            dl = self.map(cv["deadline"], f"{w}.deadline", {"name", "boxes", "effects", "ending"}, ("name", "boxes"))
            u.obstacles[f"clock.{k}"] = Obstacle(id=f"clock.{k}", sub="clock", name=self.text(ck["name"], w),
                                                 boxes=self.int(ck["boxes"], f"{w}.clock.boxes", 3))
            u.obstacles[f"deadline.{k}"] = Obstacle(id=f"deadline.{k}", sub="deadline",
                                                    name=self.text(dl["name"], w),
                                                    boxes=self.int(dl["boxes"], f"{w}.deadline.boxes", 1, 6))

        start = self.ref(p["start"], ("place",), "player.start")
        u.start = start
        for pid, pv in sections["places"].items():
            w = f"places.{pid}"
            pv = self.map(pv, w, {"name", "aliases", "senses", "exits", "rest", "clue", "hidden", "complications"},
                          ("name", "senses", "exits"))
            senses = self.texts(pv["senses"], f"{w}.senses")
            if not 3 <= len(senses) <= 5:
                self.fail(f"{w}.senses: needs 3 to 5 cues")
            u.places[pid] = Place(
                pid, self.text(pv["name"], w), self.texts(pv.get("aliases"), w), senses,
                tuple(self.ref(q, ("place",), f"{w}.exits") for q in self.list(pv["exits"], f"{w}.exits")),
                bool(pv.get("rest")), ())
        for tid, tv in sections["things"].items():
            w = f"things.{tid}"
            tv = self.map(tv, w, {"name", "aliases", "look", "at", "uses", "clue", "hidden"}, ("name", "look", "at"))
            uses = None if tv.get("uses") is None else self.int(tv["uses"], f"{w}.uses", 1)
            u.things[tid] = Thing(tid, self.text(tv["name"], w), self.texts(tv.get("aliases"), w),
                                  self.text(tv["look"], w), self.ref(tv["at"], ("place", "agent"), f"{w}.at"), uses)
            if uses:
                # what is left, counted down from the first value a flag starts at
                u.flags[f"uses.{tid}"] = tuple(range(uses, -1, -1))
        # Complications and favors come later, after all ids exist.
        for cid, cv in sections["characters"].items():
            u.agents[cid] = self.agent(cid, cv, f"characters.{cid}", None)
        for lid, lv in sections["latents"].items():
            w = f"latents.{lid}"
            lv = self.map(lv, w, {"name", "when", "text", "brings", "effects"}, ("name", "when", "text"))
            brings = []
            for bid, bv in self.map(lv.get("brings"), f"{w}.brings").items():
                if self.kinds[bid] == "thing":
                    bv = self.map(bv, f"{w}.brings.{bid}", {"name", "aliases", "look"}, ("name", "look"))
                    u.things[bid] = Thing(bid, self.text(bv["name"], w), self.texts(bv.get("aliases"), w),
                                          self.text(bv["look"], w), None)
                else:
                    u.agents[bid] = self.agent(bid, bv, f"{w}.brings.{bid}", lid)
                brings.append(bid)
            self.pending.append((lid, lv, tuple(brings)))
            u.props[lid] = Prop(lid, self.text(lv["text"], w), tuple(brings), tuple(brings), (), "latent")

        for sec, table in (("places", u.places), ("characters", u.agents), ("things", u.things),
                           ("obstacles", None)):
            for i, v in sections[sec].items():
                v = self.map(v, f"{sec}.{i}")
                if v.get("hidden") is not None:
                    u.props[f"{i}.hidden"] = Prop(f"{i}.hidden", self.text(v["hidden"], f"{sec}.{i}.hidden"),
                                                  (i,), (i,), (), "hidden")
                if v.get("clue") is not None:
                    u.props[f"{i}.clue"] = Prop(f"{i}.clue", self.text(v["clue"], f"{sec}.{i}.clue"),
                                                (i,), (), (), "clue")
        for cid, cv in sections["characters"].items():
            for b, bv in self.map(cv.get("beliefs"), f"characters.{cid}.beliefs").items():
                bw = f"characters.{cid}.beliefs.{b}"
                # A belief used as a reliance was labelled by its sentence, full stop and all ("…꺼져 있다.에 기대어",
                # qa_test/runs/goal-6-bold 16), so it may carry a short title.
                if isinstance(bv, dict):
                    bv = self.map(bv, bw, {"title", "text"}, ("title", "text"))
                    u.props[b] = Prop(b, self.text(bv["text"], bw), (), (), (), "belief", self.text(bv["title"], f"{bw}.title"))
                else:
                    u.props[b] = Prop(b, self.text(bv, bw), (), (), (), "belief")
            for t, tv in self.map(cv.get("topics"), f"characters.{cid}.topics").items():
                if "text" in tv:
                    u.props[t] = Prop(t, self.text(tv["text"], f"characters.{cid}.topics.{t}"), (), (), (), "topic")
        for c, cv in sections["claims"].items():
            w = f"claims.{c}"
            cv = self.map(cv, w, {"text", "against"}, ("text", "against"))
            against = self.ref(cv["against"], ("prop",), f"{w}.against")
            u.claims[c] = against
            u.props[c] = Prop(c, self.text(cv["text"], w), (), (), (against,), "claim")
        for pid, prop in u.props.items():
            for x in prop.shows:
                u.shows[x] = u.shows.get(x, ()) + (pid,)

        for oid, ov in sections["obstacles"].items():
            u.obstacles[oid] = self.obstacle(oid, ov)
        for cid, weight, eff in (("engine.snag", "light", ("tag", PLAYER, "snag", "scene", None)),
                                 ("engine.beat", "light", ("set", "stat", (PLAYER, "beats"), "+1")),
                                 ("engine.wound", "heavy", WOUND),
                                 ("engine.end", "heavy", ("scene_end",))):
            u.engine_complications[cid] = Complication(cid, cid, weight, TRUE, (eff,), None)
        for pid, pv in sections["places"].items():
            comps = self.complications(pv.get("complications"), f"places.{pid}", pid)
            u.places[pid] = _replace(u.places[pid], complications=comps)
        for cid, cv in sections["characters"].items():
            u.agents[cid] = self.agent_parts(u.agents[cid], cv, f"characters.{cid}")
        for lid, lv, brings in self.pending:
            w = f"latents.{lid}"
            for bid in brings:
                if bid in u.agents:
                    u.agents[bid] = self.agent_parts(u.agents[bid], self.map(lv["brings"], w)[bid], f"{w}.brings.{bid}")
            u.latents[lid] = Latent(lid, self.text(lv["name"], w), self.cond(lv["when"], f"{w}.when"), brings,
                                    self.effects(lv.get("effects"), f"{w}.effects"))

        for k, cv in enumerate(chapters, 1):
            w = f"chapters[{k}]"
            last = k == len(chapters)
            dl = cv["deadline"]
            ending = dl.get("ending")
            if ending is not None:
                if ending not in sections["endings"] or ending == "collapse":
                    self.fail(f"{w}.deadline.ending: {ending!r} is not an ending other than collapse")
            elif last:
                self.fail(f"{w}.deadline: the last chapter's deadline needs an ending")
            if last and cv.get("goal") is not None:
                self.fail(f"{w}: the last chapter has no goal")
            if not last and cv.get("goal") is None:
                self.fail(f"{w}: needs a goal")
            arrival = self.effects(dl.get("effects"), f"{w}.deadline.effects")
            arrival += (("end", ending),) if ending else (("chapter_to", k + 1, (), True),)
            crisis = self.effects(cv["clock"]["crisis"], f"{w}.clock.crisis")
            if not crisis:
                self.fail(f"{w}.clock.crisis: needs at least one effect")
            u.obstacles[f"deadline.{k}"] = _replace(u.obstacles[f"deadline.{k}"], arrival=arrival)
            u.chapters.append(Chapter(k, self.text(cv["title"], w), self.text(cv["aim"], f"{w}.aim"), self.opt_cond(cv.get("goal"), f"{w}.goal"),
                                      self.effects(cv.get("goal_effects"), f"{w}.goal_effects"),
                                      f"clock.{k}", f"deadline.{k}", crisis))
        for oid, ov in sections["threats"].items():
            w = f"threats.{oid}"
            ov = self.map(ov, w, {"name", "boxes", "appears_when", "arrival"}, ("name", "boxes", "appears_when"))
            u.obstacles[oid] = _replace(u.obstacles[oid], name=self.text(ov["name"], w),
                                        appears_when=self.cond(ov["appears_when"], f"{w}.appears_when"),
                                        arrival=self.effects(ov.get("arrival"), f"{w}.arrival"))
        for oid, ov in sections["forks"].items():
            w = f"forks.{oid}"
            ov = self.map(ov, w, {"name", "boxes", "appears_when", "choices", "default"},
                          ("name", "boxes", "appears_when", "choices", "default"))
            choices = []
            for ch, cv in self.map(ov["choices"], f"{w}.choices").items():
                self.new_id(ch, "choices", None, f"{w}.choices.{ch}")
                cv = self.map(cv, f"{w}.choices.{ch}", {"name", "effects"}, ("name",))
                choices.append((ch, self.text(cv["name"], w), self.effects(cv.get("effects"), f"{w}.choices.{ch}")))
            if len(choices) < 2:
                self.fail(f"{w}.choices: needs two or more")
            d = self.map(ov["default"], f"{w}.default", {"name", "effects"}, ("name",))
            default = (self.text(d["name"], w), self.effects(d.get("effects"), f"{w}.default.effects"))
            u.obstacles[oid] = _replace(u.obstacles[oid], name=self.text(ov["name"], w),
                                        appears_when=self.cond(ov["appears_when"], f"{w}.appears_when"),
                                        choices=tuple(choices), default=default, arrival=default[1])
        for eid, ev in sections["endings"].items():
            w = f"endings.{eid}"
            ev = self.map(ev, w, {"title", "when", "frame"}, ("title", "frame"))
            if eid == "collapse" and ev.get("when") is not None:
                self.fail(f"{w}: collapse has no when")
            u.endings[eid] = Ending(eid, self.text(ev["title"], w), self.opt_cond(ev.get("when"), f"{w}.when"),
                                    self.text(ev["frame"], w))
        pointed = {c.get("deadline", {}).get("ending") for c in chapters}
        for eid, e in u.endings.items():
            if eid != "collapse" and e.when is None and eid not in pointed:
                self.fail(f"endings.{eid}: an ending without when must be named by a deadline")

        # One engine favor pattern per character with a favor, and one per wanted thing shown (rule.md 5.1).
        for aid, ag in u.agents.items():
            if ag.favor is not None:
                u.favor_patterns[aid] = len(u.patterns)
                u.patterns.append(compile_pattern(f"talk:{aid}:favor", ("success", "none")))
            for x in ag.wants:
                u.show_patterns[(x, aid)] = len(u.patterns)
                u.patterns.append(compile_pattern(f"show:{x}:{aid}", None))
            # What a failed talk teaches (rule.md 5.1): the person's desire, as something the player can know.
            u.props[f"{aid}.desire"] = Prop(f"{aid}.desire", ko.fill(ko.DESIRE_FACT, name=ag.name, desire=ag.desire),
                                            (), (), (), "desire", ko.fill(ko.DESIRE_TITLE, name=ag.name))

        # Triggers, in weaving order (story.md 3.11).
        woven = []
        for sub in ("threat", "fork"):
            for oid, o in u.obstacles.items():
                if o.sub == sub:
                    woven.append(Trigger(f"appear.{oid}", o.appears_when, (("move", oid, PLAYER),), False, "appear"))
        for tid, tv in sections["triggers"].items():
            w = f"triggers.{tid}"
            tv = self.map(tv, w, {"when", "effects", "repeat"}, ("when",))
            repeat = tv.get("repeat") is True
            woven.append(Trigger(tid, self.cond(tv["when"], f"{w}.when"), self.effects(tv.get("effects"), w),
                                 repeat, "story"))
        for ch in u.chapters:
            if ch.goal is not None:
                woven.append(Trigger(f"goal.{ch.k}", conj(("flag", "chapter", ch.k), ch.goal),
                                     (("chapter_to", ch.k + 1, ch.goal_effects),), False, "goal"))
        for eid, e in u.endings.items():
            if e.when is not None:
                woven.append(Trigger(f"end.{eid}", e.when, (("end", eid),), False, "ending"))
        for t in woven:
            if t.repeat:
                u.triggers.append(t)
            else:
                fired = f"fired_{t.id}"
                u.flags[fired] = (0, 1)
                u.triggers.append(Trigger(t.id, conj(t.when, ("not", ("flag", fired, 1))),
                                          t.effects + (("set", "flag", (fired,), 1),), False, t.kind))
        u.witnesses = self.map(r["witnesses"], "witnesses", {"creation", "paths"}, ("paths",))
        return u

    def agent(self, cid, cv, w, latent) -> Agent:
        cv = self.map(cv, w, {"name", "aliases", "pronoun", "voice", "desire", "fear", "persona", "at", "regards",
                              "beliefs", "wants", "topics", "favor", "avoids", "knows", "clue", "hidden", "complications"},
                      ("name", "pronoun", "voice", "desire", "fear", "persona") + (("at",) if latent is None else ()))
        if cv["persona"] not in ko.PERSONAS:
            self.fail(f"{w}.persona: one of {', '.join(ko.PERSONAS)}")
        if latent is not None and cv.get("at") is not None:
            self.fail(f"{w}.at: what a latent brings has no at")
        reg = self.map(cv.get("regards"), f"{w}.regards", set(AXES))
        knows = self.texts(cv.get("knows"), f"{w}.knows")
        if len(knows) > KNOWS:
            self.fail(f"{w}.knows: at most {KNOWS} sentences")
        return Agent(cid, self.text(cv["name"], w), self.texts(cv.get("aliases"), w), self.text(cv["pronoun"], w),
                     self.text(cv["voice"], w), self.text(cv["desire"], w), self.text(cv["fear"], w), cv["persona"],
                     self.ref(cv["at"], ("place",), f"{w}.at") if latent is None else None,
                     {ax: self.int(reg.get(ax, 0), f"{w}.regards.{ax}", -3, 3) for ax in AXES},
                     tuple(self.map(cv.get("beliefs"), f"{w}.beliefs")), (), (), None, (),
                     tuple(self.ref(q["place"] if isinstance(q, dict) else q, ("place",), f"{w}.avoids")
                           for q in self.list(cv.get("avoids"), f"{w}.avoids")),
                     knows)

    def agent_parts(self, ag: Agent, cv, w) -> Agent:
        wants = tuple(self.ref(x, ("thing",), f"{w}.wants") for x in self.list(cv.get("wants"), f"{w}.wants"))
        topics = []
        for t, tv in self.map(cv.get("topics"), f"{w}.topics").items():
            tw = f"{w}.topics.{t}"
            tv = self.map(tv, tw, {"title", "text", "reveals", "free_when"}, ("title",))
            if ("text" in tv) == ("reveals" in tv):
                self.fail(f"{tw}: needs exactly one of text and reveals")
            if "reveals" in tv:
                x = tv["reveals"]
                if f"{x}.hidden" not in self.u.props:
                    self.fail(f"{tw}.reveals: {x!r} has no hidden sentence")
                prop = f"{x}.hidden"
            else:
                prop = t
            topics.append(Topic(t, self.text(tv["title"], tw), prop, self.opt_cond(tv.get("free_when"), f"{tw}.free_when")))
        favor = None
        if cv.get("favor") is not None:
            fw = f"{w}.favor"
            fv = self.map(cv["favor"], fw, {"label", "effects", "promise"}, ("label", "promise"))
            pr = self.map(fv["promise"], f"{fw}.promise", {"name", "keep", "break"}, ("name", "keep"))
            favor = Favor(self.text(fv["label"], fw), self.effects(fv.get("effects"), f"{fw}.effects"),
                          self.text(pr["name"], fw), self.cond(pr["keep"], f"{fw}.promise.keep"),
                          self.opt_cond(pr.get("break"), f"{fw}.promise.break"))
        comps = self.complications(cv.get("complications"), w, ag.id)
        until = {}
        for i, q in enumerate(self.list(cv.get("avoids"), f"{w}.avoids")):
            if isinstance(q, dict):
                q = self.map(q, f"{w}.avoids[{i}]", {"place", "until"}, ("place", "until"))
                until[q["place"]] = self.cond(q["until"], f"{w}.avoids[{i}].until")
        return _replace(ag, wants=wants, topics=tuple(topics), favor=favor, complications=comps, until=until)

    def obstacle(self, oid, ov) -> Obstacle:
        w = f"obstacles.{oid}"
        ov = self.map(ov, w, {"name", "aliases", "look", "at", "boxes", "risk", "fits", "clashes", "blocks",
                              "solutions", "clue", "hidden", "complications"},
                      ("name", "look", "at", "solutions"))
        sols = []
        for sid, sv in self.map(ov["solutions"], f"{w}.solutions").items():
            sw = f"{w}.solutions.{sid}"
            self.new_id(sid, "solutions", None, sw)
            sv = self.map(sv, sw, {"label", "approach", "rely", "when"}, ("label", "approach"))
            rely = None
            if sv.get("rely") is not None:
                x = sv["rely"]
                k = self.kinds.get(x)
                if k == "thing":
                    rely = f"thing:{x}"
                elif k == "prop":
                    rely = f"prop:{x}"
                else:
                    self.fail(f"{sw}.rely: {x!r} is not a thing or a proposition")
            sols.append(Solution(sid, self.text(sv["label"], sw), self.choice(sv["approach"], APPROACHES, sw),
                                 rely, self.cond(sv["when"], f"{sw}.when") if sv.get("when") is not None else TRUE))
        if len(sols) < 2 or len({s.approach for s in sols}) != len(sols):
            self.fail(f"{w}.solutions: needs two or more with different approaches")
        return Obstacle(
            id=oid, sub="plain", name=self.text(ov["name"], w), aliases=self.texts(ov.get("aliases"), w),
            look=self.text(ov["look"], w), at=self.ref(ov["at"], ("place",), f"{w}.at"),
            boxes=self.u.obstacles[oid].boxes,
            risk=self.choice(ov.get("risk", "normal"), STORY_RISKS, f"{w}.risk"),
            fits=tuple(self.choice(x, APPROACHES, f"{w}.fits") for x in self.list(ov.get("fits"), w)),
            clashes=tuple(self.choice(x, APPROACHES, f"{w}.clashes") for x in self.list(ov.get("clashes"), w)),
            blocks=tuple(self.ref(x, ("place", "thing", "agent", "obstacle"), f"{w}.blocks")
                         for x in self.list(ov.get("blocks"), w)),
            solutions=tuple(sols), complications=self.complications(ov.get("complications"), w, oid))

    def complications(self, raw, w, host) -> tuple[Complication, ...]:
        out = []
        for cid, cv in self.map(raw, f"{w}.complications").items():
            cw = f"{w}.complications.{cid}"
            self.new_id(cid, "complications", None, cw)
            cv = self.map(cv, cw, {"name", "weight", "when", "effects", "wound"}, ("name", "weight"))
            effects = self.effects(cv.get("effects"), f"{cw}.effects")
            if cv.get("wound") is not None:
                effects += (WOUND,) * self.int(cv["wound"], f"{cw}.wound", 1)
            if not effects:
                self.fail(f"{cw}: needs effects or wound")
            out.append(Complication(cid, self.text(cv["name"], cw), self.choice(cv["weight"], WEIGHTS, cw),
                                    self.cond(cv["when"], f"{cw}.when") if cv.get("when") is not None else TRUE,
                                    effects, host))
        return tuple(out)




def build(raw: dict, digest: str) -> Universe:
    return _Builder(raw, digest).build()
