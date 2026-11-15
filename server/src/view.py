from .locale import ko
from .rules.act import (
    LOCK_METHODS,
    NEED,
    TALK_METHODS,
    find_bet_bonus,
    find_path,
    list_blocks_here,
)
from .rules.state import STATS, judge_ending, list_people_here

GROUPS = {"곳": "places", "사람": "people", "물건": "items", "본 것": "seen", "들은 말": "heard"}


def find_chance(bonus):
    return round(100 * sum(1 for a in range(1, 7) for b in range(1, 7) if a + b + bonus >= 8) / 36)


def find_stage(story, state):
    if state["conclusion"] is not None:
        return "over"
    if state["stats"] is None:
        return "start"
    return "closing" if state["spent"] >= story.head.cells else "play"


def show_name(story, kind, name):
    entry = {"곳": story.places, "사람": story.people, "볼 것": story.things}[kind][name]
    return entry.display or name


def show_line(story, addr):
    line = story.lines[addr]
    if line.kind == "말":
        return ko.said(show_name(story, "사람", line.name), line.text)
    if line.kind == "볼 것" and not story.things[line.name].item:
        return line.text
    return show_name(story, line.kind, line.name)


def find_group(story, addr):
    line = story.lines[addr]
    if line.kind == "볼 것":
        return "물건" if story.things[line.name].item else "본 것"
    return "들은 말" if line.kind == "말" else line.kind


def make_view(story, state):
    maker = ViewMaker(story, state)
    return maker.make(), maker.acts


