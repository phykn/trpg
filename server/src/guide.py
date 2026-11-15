from .rules.state import list_people_here

GAP = 4
STUCK = 4


def make_guide(story, before, after, turn, last):
    """When the DM, the host of the table, speaks after a turn (game/07 2절): at the start and when time is up, and
    otherwise at most once every GAP turns, on arriving where someone is not yet talked to, at the first held topic,
    or when nothing new has turned up for a while. `last` is the turn the DM last spoke."""
    action, changes = turn["action"], turn["changes"]
    if action["do"] in ("read", "face", "conclude"):
        return None
    if after["spent"] == story.head.cells and before["spent"] < story.head.cells:
        return {"key": "conclude"}
    if action["do"] == "stats":
        here = list_people_here(story, after)
        return {"key": "open", "name": here[0]} if here else {"key": "open"}
    if after["turn"] - last < GAP:
        return None
    held = [story.blocks[c["block"]].name for c in changes if c["op"] == "withhold"]
    if held and not before["withheld"] and not any(b.startswith("꺼림 ") for b in before["opened"]):
        return {"key": "held", "name": held[0]}
    here = list_people_here(story, after)
    talked = {p for p, talk in before["talks"].items() if talk["topics"] or talk["passes"]}
    new = [p for p in here if p not in talked]
    if new and any(c["op"] == "move" for c in changes):
        return {"key": "meet", "name": new[0]}
    idle = after["turn"] - max(after["notebook"].values())
    if any(c["op"] == "write" for c in changes) or idle < STUCK or idle % STUCK:
        return None
    unvisited = [a[2:] for a in after["notebook"] if a.startswith("곳 ") and a[2:] not in after["visited"]]
    if unvisited:
        return {"key": "unvisited", "name": unvisited[0]}
    return {"key": "ask", "name": here[0]} if here else {"key": "look"}
