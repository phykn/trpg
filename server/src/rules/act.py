import hashlib

from .state import (
    IMPRESSIONS,
    STATS,
    apply_change,
    apply_turn,
    is_block_shown,
    is_shown,
    list_people_here,
    write_up,
)

NEED = 8   # 2d6 + bonus must reach this (game/05 4절)
METHOD_STATS = {"soothe": "charm", "press": "might", "trick": "wit", "sneak": "skill", "force": "might"}
TALK_METHODS = ("soothe", "press", "trick")
LOCK_METHODS = ("sneak", "force")
RUMOR_DELAY = 2   # cells before close people hear of an impression (game/04 4절)


class Refused(ValueError):
    def __init__(self, message, code="not_allowed"):
        super().__init__(message)
        self.code = code


def act(story, state, action, heard=None):
    do = action["do"]
    if state["conclusion"] is not None:
        raise Refused("the game is over")
    if (state["stats"] is None) != (do == "stats"):
        raise Refused("stats come first and once")
    if state["spent"] >= story.head.cells and do not in ("read", "conclude"):
        raise Refused("no cells left")
    turn = Turn(story, state)
    turn.do(action, heard)
    return {"state": apply_turn(story, state, turn.changes), "changes": turn.changes, "dice": turn.dice,
            "happened": turn.happened, "talk": turn.talk}


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
            if is_shown(story, state, f"말 {person}.{t}.{next(iter(topic.list_branches()))}")]


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


def was_tried(story, state, line, target):
    # A present that failed fails again while the target holds nothing it did not hold then.
    here = [b.addr for b in list_blocks_here(story, state) if b.addr == target or b.name == target and b.kind != "잠김"]
    return any(t["line"] == line and t["target"] == target and set(here) <= set(t["blocks"]) for t in state["tried"])


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
    return any(want == line.shows or want in line.props for want in block.wants)


def find_listener(story, state, action):
    """Who the player's words in this action are said to, so they may leave an impression (engine/01 1절)."""
    if state["stats"] is None or state["conclusion"] is not None:
        return None
    target = action.get("target")
    if action["do"] == "ask":
        return state["partner"]
    if action["do"] == "present" and target in list_people_here(story, state):
        return target
    if action["do"] == "bet" and action.get("text"):
        found = story.lines.get(target) or story.blocks.get(target)
        if found and found.kind != "잠김" and found.name in list_people_here(story, state):
            return found.name
    return None


def find_bet_bonus(story, state, target, method):
    bonus = state["stats"][METHOD_STATS[method]]
    if method in LOCK_METHODS:
        return bonus - story.blocks[target].hard
    person = story.lines[target].name if target in story.lines else story.blocks[target].name
    return bonus + {"soothe": state["attitudes"][person]["trust"], "press": state["attitudes"][person]["fear"]}.get(
        method, 0)


