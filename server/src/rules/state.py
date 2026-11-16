STATS = ("charm", "might", "wit", "skill")
# The common impressions and the attitude each leans (game/04 4절); a person's own impressions lean nowhere.
IMPRESSIONS = {"다정": ("trust", 1), "위로": ("trust", 1), "칭찬": ("trust", 1), "선물": ("trust", 1),
               "무례": ("trust", -1), "의심": ("trust", -1), "위협": ("fear", 1), "들킴": ("trust", -1)}


class RuleError(ValueError):
    pass


def start_state(story, seed):
    start = story.head.start
    state = {
        "seed": seed, "turn": 0, "stats": None,
        "notebook": {}, "struck": [], "withheld": [], "hints": [], "judged": {}, "read": [],
        "opened": [], "closed": [], "tried": [], "partner": None,
        "attitudes": {name: {"trust": p.attitude.trust, "fear": p.attitude.fear} for name, p in story.people.items()},
        "talks": {name: {"topics": {}, "passes": 0, "done": False} for name in story.people},
        "spent": 0, "place": start, "visited": [start], "looked": [],
        "events": {}, "where": {name: p.place for name, p in story.people.items()}, "gone": [], "lost": [],
        "conclusion": None,
    }
    state, _ = write_up(story, state, [], 0)
    here = list_people_here(story, state)
    return {**state, "partner": here[0] if len(here) == 1 else None}


def judge_ending(story, state):
    end, truth = state["conclusion"], story.head.truth
    answers = {"who": None if end["who"] is None else end["who"] == truth.who}
    for key, fact in (("how", truth.how), ("why", truth.why)):
        answers[key] = None if end[key] is None else story.lines[end[key]].shows == fact
    if end["who"] is None:
        verdict = "unsolved"
    elif not answers["who"]:
        verdict = "wrong"
    else:
        verdict = "solved" if answers["how"] and answers["why"] else "who_only"
    events = []
    for i, event in enumerate(story.events):
        result = state["events"].get(str(i)) or ("prevented" if event.guard in state["opened"] else None)
        if result:
            events.append([i, result])
    return {"verdict": verdict, "answers": answers, "events": events}


def is_shown(story, state, addr):
    line = story.lines[addr]
    if line.cond and line.cond not in state["notebook"]:
        return False
    if line.lock and line.lock not in state["opened"]:
        return False
    if line.kind == "볼 것" and line.name in state["lost"]:
        return False
    return not (line.kind == "말" and line.name in state["gone"])


def is_block_shown(story, state, addr):
    block = story.blocks[addr]
    if block.cond and block.cond not in state["notebook"]:
        return False
    if block.kind == "잠김":
        return is_shown(story, state, f"볼 것 {block.name}")
    return block.name not in state["gone"]


def list_people_here(story, state):
    return [p for p in story.people if state["where"][p] == state["place"] and p not in state["gone"]]


def write_up(story, state, fresh, turn):
    fresh = list(fresh)
    changes = []
    while writes := list_writes(story, state, fresh):
        for addr in writes:
            change = {"op": "write", "line": addr}
            state = apply_change(state, change, turn)
            changes.append(change)
            fresh.append(addr)
    return state, changes


def list_writes(story, state, fresh):
    place = state["place"]
    things = [a for a, line in story.lines.items() if line.kind == "볼 것" and line.place == place
              and place in state["looked"]]   # what lies in a place is written once the player looks around it
    people = [f"사람 {p}" for p in list_people_here(story, state)]
    places = [f"곳 {place}"] + [f"곳 {p}" for p in story.links[place]]
    told = [t for a in fresh for t in story.lines[a].tells]
    writes = []
    for addr in things + people + places + told:
        if addr not in state["notebook"] and addr not in writes and is_shown(story, state, addr):
            writes.append(addr)
    return writes


def apply_turn(story, state, changes):
    turn = state["turn"] + 1
    new = state
    for change in changes:
        new = apply_change(new, change, turn)
    new = {**new, "turn": turn}
    broken = Invariants(story, state, new, changes).find_broken()
    if broken:
        raise RuleError(f"turn {turn} breaks {broken}")
    return new


def apply_change(state, change, turn):
    op = change["op"]
    if op in ADDS:
        key, field = ADDS[op]
        return {**state, key: add(state[key], change[field])}
    if op == "write":
        return {**state, "notebook": {**state["notebook"], change["line"]: turn}}
    if op not in WRITES:
        raise RuleError(f"unknown change {op!r}")
    return {**state, **WRITES[op](state, change)}


def add(items, item):
    return items if item in items else items + [item]


def shift_attitude(state, change):
    person, axis = change["person"], change["axis"]
    old = state["attitudes"][person]
    return {"attitudes": {**state["attitudes"], person: {**old, axis: max(-1, min(1, old[axis] + change["by"]))}}}


def count_talk(state, change):
    old = state["talks"][change["person"]]
    talk = ({**old, "passes": change["value"]} if change["topic"] is None
            else {**old, "topics": {**old["topics"], change["topic"]: change["value"]}})
    return {"talks": {**state["talks"], change["person"]: talk}}


def record_try(state, change):
    others = [t for t in state["tried"] if (t["line"], t["target"]) != (change["line"], change["target"])]
    return {"tried": others + [{k: change[k] for k in ("line", "target", "blocks")}]}


