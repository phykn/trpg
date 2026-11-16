from .act import does_fit, find_path, list_untold
from .state import is_block_shown, list_people_here

STUCK = 4   # turns without a new line before the DM points somewhere (game/07 2절)
HELP = 8   # turns without a new line before the DM helps a little more (game/07 2절)
SIGNS = ("doubt", "held", "warm", "cold", "shaken")   # gestures of the person a turn spoke to, shown every time
HELPS = ("hint_topic", "hint_line", "hint_place")


def make_guide(story, before, after, turn, past):
    """`past` holds what the DM said before, each with its turn (game/07 2절)."""
    do = turn["action"]["do"]
    if do in ("read", "face", "conclude", "stats"):
        return None
    if after["spent"] == story.head.cells and before["spent"] < story.head.cells:
        return {"key": "conclude"}
    sign = find_sign(story, after, turn)
    if sign:
        return sign
    remarks = [g["turn"] for g in past if g["key"] not in SIGNS]
    if after["turn"] - max(remarks, default=0) < 4:
        return None
    return find_remark(story, before, after, turn["changes"], past) or find_nudge(story, after, turn["changes"], past)


def find_sign(story, after, turn):
    changes, here = turn["changes"], list_people_here(story, after)
    lying = [c["line"] for c in changes if c["op"] == "judge" and c["verdict"] == "lying"]
    if lying:
        return {"key": "doubt", "name": story.lines[lying[0]].name}
    held = [story.blocks[item["withhold"]].name for item in turn["talk"] if "withhold" in item]
    if held:
        return {"key": "held", "name": held[0]}
    moved = [c for c in changes if c["op"] == "shift" and c.get("why") == "impression" and c["person"] in here]
    if moved:
        c = moved[-1]
        return {"key": "warm" if c["axis"] == "trust" and c["by"] > 0 else "cold" if c["axis"] == "trust" else "shaken",
                "name": c["person"]}
    return None


def find_remark(story, before, after, changes, past):
    if not any(c["op"] == "move" for c in changes):
        return None
    talked = {p for p, talk in before["talks"].items() if talk["topics"] or talk["passes"]}
    new = [p for p in list_people_here(story, after) if p not in talked]
    if new:
        return {"key": "meet", "name": new[0]}
    if after["place"] not in after["looked"] and ("around", after["place"]) not in [
            (g["key"], g.get("name")) for g in past]:
        return {"key": "around", "name": after["place"]}
    return None


def find_nudge(story, after, changes, past):
    idle = after["turn"] - max(after["notebook"].values())
    if any(c["op"] == "write" for c in changes) or idle < STUCK or idle % STUCK:
        return None
    said = [(g["key"], g.get("name")) for g in past]
    keys = [k for k, _ in said]
    if "ready" not in keys and is_ready(story, after):
        return {"key": "ready"}
    if idle >= HELP:
        helping = next((h for key in HELPS if key not in keys and (h := find_help(story, after, key))), None)
        if helping:
            return helping
    unvisited = [a[2:] for a in after["notebook"] if a.startswith("곳 ") and a[2:] not in after["visited"]]
    around = [] if after["place"] in after["looked"] else [("around", after["place"])]
    here = list_people_here(story, after)
    nudges = around + [("unvisited", p) for p in unvisited] + [("ask", p) for p in here] + [("look", None)]
    fresh = [n for n in nudges if n not in said]   # each nudge once; after that only "look", never twice running
    if not fresh and said[-1] == ("look", None):
        return None
    key, name = fresh[0] if fresh else ("look", None)
    return {"key": key, "name": name} if name else {"key": key}


def is_ready(story, state):
    book = state["notebook"]
    return f"사람 {story.head.truth.who}" in book and all(any(story.lines[a].shows in facts for a in book)
                                                            for facts in story.answers.values())


def find_help(story, state, key):
    book = state["notebook"]
    if key == "hint_topic":
        here = list_people_here(story, state)
        people = [state["partner"], *here] if state["partner"] else here
        topic = next(((p, t) for p in people for t in list_untold(story, state, p)), None)
        return {"key": key, "name": topic[0], "topic": topic[1]} if topic else None
    if key == "hint_line":
        blocks = [b for b in story.blocks.values() if b.addr not in state["opened"] and is_block_shown(story, state, b.addr)]
        line = next((a for a in book if story.lines[a].kind in ("볼 것", "말") and a not in state["struck"]
                     and any(does_fit(story, a, b) for b in blocks)), None)
        return {"key": key, "line": line} if line else None
    place = next((a[2:] for a in book if a.startswith("곳 ") and a[2:] not in state["visited"]
                  and find_path(story, state, a[2:])), None)
    return {"key": key, "name": place} if place else None
