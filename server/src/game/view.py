from ..ai.jobs import list_slots
from ..locale import ko
from ..rules.act import (
    LOCK_METHODS,
    METHOD_STATS,
    NEED,
    TALK_METHODS,
    find_bet_bonus,
    find_path,
    list_blocks_here,
    list_topics,
    was_tried,
)
from ..rules.state import STATS, judge_ending, list_people_here
from ..story.load import CASE
from .names import show_clock, show_line, show_name

GROUPS = {"곳": "places", "사람": "people", "물건": "items", "본 것": "seen", "들은 말": "heard", CASE: "heard"}


def make_view(story, state, last=None):
    """`last` is the turn just played, whose typed action may offer dice (engine/02 `offers`)."""
    maker = ViewMaker(story, state, last)
    return maker.make(), maker.acts


class ViewMaker:
    """Builds the view and numbers every act it offers; a command names an act by its id (engine/02 3절)."""

    def __init__(self, story, state, last=None):
        self.story = story
        self.state = state
        self.last = last
        if state["conclusion"] is not None:
            self.stage = "over"
        elif state["stats"] is None:
            self.stage = "start"
        else:
            self.stage = "closing" if state["spent"] >= story.head.cells else "play"
        self.ids = {addr: i for i, addr in enumerate(state["notebook"], 1)}
        self.here = list_people_here(story, state)
        self.locks = [b for b in list_blocks_here(story, state) if b.kind == "잠김"] if self.stage == "play" else []
        self.acts = {}

    def make(self):
        head = self.story.head
        book = self.state["notebook"]
        concluding = self.stage in ("play", "closing")
        return {
            "revision": self.state["turn"],
            "story": {"story": head.name, "title": head.title},
            "stage": self.stage,
            "start": self.make_start() if self.stage == "start" else None,
            "place": self.make_place(),
            "time": self.make_time(),
            "people": self.make_people(),
            "notebook": self.make_notebook(),
            "offers": self.make_offers(),
            "badge": len([a for a in book if a not in self.state["read"]]),
            "conclude": {"who": [self.ids[a] for a in book if self.story.lines[a].kind == "사람"],
                         "clues": [self.ids[a] for a in book if self.story.lines[a].kind in ("볼 것", "말")]}
            if concluding else None,
            "ending": self.make_ending() if self.stage == "over" else None,
        }

    def add_act(self, action, **fields):
        act_id = f"a{len(self.acts) + 1}"
        self.acts[act_id] = action
        return {"id": act_id, **fields}

    def make_start(self):
        acts = [self.add_act({"do": "stats", "plus2": a, "plus1": b}, plus2=a, plus1=b)
                for a in STATS for b in STATS if a != b]
        return {"intro": self.story.head.intro, "stats": [{"key": k, "name": ko.STATS[k]} for k in STATS],
                "acts": acts}

    def make_place(self):
        moves = []
        for addr in self.state["notebook"] if self.stage == "play" else []:
            line = self.story.lines[addr]
            path = find_path(self.story, self.state, line.name) if line.kind == "곳" else None
            if path:
                moves.append(self.add_act({"do": "move", "place": line.name}, name=show_name(self.story, "곳", line.name),
                                          cells=len(path), unvisited=line.name not in self.state["visited"]))
        look = self.add_act({"do": "look"}) if self.stage == "play" else None
        return {"name": show_name(self.story, "곳", self.state["place"]), "moves": moves, "look": look,
                "looked": self.state["place"] in self.state["looked"]}

    def make_time(self):
        left = self.story.head.cells - self.state["spent"]
        clock_text = show_clock(self.story, self.state["spent"])
        # The bar shows the clock and the turns left apart, each by its icon; `text` keeps both for older screens.
        return {"text": ko.time_bar(clock_text, left), "clock": clock_text, "left": left, "last": left <= 3}

    def make_people(self):
        partner = self.state["partner"]
        return [{"name": show_name(self.story, "사람", p), "partner": p == partner,
                 "act": self.add_act({"do": "face", "person": None if p == partner else p})["id"]
                 if self.stage == "play" else None} for p in self.here]

    def make_offers(self):
        tried = [item for item in (self.last or {}).get("talk", []) if "try" in item]
        if self.stage != "play" or not tried:
            return []
        target, method = tried[0]["try"], tried[0]["method"]
        if target in self.story.blocks:
            bets = self.list_bets(target, (method,)) if self.story.blocks[target] in self.locks else []
        elif target in self.here and (aim := self.find_aim(target, method)):
            bets = self.list_bets(aim, (method,), person=show_name(self.story, "사람", target))
        else:
            bets = []
        # A sure action opens the dice at once; a guessed one only offers them (game/07 2절)
        return [{**bet, "now": not tried[0].get("guess")} for bet in bets]

    def find_aim(self, person, method):
        """What an action at a person bets on: what they hold back, else the last thing they said (game/05 3절)."""
        state = self.state
        held = [b.addr for b in self.story.blocks.values() if b.name == person and b.addr in state["withheld"]]
        said = [a for a in state["notebook"] if self.story.lines[a].kind == "말" and self.story.lines[a].name == person
                and a not in state["struck"] and a not in state["judged"]]
        return next((a for a in [*held, *reversed(said)] if [a, method] not in state["closed"]), None)

    def make_notebook(self):
        book = {group: [] for group in GROUPS.values()}
        speakers = []
        for addr in self.state["notebook"]:
            line = self.story.lines[addr]
            if line.kind == "볼 것":
                group = "items" if self.story.things[line.name].item else "seen"
            else:
                group = GROUPS["들은 말" if line.kind == "말" else line.kind]
            book[group].append({
                "id": self.ids[addr], "text": show_line(self.story, addr), "marks": self.list_marks(addr),
                "struck": addr in self.state["struck"], "intro": self.find_intro(line),
                "about": self.list_about(addr), "new": addr not in self.state["read"],
                "acts": self.list_acts(addr) if self.stage == "play" else []})
            if group == "heard":
                speakers.append(line.name)
        # The case heads what was heard; what each person said stays together, people in the order they first spoke.
        order = [CASE, *dict.fromkeys(speakers)]
        book["heard"] = [x for _, x in sorted(zip(speakers, book["heard"], strict=True), key=lambda p: order.index(p[0]))]
        return book

    def list_about(self, addr):
        """The lines a line's sheet gathers: what a person said, what was seen at a place, where a clue was
        found or who said it, and the places and people it told of (game/03 1절)."""
        line, book, lines = self.story.lines[addr], self.state["notebook"], self.story.lines
        if line.kind == CASE:
            return []
        if line.kind == "사람":
            about = [a for a in book if lines[a].kind == "말" and lines[a].name == line.name]
        elif line.kind == "곳":
            about = [a for a in book if lines[a].kind == "볼 것" and lines[a].place == line.name]
        else:
            about = [f"사람 {line.name}" if line.kind == "말" else f"곳 {line.place}", *line.tells]
        return [self.ids[a] for a in dict.fromkeys(about) if a in self.ids and a != addr]

    def find_intro(self, line):
        if line.kind == CASE:
            return line.text
        if line.kind == "곳":
            return self.story.places[line.name].desc if line.name in self.state["visited"] else None
        if line.kind == "사람":
            return self.story.people[line.name].intro
        return self.story.things[line.name].intro if line.kind == "볼 것" else None

    def list_marks(self, addr):
        line, state = self.story.lines[addr], self.state
        if line.kind == "곳":
            return [] if line.name in state["visited"] else [ko.UNVISITED]
        if line.kind == "말":
            return [ko.JUDGED[state["judged"][addr]]] if addr in state["judged"] else []
        own = [b for b in self.story.blocks.values()
               if b.name == line.name and b.kind != "거짓말" and b.addr not in state["opened"]]
        marks = [ko.withheld(b.topic) for b in own if b.addr in state["withheld"]]
        marks += [ko.hint(b.hint) for b in own if b.addr in state["hints"]]
        if line.kind == "볼 것" and f"잠김 {line.name}" in state["opened"]:
            marks.append(ko.OPENED)
        if line.kind == "사람" and line.name in state["gone"]:
            marks.append(ko.GONE)
        return marks

    def list_acts(self, addr):
        line, state = self.story.lines[addr], self.state
        acts = self.list_presents(addr)
        lock = self.story.blocks.get(f"잠김 {line.name}")
        if line.kind == "볼 것" and lock in self.locks:
            items = [a for a in state["notebook"]
                     if self.story.lines[a].kind == "볼 것" and self.story.things[self.story.lines[a].name].item]
            acts += [self.add_act({"do": "present", "line": a, "target": lock.addr}, label=ko.use_item(
                show_name(self.story, "볼 것", self.story.lines[a].name), was_tried(self.story, state, a, lock.addr)))
                for a in items]
            acts += self.list_bets(lock.addr, LOCK_METHODS)
        if line.kind == "말" and line.name in self.here and addr not in state["struck"] and addr not in state["judged"]:
            acts += self.list_bets(addr, TALK_METHODS, person=show_name(self.story, "사람", line.name))
        if line.kind == "사람" and line.name in self.here:
            held = [b for b in self.story.blocks.values() if b.name == line.name and b.addr in state["withheld"]]
            for block in held:
                acts += self.list_bets(block.addr, TALK_METHODS, block.topic if len(held) > 1 else None)
        return acts

    def list_presents(self, addr):
        line, state = self.story.lines[addr], self.state
        partner = state["partner"]
        acts = []
        if line.kind in ("볼 것", "말") and partner:
            acts.append(self.add_act({"do": "present", "line": addr, "target": partner}, label=ko.present_to(
                show_name(self.story, "사람", partner), was_tried(self.story, state, addr, partner))))
        item = line.kind == "볼 것" and self.story.things[line.name].item
        for lock in self.locks if item else []:
            acts.append(self.add_act({"do": "present", "line": addr, "target": lock.addr}, label=ko.use_on(
                show_name(self.story, "볼 것", lock.name), was_tried(self.story, state, addr, lock.addr))))
        return acts

    def list_bets(self, target, methods, topic=None, person=None):
        bets = []
        for method in methods:
            if [target, method] in self.state["closed"]:
                continue
            bonus = find_bet_bonus(self.story, self.state, target, method)
            chance = round(100 * sum(1 for a in range(1, 7) for b in range(1, 7) if a + b + bonus >= NEED) / 36)
            bets.append(self.add_act({"do": "bet", "target": target, "method": method},
                                     label=ko.bet(method, chance, topic, person), roll=self.make_roll(target, method, chance)))
        return bets

    def make_roll(self, target, method, chance):
        """What the dice sheet shows before the roll: who, what is aimed at, the number to reach and what adds to it."""
        story, state = self.story, self.state
        adds = [{"name": ko.STATS[METHOD_STATS[method]], "value": state["stats"][METHOD_STATS[method]]}]
        if method in LOCK_METHODS:
            block = story.blocks[target]
            who, aim = show_name(story, "볼 것", block.name), None
            adds += [{"name": ko.HARD, "value": -block.hard}] if block.hard else []
        else:
            found = story.lines.get(target) or story.blocks[target]
            who = show_name(story, "사람", found.name)
            aim = f"“{found.text}”" if target in story.lines else ko.withheld(found.topic)
            feeling = {"soothe": "trust", "press": "fear"}.get(method)
            adds += [{"name": ko.FEELINGS[feeling], "value": state["attitudes"][found.name][feeling]}] if feeling else []
        return {"title": f"{ko.eul(who)} {ko.METHODS[method]}", "aim": aim, "need": NEED, "adds": adds, "chance": chance}

    def make_ending(self):
        ending = judge_ending(self.story, self.state)
        met, unmet = {"lies": [], "held": [], "locks": []}, {"lies": [], "held": [], "locks": []}
        book = self.state["notebook"]
        for block in self.story.blocks.values():
            if block.addr in self.state["opened"]:
                continue
            if block.kind == "거짓말":
                line = f"말 {block.name}.{block.topic}.거짓말"
                text = ko.said(show_name(self.story, "사람", block.name), self.story.lines[line].text)
                kind, seen = "lies", line in book
            elif block.kind == "꺼림":
                text = ko.missed_topic(show_name(self.story, "사람", block.name), block.topic)
                kind, seen = "held", block.addr in self.state["withheld"]
            else:
                line = f"볼 것 {block.name}"
                text, kind, seen = self.story.lines[line].text, "locks", line in book
            if seen:
                met[kind].append(text)
            else:
                unmet[kind].append(f"{text} · {ko.UNMET[kind]}")
        answers = {k: "blank" if v is None else "hit" if v else "miss" for k, v in ending["answers"].items()}
        # What the player came upon and left closed comes first, then what they never came upon.
        return {"verdict": ending["verdict"], "answers": answers, "turn": self.state["turn"],
                "missed": {k: met[k] + unmet[k] for k in met}}


