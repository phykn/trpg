import hashlib

from .state import (
    STATS,
    apply_change,
    apply_turn,
    is_block_shown,
    is_shown,
    list_people_here,
    write_up,
)

METHOD_STATS = {"soothe": "charm", "press": "might", "trick": "wit", "sneak": "skill", "force": "might"}
TALK_METHODS = ("soothe", "press", "trick")
LOCK_METHODS = ("sneak", "force")


class Refused(ValueError):
    def __init__(self, message, code="not_allowed"):
        super().__init__(message)
        self.code = code


def roll_dice(seed, turn):
    digest = hashlib.sha256(f"{seed}:{turn}".encode()).digest()
    return [digest[0] % 6 + 1, digest[1] % 6 + 1]


def find_stance(story, state, person, topic):
    stance = story.people[person].topics[topic].stance
    block = {"거짓말한다": f"거짓말 {person}.{topic}", "꺼린다": f"꺼림 {person}.{topic}"}.get(stance)
    return "숨기지 않는다" if block in state["opened"] else stance


def find_said_line(story, state, person, topic):
    stance = story.people[person].topics[topic].stance
    if stance == "숨기지 않는다":
        return f"말 {person}.{topic}.참말"
    opened = f"{'거짓말' if stance == '거짓말한다' else '꺼림'} {person}.{topic}" in state["opened"]
    if stance == "꺼린다":
        return f"말 {person}.{topic}.풀린 뒤" if opened else None
    return f"말 {person}.{topic}.{'깨진 뒤' if opened else '거짓말'}"


def list_topics(story, state, person):
    return [t for t, topic in story.people[person].topics.items()
            if is_shown(story, state, f"말 {person}.{t}.{next(iter(topic.branches()))}")]


def find_path(story, state, place):
    book = state["notebook"]
    if f"곳 {place}" not in book or place == state["place"] or not is_shown(story, state, f"곳 {place}"):
        return None
    paths = {state["place"]: []}
    queue = [state["place"]]
    while queue:
        here = queue.pop(0)
        for nxt in story.links[here]:
            if nxt not in paths and f"곳 {nxt}" in book and is_shown(story, state, f"곳 {nxt}"):
                paths[nxt] = paths[here] + [nxt]
                queue.append(nxt)
    return paths.get(place)


def list_blocks_here(story, state):
    here = list_people_here(story, state)
    blocks = []
    for block in story.blocks.values():
        if block.addr in state["opened"] or not is_block_shown(story, state, block.addr):
            continue
        thing = f"볼 것 {block.name}"
        if block.name in here if block.kind != "잠김" else (
                thing in state["notebook"] and story.lines[thing].place == state["place"]):
            blocks.append(block)
    return blocks


def does_fit(story, addr, block):
    line = story.lines[addr]
    if line.branch == "거짓말" or block.kind == "꺼림" and line.kind == "말" and line.name == block.name:
        return False
    return block.wants == line.shows or block.wants in line.props


def find_bet_bonus(story, state, target, method):
    bonus = state["stats"][METHOD_STATS[method]]
    if method in LOCK_METHODS:
        return bonus - story.blocks[target].hard
    person = story.lines[target].name if target in story.lines else story.blocks[target].name
    return bonus + {"soothe": state["attitudes"][person]["trust"], "press": state["attitudes"][person]["fear"]}.get(
        method, 0)


def act(story, state, action, heard=None):
    do = action["do"]
    if state["conclusion"] is not None:
        raise Refused("the game is over")
    if (state["stats"] is None) != (do == "stats"):
        raise Refused("stats come first and once")
    if state["spent"] >= story.head.cells and do not in ("read", "conclude"):
        raise Refused("no cells left")
    turn = Turn(story, state)
    getattr(turn, f"do_{do}")(action, heard)
    return {"state": apply_turn(story, state, turn.changes), "changes": turn.changes, "dice": turn.dice,
            "happened": turn.happened, "talk": turn.talk}