class ViewMaker:
    def __init__(self, story, state):
        self.story = story
        self.state = state
        self.stage = find_stage(story, state)
        self.ids = {addr: i for i, addr in enumerate(state["notebook"], 1)}
        self.here = list_people_here(story, state)
        self.locks = [b for b in list_blocks_here(story, state) if b.kind == "잠김"] if self.stage == "play" else []
        self.acts = {}

    def add_act(self, action, **fields):
        act_id = f"a{len(self.acts) + 1}"
        self.acts[act_id] = action
        return {"id": act_id, **fields}

    def make(self):
        head = self.story.head
        book = self.state["notebook"]
        clues = [self.ids[a] for a in book if self.story.lines[a].kind in ("볼 것", "말")]
        return {
            "revision": self.state["turn"],
            "story": {"story": head.name, "title": head.title},
            "stage": self.stage,
            "start": self.make_start() if self.stage == "start" else None,
            "place": self.make_place(),
            "time": self.make_time(),
            "people": self.make_people(),
            "notebook": self.make_notebook(),
            "badge": len([a for a in book if a not in self.state["read"]]),
            "conclude": {"who": [self.ids[a] for a in book if self.story.lines[a].kind == "사람"], "clues": clues}
            if self.stage in ("play", "closing") else None,
            "ending": self.make_ending() if self.stage == "over" else None,
        }

    def make_start(self):
        acts = [self.add_act({"do": "stats", "plus2": a, "plus1": b}, plus2=a, plus1=b)
                for a in STATS for b in STATS if a != b]
        return {"intro": self.story.head.intro, "stats": [{"key": k, "name": ko.STATS[k]} for k in STATS],
                "acts": acts}

    def make_place(self):
        moves = []
        if self.stage == "play":
            for addr in self.state["notebook"]:
                line = self.story.lines[addr]
                path = find_path(self.story, self.state, line.name) if line.kind == "곳" else None
                if path:
                    moves.append(self.add_act({"do": "move", "place": line.name}, name=show_name(
                        self.story, "곳", line.name), cells=len(path), unvisited=line.name not in self.state["visited"]))
        return {"name": show_name(self.story, "곳", self.state["place"]), "moves": moves}

    def make_time(self):
        clock = self.story.head.clock
        left = self.story.head.cells - self.state["spent"]
        clock_text = ko.clock(clock.start + self.state["spent"] * clock.step) if clock else None
        return {"text": ko.time_bar(clock_text, left), "left": left, "last": left <= 3}

    def make_people(self):
        partner = self.state["partner"]
        return [{"name": show_name(self.story, "사람", p), "partner": p == partner,
                 "act": self.add_act({"do": "face", "person": None if p == partner else p})["id"]
                 if self.stage == "play" else None} for p in self.here]

    def make_notebook(self):
        book = {group: [] for group in GROUPS.values()}
        speakers = []
        for addr in self.state["notebook"]:
            group = GROUPS[find_group(self.story, addr)]
            book[group].append({
                "id": self.ids[addr], "text": show_line(self.story, addr), "marks": self.list_marks(addr),
                "struck": addr in self.state["struck"], "new": addr not in self.state["read"],
                "acts": self.list_acts(addr) if self.stage == "play" else []})
            if group == "heard":
                speakers.append(self.story.lines[addr].name)
        order = list(dict.fromkeys(speakers))
        book["heard"] = [line for _, line in sorted(zip(speakers, book["heard"], strict=True),
                                                    key=lambda pair: order.index(pair[0]))]
        return book

    def list_marks(self, addr):
        line, state = self.story.lines[addr], self.state
        if line.kind == "곳":
            return [] if line.name in state["visited"] else [ko.UNVISITED]
        if line.kind == "말":
            return [ko.JUDGED[state["judged"][addr]]] if addr in state["judged"] else []
        own = [b for b in self.story.blocks.values() if b.name == line.name and b.kind != "거짓말"
               and b.addr not in state["opened"]]
        marks = [ko.withheld(b.topic) for b in own if b.addr in state["withheld"]]
        marks += [ko.hint(b.hint) for b in own if b.addr in state["hints"]]
        if line.kind == "볼 것" and f"잠김 {line.name}" in state["opened"]:
            marks.append(ko.OPENED)
        if line.kind == "사람" and line.name in state["gone"]:
            marks.append(ko.GONE)
        return marks

    def list_acts(self, addr):
        line, state = self.story.lines[addr], self.state
        acts = []
        partner = state["partner"]
        if line.kind in ("볼 것", "말") and partner:
            acts.append(self.add_act({"do": "present", "line": addr, "target": partner},
                                     label=ko.present_to(show_name(self.story, "사람", partner))))
        item = line.kind == "볼 것" and self.story.things[line.name].item
        for lock in self.locks if item else []:
            acts.append(self.add_act({"do": "present", "line": addr, "target": lock.addr},
                                     label=ko.use_on(show_name(self.story, "볼 것", lock.name))))
        lock = self.story.blocks.get(f"잠김 {line.name}")
        if line.kind == "볼 것" and lock in self.locks:
            for other in state["notebook"]:
                if self.story.lines[other].kind == "볼 것" and self.story.things[self.story.lines[other].name].item:
                    acts.append(self.add_act({"do": "present", "line": other, "target": lock.addr},
                                             label=ko.use_item(show_name(self.story, "볼 것", self.story.lines[other].name))))
            acts += self.list_bets(lock.addr, LOCK_METHODS)
        if line.kind == "말" and line.name in self.here and addr not in state["struck"] and addr not in state["judged"]:
            acts += self.list_bets(addr, TALK_METHODS, person=show_name(self.story, "사람", line.name))
        if line.kind == "사람" and line.name in self.here:
            held = [b for b in self.story.blocks.values() if b.name == line.name and b.addr in state["withheld"]]
            for block in held:
                acts += self.list_bets(block.addr, TALK_METHODS, block.topic if len(held) > 1 else None)
        return acts

    def list_bets(self, target, methods, topic=None, person=None):
        return [self.add_act({"do": "bet", "target": target, "method": m}, label=ko.bet(
            m, find_chance(find_bet_bonus(self.story, self.state, target, m)), topic, person))
            for m in methods if [target, m] not in self.state["closed"]]

    def make_ending(self):
        ending = judge_ending(self.story, self.state)
        missed = {"lies": [], "held": [], "locks": []}
        for block in self.story.blocks.values():
            if block.addr in self.state["opened"]:
                continue
            if block.kind == "거짓말":
                missed["lies"].append(ko.said(show_name(self.story, "사람", block.name),
                                              self.story.lines[f"말 {block.name}.{block.topic}.거짓말"].text))
            elif block.kind == "꺼림":
                missed["held"].append(ko.missed_topic(show_name(self.story, "사람", block.name), block.topic))
            else:
                missed["locks"].append(self.story.lines[f"볼 것 {block.name}"].text)
        answers = {k: "blank" if v is None else "hit" if v else "miss" for k, v in ending["answers"].items()}
        return {"verdict": ending["verdict"], "answers": answers, "turn": self.state["turn"], "missed": missed}