def make_feed(story, turn, ids, opening=(), after=None):
    """`opening` holds the lines written before the first turn; the first turn tells them as its own notes.

    With `after`, the state after the turn, a person's text carries the topics of theirs not yet heard, which the
    screen underlines where the text names them (game/04 5절)."""
    changes = turn["changes"]
    if turn["action"]["do"] == "stats":
        changes = [{"op": "write", "line": a} for a in opening] + changes
    feed = []
    moves = [c["place"] for c in changes if c["op"] == "move"]
    if moves:
        feed.append({"kind": "move", "text": ko.divider(show_name(story, "곳", moves[-1]), len(moves))})
    dice = turn["dice"]
    if dice:
        feed.append({"kind": "roll", "method": ko.METHODS[dice["method"]], "need": NEED, "eyes": dice["eyes"],
                     "add": dice["total"] - sum(dice["eyes"]), "total": dice["total"], "won": dice["won"]})
    texts = [{"kind": s["kind"], "who": s.get("person") and show_name(story, "사람", s["person"]), "slot": i,
              **({"topics": list_unheard(story, after, s["person"])} if after and s.get("person") else {}),
              **({"topics": [s["guide"]["topic"]]} if s["kind"] == "guide" and "topic" in s["guide"] else {})}
             for i, s in enumerate(list_slots(story, turn))]
    lead = [t for t in texts if t["kind"] in ("text", "ending")]
    return feed + lead + make_notes(story, changes, ids) + texts[len(lead):]