# The changes of data/04 1절 that add one name to a list: op → (state key, change field).
ADDS = {"look": ("looked", "place"), "strike": ("struck", "line"), "withhold": ("withheld", "block"),
        "hint": ("hints", "block"), "open": ("opened", "block"), "leave": ("gone", "person"),
        "vanish": ("lost", "thing")}
WRITES = {
    "set_stats": lambda _state, change: {"stats": dict(change["stats"])},
    "spend": lambda state, _change: {"spent": state["spent"] + 1},
    "move": lambda state, change: {"place": change["place"], "visited": add(state["visited"], change["place"])},
    "unwithhold": lambda state, change: {"withheld": [b for b in state["withheld"] if b != change["block"]]},
    "judge": lambda state, change: {"judged": {**state["judged"], change["line"]: change["verdict"]}},
    "close": lambda state, change: {"closed": state["closed"] + [[change["target"], change["method"]]]},
    "shift": shift_attitude,
    "settle": lambda state, change: {"events": {**state["events"], str(change["event"]): change["result"]}},
    "relocate": lambda state, change: {"where": {**state["where"], change["person"]: change["place"]}},
    "count": count_talk,
    "done": lambda state, change: {"talks": {**state["talks"], change["person"]: {
        **state["talks"][change["person"]], "done": True}}},
    "face": lambda _state, change: {"partner": change["person"]},
    "read": lambda state, change: {"read": state["read"] + [a for a in change["lines"] if a not in state["read"]]},
    "try": record_try,
    "conclude": lambda _state, change: {"conclusion": {k: change[k] for k in ("who", "how", "why")}},
}


# What every turn keeps (data/05 1절); the first one a turn breaks names the refusal.
class Invariants:
    def __init__(self, story, old, new, changes):
        self.story, self.old, self.new, self.changes = story, old, new, changes
        self.book = new["notebook"]

    def find_broken(self):
        checks = (("final", self.breaks_final), ("ended", self.breaks_ended), ("notebook", self.breaks_notebook),
                  ("shown", self.breaks_shown), ("struck", self.breaks_struck), ("after", self.breaks_after),
                  ("gone", self.breaks_gone), ("withheld", self.breaks_withheld), ("hint", self.breaks_hint),
                  ("judged", self.breaks_judged), ("closed", self.breaks_closed), ("stats", self.breaks_stats),
                  ("place", self.breaks_place), ("partner", self.breaks_partner), ("spent", self.breaks_spent),
                  ("events", self.breaks_events), ("conclusion", self.breaks_conclusion))
        return next((name for name, breaks in checks if breaks()), None)

    def breaks_final(self):
        return self.old["conclusion"] is not None and bool(self.changes)

    def breaks_ended(self):
        return self.old["spent"] == self.story.head.cells and any(
            c["op"] not in ("read", "conclude") for c in self.changes)

    def breaks_notebook(self):
        old = list(self.old["notebook"].items())
        return old != list(self.book.items())[:len(old)] or any(a not in self.story.lines for a in self.book)

    def breaks_shown(self):
        return any(not is_shown(self.story, self.new, a) for a in self.book if a not in self.old["notebook"])

    def breaks_struck(self):
        lies = {f"말 {b.name}.{b.topic}.거짓말": b.addr for b in self.story.blocks.values() if b.kind == "거짓말"}
        opened, struck = self.new["opened"], self.new["struck"]
        return any(a not in self.book or lies.get(a) not in opened for a in struck) or any(
            a in self.book and a not in struck for a, b in lies.items() if b in opened)

    def breaks_after(self):
        return any(a in self.book and b.addr not in self.new["opened"] for b in self.story.blocks.values()
                   for a in b.opens if b.kind != "잠김")

    def breaks_gone(self):
        blocks = self.story.blocks
        return any(b not in self.old["opened"] and blocks[b].name in self.old["gone"] for b in self.new["opened"]
                   if blocks[b].kind != "잠김")

    def breaks_withheld(self):
        return any(not b.startswith("꺼림 ") or b in self.new["opened"] for b in self.new["withheld"])

    def breaks_hint(self):
        closed = [t for t, _ in self.new["closed"]]
        return any(h not in closed or h.startswith("거짓말 ") for h in self.new["hints"])

    def breaks_judged(self):
        return any(a not in self.book or self.story.lines[a].kind != "말" for a in self.new["judged"])

    def breaks_closed(self):
        return len({tuple(c) for c in self.new["closed"]}) != len(self.new["closed"])

    def breaks_stats(self):
        stats = self.new["stats"]
        return stats is not None and (set(stats) != set(STATS) or sorted(stats.values()) != [0, 0, 1, 2])

    def breaks_place(self):
        place = self.new["place"]
        return place not in self.new["visited"] or not is_shown(self.story, self.new, f"곳 {place}")

    def breaks_partner(self):
        partner = self.new["partner"]
        return partner is not None and partner not in list_people_here(self.story, self.new)

    def breaks_spent(self):
        return not self.old["spent"] <= self.new["spent"] <= self.story.head.cells

    def breaks_events(self):
        return any(self.old["events"].get(k, r) != r or self.story.events[int(k)].at > self.new["spent"]
                   for k, r in self.new["events"].items())

    def breaks_conclusion(self):
        end = self.new["conclusion"]
        if not end:
            return False
        clues = [end[k] for k in ("how", "why") if end[k]]
        return bool(end["who"] and f"사람 {end['who']}" not in self.book or any(
            a not in self.book or self.story.lines[a].kind not in ("볼 것", "말") for a in clues))