def make_feed(story, turn, ids, opening=()):
    """`opening` holds the lines written before the first turn; the first turn tells them as its own notes."""
    feed = []
    action, changes = turn["action"], turn["changes"]
    if action["do"] == "stats":
        changes = [{"op": "write", "line": a} for a in opening] + changes

    def add_text(kind, who):
        feed.append({"kind": kind, "who": who, "slot": len([f for f in feed if "slot" in f])})

    moves = [c["place"] for c in changes if c["op"] == "move"]
    if moves:
        feed.append({"kind": "move", "text": ko.divider(show_name(story, "곳", moves[-1]), len(moves))})
    if turn["dice"]:
        dice = turn["dice"]
        feed.append({"kind": "roll", "text": ko.roll(dice["method"], dice["eyes"], dice["total"], NEED), "won": dice["won"]})
    if action["do"] == "conclude":
        add_text("ending", None)
    elif action["do"] not in ("face", "read"):
        speaker = next((find_speaker(story, t) for t in turn["talk"] if find_speaker(story, t)), None)
        add_text("text", speaker and show_name(story, "사람", speaker))
    feed += make_notes(story, changes, ids)
    for happened in turn["happened"]:
        if happened.get("result") != "prevented":   # it passes quietly; the ending tells it
            add_text("omen" if "omen" in happened else "event", None)
    if turn.get("guide"):
        add_text("guide", None)
    return feed


def find_speaker(story, talk):
    kind, value = next(iter(talk.items()))
    if kind == "say":
        return story.lines[value].name
    if kind == "withhold":
        return story.blocks[value].name
    if kind == "lead":
        return value.split(".")[0]
    return value if kind in ("pass", "done", "chat", "unsure") else None


def make_notes(story, changes, ids):
    notes = {}
    struck = {c["line"] for c in changes if c["op"] == "strike"}

    def add(key, text, line_id):
        notes.setdefault(key, {"kind": "note", "text": "", "lines": []})
        notes[key]["text"] = ko.note(text) if key != "wrote" else notes[key]["text"]
        if line_id not in notes[key]["lines"]:
            notes[key]["lines"].append(line_id)

    written = []
    for change in changes:
        op = change["op"]
        if op == "write":
            line = story.lines[change["line"]]
            person = line.kind == "말" and show_name(story, "사람", line.name)
            if not person:
                written.append(show_name(story, line.kind, line.name))
                add("wrote", "", ids[change["line"]])
            elif f"말 {line.name}.{line.topic}.거짓말" in struck:
                add(("broke", line.name), ko.broke(person), ids[change["line"]])
            else:
                add(("heard", line.name), ko.heard(person), ids[change["line"]])
        elif op in ("withhold", "hint") or op == "open" and change["block"].startswith("잠김 "):
            block = story.blocks[change["block"]]
            kind = "볼 것" if block.kind == "잠김" else "사람"
            name = show_name(story, kind, block.name)
            text = ko.held(name, block.topic) if op == "withhold" else ko.hinted(name) if op == "hint" else ko.opened(name)
            add((op, block.addr), text, ids[f"{kind} {block.name}"])
        elif op == "judge":
            line = story.lines[change["line"]]
            add(("judge", line.addr), ko.judged(show_name(story, "사람", line.name), change["verdict"]), ids[line.addr])
    if written:
        notes["wrote"]["text"] = ko.note(ko.wrote(written))
    return list(notes.values())
