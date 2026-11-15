from .rules.state import list_people_here

STUCK = 3


def make_guide(story, before, after, turn):
    """What the DM says after one turn, in the order of game/07 2절: each part of the game the first time it shows up,
    then a nudge every third turn without a new line."""
    action, changes = turn["action"], turn["changes"]
    if action["do"] in ("read", "face", "conclude"):
        return None
    if after["spent"] == story.head.cells and before["spent"] < story.head.cells:
        return {"key": "conclude"}
    if action["do"] == "stats":
        here = list_people_here(story, after)
        return {"key": "talk", "name": here[0]} if here else {"key": "move"}
    written = [story.lines[c["line"]] for c in changes if c["op"] == "write"]
    speakers = [{story.lines[a].name for a in state["notebook"] if story.lines[a].kind == "말"} for state in (before, after)]
    held = [story.blocks[c["block"]].name for c in changes if c["op"] == "withhold"]

    def has_lock(lines):
        return any(line.kind == "볼 것" and story.things[line.name].lock for line in lines)

    if not speakers[0] and speakers[1]:
        return {"key": "notebook"}
    if len(speakers[0]) < 2 <= len(speakers[1]):
        return {"key": "present"}
    if held and not before["withheld"] and not any(b.startswith("꺼림 ") for b in before["opened"]):
        return {"key": "held", "name": held[0]}
    if any(c["op"] == "strike" for c in changes) and not before["struck"]:
        return {"key": "broke"}
    if has_lock(written) and not has_lock(story.lines[a] for a in before["notebook"]):
        return {"key": "lock"}
    if any("omen" in h for h in turn["happened"]) and not any(
            e.at - 3 <= before["spent"] for e in story.events if e.omen and e.at > 3):
        return {"key": "omen"}
    idle = after["turn"] - max(after["notebook"].values())
    if written or idle < STUCK or idle % STUCK:
        return None
    unvisited = [a[2:] for a in after["notebook"] if a.startswith("곳 ") and a[2:] not in after["visited"]]
    if unvisited:
        return {"key": "unvisited", "name": unvisited[0]}
    here = list_people_here(story, after)
    return {"key": "ask", "name": here[0]} if here else {"key": "look"}