def make_notes(story, changes, ids):
    """One note per kind of news, each pointing at the notebook lines it is about (engine/02 4절)."""
    notes = {}
    struck = {c["line"] for c in changes if c["op"] == "strike"}
    written = [show_name(story, line.kind, line.name) for line in
               (story.lines[c["line"]] for c in changes if c["op"] == "write") if line.kind != "말"]

    def add(key, text, line_id):
        note = notes.setdefault(key, {"kind": "note", "text": "", "lines": []})
        note["text"] = ko.note(text)
        if line_id not in note["lines"]:
            note["lines"].append(line_id)

    for change in changes:
        op = change["op"]
        if op == "write":
            line = story.lines[change["line"]]
            if line.kind != "말":
                add("wrote", ko.wrote(written), ids[line.addr])
            elif f"말 {line.name}.{line.topic}.거짓말" in struck:
                add(("broke", line.name), ko.broke(show_name(story, "사람", line.name)), ids[line.addr])
            else:
                add(("heard", line.name), ko.heard(show_name(story, "사람", line.name)), ids[line.addr])
        elif op in ("withhold", "hint") or (op == "open" and change["block"].startswith("잠김 ")):
            block = story.blocks[change["block"]]
            kind = "볼 것" if block.kind == "잠김" else "사람"
            name = show_name(story, kind, block.name)
            text = ko.held(name, block.topic) if op == "withhold" else ko.hinted(name) if op == "hint" else ko.opened(name)
            add((op, block.addr), text, ids[f"{kind} {block.name}"])
        elif op == "judge":
            line = story.lines[change["line"]]
            add(("judge", line.addr), ko.judged(show_name(story, "사람", line.name), change["verdict"]), ids[line.addr])
    return list(notes.values())


def list_unheard(story, state, person):
    heard = {story.lines[a].topic for a in state["notebook"]
             if story.lines[a].kind == "말" and story.lines[a].name == person}
    return [t for t in list_topics(story, state, person) if t not in heard]