class Turn:
    def __init__(self, story, state):
        self.story = story
        self.state = state
        self.number = state["turn"] + 1
        self.changes = []
        self.forced = ()   # events the story check makes happen even when their guard is open
        self.fresh = []
        self.dice = None
        self.happened = []
        self.talk = []

    def do(self, action, heard):
        steps = {
            "stats": lambda: self.do_stats(action["plus2"], action["plus1"]),
            "ask": lambda: self.do_ask(heard),
            "look": self.do_look,
            "move": lambda: self.do_move(action["place"]),
            "present": lambda: self.do_present(action["line"], action["target"]),
            "bet": lambda: self.do_bet(action["target"], action["method"]),
            "face": lambda: self.do_face(action["person"]),
            "read": lambda: self.do_read(action["lines"]),
            "conclude": lambda: self.do_conclude(action["who"], action["how"], action["why"]),
        }
        listener = find_listener(self.story, self.state, action)
        if listener and heard and heard.get("impression"):
            self.impress(listener, heard["impression"])
        steps[action["do"]]()

    def impress(self, person, name):
        """An impression builds up, may move the attitude, and spreads as a rumor (game/04 4절)."""
        known = {*IMPRESSIONS, *self.story.people[person].impressions}
        if name not in known:
            raise Refused(f"an impression {person} cannot take")
        self.change("impress", person=person, impression=name)
        if name in IMPRESSIONS:
            lean = IMPRESSIONS[name]
            total = sum(n for i, n in self.state["impressions"][person].items() if IMPRESSIONS.get(i) == lean)
            if total % 2 == 0:
                self.change("shift", person=person, axis=lean[0], by=lean[1], why="impression")
        here = [p for p in list_people_here(self.story, self.state) if p != person]
        for other in here:
            self.change("rumor", to=other, about=person, impression=name, at=self.state["spent"], seen=True)
        for other in self.story.close[person]:
            if other not in here and other not in self.state["gone"]:
                self.change("rumor", to=other, about=person, impression=name, at=self.state["spent"] + RUMOR_DELAY,
                            seen=False)

    def do_stats(self, plus2, plus1):
        if plus2 == plus1 or plus2 not in STATS or plus1 not in STATS:
            raise Refused("two different stats")
        self.change("set_stats", stats={s: 2 if s == plus2 else 1 if s == plus1 else 0 for s in STATS})

    def do_ask(self, heard):
        kind = heard["kind"]
        person = self.state["partner"]
        if kind == "move":
            self.do_move(heard["place"])
        elif kind == "action" and (person or heard["method"] in LOCK_METHODS):
            self.try_action(person, heard["method"], heard.get("target"))
        elif person is None or kind == "look":
            self.do_look()
        elif kind == "topics":
            self.talk_to(person)
            self.ask_topics(person, heard["topics"])
        elif kind == "none":
            self.talk_to(person)
            self.pass_on(person)
        elif kind in ("chat", "unsure"):
            self.talk_to(person)
            self.talk.append({kind: person, **({"topics": heard["topics"]} if kind == "unsure" else {})})
        else:
            raise Refused(f"unknown reading {kind!r}")

    def try_action(self, person, method, target):
        """A typed action costs no cell; the dice it could bet on are offered as buttons (game/05 3절)."""
        if method in LOCK_METHODS:
            locks = [b.addr for b in list_blocks_here(self.story, self.state) if b.kind == "잠김"]
            if target not in locks:
                raise Refused("no such lock here")
            self.talk.append({"try": target, "method": method})
            return
        if method not in TALK_METHODS:
            raise Refused(f"unknown method {method!r}")
        self.talk_to(person)
        if method == "press" and "위협" not in [c.get("impression") for c in self.changes if c["op"] == "impress"]:
            self.impress(person, "위협")
        self.talk.append({"try": person, "method": method})

    def ask_topics(self, person, topics):
        shown = list_topics(self.story, self.state, person)
        if not topics or any(t not in shown for t in topics):
            raise Refused("a topic that is not shown")
        for topic in topics:
            self.ask_topic(person, topic)
        self.change("count", person=person, topic=None, value=0)
        self.write_up()

    def ask_topic(self, person, topic):
        block = self.find_unlocked(person, topic)
        if block:
            self.open_block(block)
            if block.kind == "꺼림":
                self.shift(block.name, "trust", 1)
        elif find_stance(self.story, self.state, person, topic) == "꺼린다":
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

    def find_unlocked(self, person, topic):
        """A 꺼림 or 거짓말 the person's impressions open when the topic is asked (game/05 1절)."""
        for kind in ("꺼림", "거짓말"):
            block = self.story.blocks.get(f"{kind} {person}.{topic}")
            if block and block.unlock and block.addr not in self.state["opened"] and \
                    self.state["impressions"][person].get(block.unlock, 0) >= block.unlock_count:
                return block
        return None

    def pass_on(self, person):
        passes = self.state["talks"][person]["passes"] + 1
        self.change("count", person=person, topic=None, value=passes)
        self.talk.append({"pass": person})
        if passes >= 3:
            self.lead(person, None)

    def lead(self, person, asked):
        for topic in list_topics(self.story, self.state, person):
            if topic != asked and find_stance(self.story, self.state, person, topic) != "꺼린다" and \
                    find_said_line(self.story, self.state, person, topic) not in self.state["notebook"]:
                self.talk.append({"lead": f"{person}.{topic}"})
                return
        self.talk.append({"done": person})
        if not self.state["talks"][person]["done"]:
            self.change("done", person=person)
        self.mark_held(person)

    def talk_to(self, person):
        # Held topics that appeared after the person was done are marked the next time you talk.
        if self.state["talks"][person]["done"]:
            self.mark_held(person)

    def mark_held(self, person):
        for topic in list_topics(self.story, self.state, person):
            block = f"꺼림 {person}.{topic}"
            if find_stance(self.story, self.state, person, topic) == "꺼린다" and block not in self.state["withheld"]:
                self.change("withhold", block=block)

    def do_look(self):
        self.look_around()
        self.talk.append({"look": self.state["place"]})

    def look_around(self):
        if self.state["place"] not in self.state["looked"]:
            self.change("look", place=self.state["place"])
            self.write_up()

    def do_move(self, place):
        path = find_path(self.story, self.state, place)
        if not path:
            raise Refused("a place that cannot be reached")
        for step in path:   # the way takes the cell, so what happens meanwhile is settled before arriving
            self.change("move", place=step)
            self.spend()
            if self.state["spent"] >= self.story.head.cells:
                break
        here = list_people_here(self.story, self.state)
        self.change("face", person=here[0] if len(here) == 1 else None)

    def do_present(self, line, target):
        if line not in self.state["notebook"] or self.story.lines[line].kind not in ("볼 것", "말"):
            raise Refused("present a clue from the notebook")
        blocks = list_blocks_here(self.story, self.state)
        if target in list_people_here(self.story, self.state):
            self.talk_to(target)
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
        self.change("try", line=line, target=target, blocks=sorted(b.addr for b in blocks))
        if target in self.story.people:
            self.pass_on(target)
        else:
            self.talk.append({"shut": target})
        self.spend()

    def open_block(self, block):
        if block.kind == "꺼림" and block.addr in self.state["withheld"]:
            self.change("unwithhold", block=block.addr)
        self.change("open", block=block.addr)
        lie = f"말 {block.name}.{block.topic}.거짓말"
        if block.kind == "거짓말" and lie in self.state["notebook"]:
            self.change("strike", line=lie)
        if block.kind == "잠김":
            self.talk.append({"open": block.addr})
            return
        self.write_once(block.opens[0])
        if block.kind == "거짓말":
            self.shift(block.name, "fear", 1)
        self.talk.append({"say": block.opens[0]})

    def do_bet(self, target, method):
        person, line, block = self.find_bet(target, method)
        if [target, method] in self.state["closed"]:
            raise Refused("that way is closed")
        if not block or block.kind != "잠김":
            self.talk_to(person)
        eyes = roll_dice(self.state["seed"], self.number)
        total = sum(eyes) + find_bet_bonus(self.story, self.state, target, method)
        won = total >= NEED
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
        self.shift_after_bet(person, method, won)
        self.impress_watchers(person, block, method, won)
        self.spend()

    def impress_watchers(self, person, block, method, won):
        """Deeds leave impressions on whoever watched them and was not their target (game/04 4절)."""
        here = list_people_here(self.story, self.state)
        if method == "press" or method == "trick" and not won:
            for other in [p for p in here if p != person]:
                self.impress(other, "위협" if method == "press" else "들킴")
        elif method in LOCK_METHODS and block.owner in here:
            self.impress(block.owner, "무례")

    def find_bet(self, target, method):
        state = self.state
        here = list_people_here(self.story, state)
        line = self.story.lines.get(target)
        block = self.story.blocks.get(target)
        if line and line.kind == "말" and target in state["notebook"] and line.name in here and \
                target not in state["struck"] and target not in state["judged"] and method in TALK_METHODS:
            return line.name, line, None
        if block and block.kind == "꺼림" and target in state["withheld"] and block.name in here and \
                method in TALK_METHODS:
            return block.name, None, block
        if block and block.kind == "잠김" and block in list_blocks_here(self.story, state) and method in LOCK_METHODS:
            return block.owner, None, block
        raise Refused("nothing to bet on that way")

    def shift_after_bet(self, person, method, won):
        if method == "soothe":
            self.shift(person, "trust", 1 if won else -1)
        elif method == "press":
            if won:
                self.shift(person, "trust", -1)
            self.shift(person, "fear", 1 if won else -1)
        elif not won and person:
            self.shift(person, "trust", -1)

    def do_face(self, person):
        if person is not None and person not in list_people_here(self.story, self.state):
            raise Refused("face someone here")
        self.change("face", person=person)

    def do_read(self, lines):
        lines = [a for a in lines if a in self.state["notebook"] and a not in self.state["read"]]
        if not lines:
            raise Refused("nothing new to read")
        self.change("read", lines=lines)

    def do_conclude(self, who, how, why):
        book = self.state["notebook"]
        if who is not None and f"사람 {who}" not in book or any(
                a is not None and (a not in book or self.story.lines[a].kind not in ("볼 것", "말")) for a in (how, why)):
            raise Refused("answer from the notebook")
        self.change("conclude", who=who, how=how, why=why)

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

    def change(self, op, **fields):
        change = {"op": op, **fields}
        self.state = apply_change(self.state, change, self.number)
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
