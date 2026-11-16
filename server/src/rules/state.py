STATS = ("charm", "might", "wit", "skill")


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


def write_up(story, state, fresh, turn):
    fresh = list(fresh)
    changes = []
    while writes := list_writes(story, state, fresh):
        for addr in writes:
            change = {"op": "write", "line": addr}
            state = apply_change(story, state, change, turn)
            changes.append(change)
            fresh.append(addr)
    return state, changes


def add(items, item):
    return items if item in items else items + [item]


def apply_change(story, state, change, turn):
    op = change["op"]
    new = dict(state)
    if op == "set_stats":
        new["stats"] = dict(change["stats"])
    elif op == "spend":
        new["spent"] = state["spent"] + 1
    elif op == "look":
        new["looked"] = add(state["looked"], change["place"])
    elif op == "move":
        new["place"] = change["place"]
        new["visited"] = add(state["visited"], change["place"])
    elif op == "write":
        new["notebook"] = {**state["notebook"], change["line"]: turn}
    elif op == "strike":
        new["struck"] = add(state["struck"], change["line"])
    elif op == "withhold":
        new["withheld"] = add(state["withheld"], change["block"])
    elif op == "unwithhold":
        new["withheld"] = [b for b in state["withheld"] if b != change["block"]]
    elif op == "hint":
        new["hints"] = add(state["hints"], change["block"])
    elif op == "judge":
        new["judged"] = {**state["judged"], change["line"]: change["verdict"]}
    elif op == "open":
        new["opened"] = add(state["opened"], change["block"])
    elif op == "close":
        new["closed"] = state["closed"] + [[change["target"], change["method"]]]
    elif op == "shift":
        person, axis = change["person"], change["axis"]
        old = state["attitudes"][person]
        value = max(-1, min(1, old[axis] + change["by"]))
        new["attitudes"] = {**state["attitudes"], person: {**old, axis: value}}
    elif op == "settle":
        new["events"] = {**state["events"], str(change["event"]): change["result"]}
    elif op == "leave":
        new["gone"] = add(state["gone"], change["person"])
    elif op == "relocate":
        new["where"] = {**state["where"], change["person"]: change["place"]}
    elif op == "vanish":
        new["lost"] = add(state["lost"], change["thing"])
    elif op == "count":
        old = state["talks"][change["person"]]
        talk = ({**old, "passes": change["value"]} if change["topic"] is None
                else {**old, "topics": {**old["topics"], change["topic"]: change["value"]}})
        new["talks"] = {**state["talks"], change["person"]: talk}
    elif op == "done":
        new["talks"] = {**state["talks"], change["person"]: {**state["talks"][change["person"]], "done": True}}
    elif op == "face":
        new["partner"] = change["person"]
    elif op == "read":
        new["read"] = state["read"] + [a for a in change["lines"] if a not in state["read"]]
    elif op == "try":
        new["tried"] = [t for t in state["tried"] if (t["line"], t["target"]) != (change["line"], change["target"])] + [
            {k: change[k] for k in ("line", "target", "blocks")}]
    elif op == "conclude":
        new["conclusion"] = {k: change[k] for k in ("who", "how", "why")}
    else:
        raise RuleError(f"unknown change {op!r}")
    return new


def apply_turn(story, state, changes):
    turn = state["turn"] + 1
    new = state
    for change in changes:
        new = apply_change(story, new, change, turn)
    new = {**new, "turn": turn}
    broken = find_broken(story, state, new, changes)
    if broken:
        raise RuleError(f"turn {turn} breaks {broken}")
    return new


def find_broken(story, old, new, changes):
    book = new["notebook"]
    if old["conclusion"] is not None and changes:
        return "final"
    if old["spent"] == story.head.cells and any(c["op"] not in ("read", "conclude") for c in changes):
        return "ended"
    if list(old["notebook"].items()) != list(book.items())[:len(old["notebook"])] or any(
            a not in story.lines for a in book):
        return "notebook"
    if any(not is_shown(story, new, a) for a in book if a not in old["notebook"]):
        return "shown"
    lies = {f"말 {b.name}.{b.topic}.거짓말": b.addr for b in story.blocks.values() if b.kind == "거짓말"}
    if any(a not in book or lies.get(a) not in new["opened"] for a in new["struck"]) or any(
            a in book and a not in new["struck"] for a, b in lies.items() if b in new["opened"]):
        return "struck"
    if any(a in book and b.addr not in new["opened"] for b in story.blocks.values() for a in b.opens
           if b.kind != "잠김"):
        return "after"
    if any(b not in old["opened"] and story.blocks[b].name in old["gone"] for b in new["opened"]
           if story.blocks[b].kind != "잠김"):
        return "gone"
    if any(not b.startswith("꺼림 ") or b in new["opened"] for b in new["withheld"]):
        return "withheld"
    if any(h not in [t for t, _ in new["closed"]] or h.startswith("거짓말 ") for h in new["hints"]):
        return "hint"
    if any(a not in book or story.lines[a].kind != "말" for a in new["judged"]):
        return "judged"
    if len({tuple(c) for c in new["closed"]}) != len(new["closed"]):
        return "closed"
    if new["stats"] is not None and (set(new["stats"]) != set(STATS) or
                                     sorted(new["stats"].values()) != [0, 0, 1, 2]):
        return "stats"
    if new["place"] not in new["visited"] or not is_shown(story, new, f"곳 {new['place']}"):
        return "place"
    if new["partner"] is not None and new["partner"] not in list_people_here(story, new):
        return "partner"
    if not old["spent"] <= new["spent"] <= story.head.cells:
        return "spent"
    if any(old["events"].get(k, r) != r or story.events[int(k)].at > new["spent"] for k, r in new["events"].items()):
        return "events"
    end = new["conclusion"]
    if end and (end["who"] and f"사람 {end['who']}" not in book or any(
            end[k] and (end[k] not in book or story.lines[end[k]].kind not in ("볼 것", "말")) for k in ("how", "why"))):
        return "conclusion"
    return None