class Turn:
    def __init__(self, story, state):
        self.story = story
        self.state = state
        self.number = state["turn"] + 1
        self.changes = []
        self.forced = ()
        self.fresh = []
        self.dice = None
        self.happened = []
        self.talk = []

    def change(self, op, **fields):
        change = {"op": op, **fields}
        self.state = apply_change(self.story, self.state, change, self.number)
        self.changes.append(change)
        if op == "write":
            self.fresh.append(fields["line"])

    def write_up(self):
        self.state, changes = write_up(self.story, self.state, self.fresh, self.number)
        self.changes += changes
        self.fresh += [c["line"] for c in changes]

    def write_once(self, line):
        if line not in self.state["notebook"]:
            self.change("write", line=line)

    def shift(self, person, axis, by):
        self.change("shift", person=person, axis=axis, by=by)

    def spend(self):
        self.change("spend")
        cell = self.state["spent"]
        for i, event in enumerate(self.story.events):
            if event.at == cell:
                self.settle(i, event)
        for i, event in enumerate(self.story.events):
            if event.omen and event.at == cell + 3 and event.guard not in self.state["opened"]:
                self.happened.append({"omen": i})
        self.write_up()

    def settle(self, i, event):
        if event.guard in self.state["opened"] and i not in self.forced:
            self.change("settle", event=i, result="prevented")
            self.happened.append({"event": i, "result": "prevented"})
            return
        self.change("settle", event=i, result="happened")
        for a in event.acts:
            if a.leave:
                self.change("leave", person=a.leave)
            if a.move:
                self.change("relocate", person=a.move[0], place=a.move[1])
            if a.vanish:
                self.change("vanish", thing=a.vanish)
        if self.state["partner"] and self.state["partner"] not in list_people_here(self.story, self.state):
            self.change("face", person=None)
        self.happened.append({"event": i, "result": "happened"})

    def do_stats(self, action, heard):
        plus2, plus1 = action["plus2"], action["plus1"]
        if plus2 == plus1 or plus2 not in STATS or plus1 not in STATS:
            raise Refused("two different stats")
        self.change("set_stats", stats={s: 2 if s == plus2 else 1 if s == plus1 else 0 for s in STATS})

    def do_ask(self, action, heard):
        kind = heard["kind"]
        person = self.state["partner"]
        if kind == "move":
            return self.do_move({"place": heard["place"]}, None)
        if person is None:
            self.talk.append({"look": self.state["place"]})
            return None
        if kind == "topics":
            shown = list_topics(self.story, self.state, person)
            if not heard["topics"] or any(t not in shown for t in heard["topics"]):
                raise Refused("a topic that is not shown")
            for topic in heard["topics"]:
                self.ask_topic(person, topic)
            self.change("count", person=person, topic=None, value=0)
            self.write_up()
        elif kind == "none":
            passes = self.state["talks"][person]["passes"] + 1
            self.change("count", person=person, topic=None, value=passes)
            self.talk.append({"pass": person})
            if passes >= 3:
                self.lead(person, None)
        elif kind in ("chat", "unsure"):
            self.talk.append({kind: person, **({"topics": heard["topics"]} if kind == "unsure" else {})})
        else:
            raise Refused(f"unknown reading {kind!r}")
        return None

    def ask_topic(self, person, topic):
        if find_stance(self.story, self.state, person, topic) == "꺼린다":
            block = f"꺼림 {person}.{topic}"
            if block not in self.state["withheld"]:
                self.change("withhold", block=block)
            self.talk.append({"withhold": block})
        else:
            line = find_said_line(self.story, self.state, person, topic)
            self.write_once(line)
            self.talk.append({"say": line})
        asked = self.state["talks"][person]["topics"].get(topic, 0) + 1
        self.change("count", person=person, topic=topic, value=asked)
        if asked >= 3:
            self.lead(person, topic)

    def lead(self, person, asked):
        for topic in list_topics(self.story, self.state, person):
            if topic != asked and find_stance(self.story, self.state, person, topic) != "꺼린다" and \
                    find_said_line(self.story, self.state, person, topic) not in self.state["notebook"]:
                self.talk.append({"lead": f"{person}.{topic}"})
                return
        self.talk.append({"done": person})
        for topic in list_topics(self.story, self.state, person):
            block = f"꺼림 {person}.{topic}"
            if find_stance(self.story, self.state, person, topic) == "꺼린다" and block not in self.state["withheld"]:
                self.change("withhold", block=block)

    def do_move(self, action, heard):
        path = find_path(self.story, self.state, action["place"])
        if not path:
            raise Refused("a place that cannot be reached")
        for place in path:
            self.change("move", place=place)
            self.write_up()
            self.spend()
            if self.state["spent"] >= self.story.head.cells:
                break
        here = list_people_here(self.story, self.state)
        self.change("face", person=here[0] if len(here) == 1 else None)

    def do_present(self, action, heard):
        line, target = action["line"], action["target"]
        if line not in self.state["notebook"] or self.story.lines[line].kind not in ("볼 것", "말"):
            raise Refused("present a clue from the notebook")
        blocks = list_blocks_here(self.story, self.state)
        if target in list_people_here(self.story, self.state):
            blocks = [b for b in blocks if b.name == target and b.kind != "잠김"]
        elif target in [b.addr for b in blocks if b.kind == "잠김"]:
            if not self.story.lines[line].props:
                raise Refused("only an item opens a lock")
            blocks = [self.story.blocks[target]]
        else:
            raise Refused("present to someone or something here")
        fits = [b for b in blocks if does_fit(self.story, line, b)]
        for block in sorted(fits, key=lambda b: ("거짓말", "꺼림", "잠김").index(b.kind)):
            self.open_block(block)
            if block.kind == "꺼림":
                self.shift(block.name, "trust", 1)
        if fits:
            self.write_up()
            return
        if target in self.story.people:
            passes = self.state["talks"][target]["passes"] + 1
            self.change("count", person=target, topic=None, value=passes)
            self.talk.append({"pass": target})
            if passes >= 3:
                self.lead(target, None)
        else:
            self.talk.append({"shut": target})
        self.spend()

    def open_block(self, block):
        if block.kind == "거짓말":
            self.change("open", block=block.addr)
            lie = f"말 {block.name}.{block.topic}.거짓말"
            if lie in self.state["notebook"]:
                self.change("strike", line=lie)
            self.write_once(block.opens[0])
            self.shift(block.name, "fear", 1)
            self.talk.append({"say": block.opens[0]})
        elif block.kind == "꺼림":
            if block.addr in self.state["withheld"]:
                self.change("unwithhold", block=block.addr)
            self.change("open", block=block.addr)
            self.write_once(block.opens[0])
            self.talk.append({"say": block.opens[0]})
        else:
            self.change("open", block=block.addr)
            self.talk.append({"open": block.addr})

    def do_bet(self, action, heard):
        target, method = action["target"], action["method"]
        here = list_people_here(self.story, self.state)
        line = self.story.lines.get(target)
        block = self.story.blocks.get(target)
        if line and line.kind == "말" and target in self.state["notebook"] and line.name in here and \
                target not in self.state["struck"] and target not in self.state["judged"] and method in TALK_METHODS:
            person = line.name
        elif block and block.kind == "꺼림" and target in self.state["withheld"] and block.name in here and \
                method in TALK_METHODS:
            person = block.name
        elif block and block.kind == "잠김" and block in list_blocks_here(self.story, self.state) and \
                method in LOCK_METHODS:
            person = block.owner
        else:
            raise Refused("nothing to bet on that way")
        if [target, method] in self.state["closed"]:
            raise Refused("that way is closed")
        eyes = roll_dice(self.state["seed"], self.number)
        total = sum(eyes) + find_bet_bonus(self.story, self.state, target, method)
        won = total >= 8
        self.dice = {"method": method, "eyes": eyes, "total": total, "won": won}
        if won and line:
            self.change("judge", line=target, verdict="lying" if line.branch == "거짓말" else "true")
            self.talk.append({"say": target})
        elif won:
            self.open_block(block)
            self.write_up()
        else:
            self.change("close", target=target, method=method)
            if block:
                self.change("hint", block=target)
            self.talk.append({"say": target} if line else {"withhold": target} if block.kind == "꺼림" else
                             {"shut": target})
        if method == "soothe":
            self.shift(person, "trust", 1 if won else -1)
        elif method == "press":
            if won:
                self.shift(person, "trust", -1)
            self.shift(person, "fear", 1 if won else -1)
        elif not won and person:
            self.shift(person, "trust", -1)
        self.spend()

    def do_face(self, action, heard):
        person = action["person"]
        if person is not None and person not in list_people_here(self.story, self.state):
            raise Refused("face someone here")
        self.change("face", person=person)

    def do_read(self, action, heard):
        lines = [a for a in action["lines"] if a in self.state["notebook"] and a not in self.state["read"]]
        if not lines:
            raise Refused("nothing new to read")
        self.change("read", lines=lines)

    def do_conclude(self, action, heard):
        book = self.state["notebook"]
        who, how, why = action["who"], action["how"], action["why"]
        if who is not None and f"사람 {who}" not in book or any(
                a is not None and (a not in book or self.story.lines[a].kind not in ("볼 것", "말")) for a in (how, why)):
            raise Refused("answer from the notebook")
        self.change("conclude", who=who, how=how, why=why)
