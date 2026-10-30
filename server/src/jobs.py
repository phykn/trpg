from __future__ import annotations

from .lang.context import pace
from .locale import ko
from .narrate import (
    GROWN_CHARS,
    GROWN_SENTENCES,
    RECAP_CHARS,
    RECAP_SENTENCES,
    REPLY_SIZE,
    SHORT_CHARS,
    Job,
    change_ids,
    ledger,
    step_lines,
)
from .onto.atoms import PLAYER
from .onto.save import Game, replay
from .onto.universe import Universe
from .onto.view import observe
from .rules.acts import parse
from .rules.recommend import recommend
from .rules.schemas import small_talk
from .view import action_label, rely_label

PREVIOUS_TURNS = 3
SAID = 4                # earlier exchanges per speaker handed to narration (engine.md 5.1)
SHARED = 4              # events lived together per speaker (ontology.md 3.4)
RECAP_NOTABLE = 5
RECAP_PEOPLE = 4


def observed(u: Universe, g: Game, t1: int):
    s, log = replay(u, g.creation, g.log.events[:t1 + 1])
    return observe(u, s, log)

def turn_job(u: Universe, g: Game, n: int) -> Job | None:
    p = g.presentation
    turn = next((x for x in p["turns"] if x["n"] == n), None)
    if turn is None:
        return None
    o = observed(u, g, turn["t1"])
    changes = [c for r in turn["steps"] for c in r["changes"]]
    happened, delta, ids, named = [], [], set(), []
    for r in turn["steps"]:
        lines, told = step_lines(u, r)
        happened += lines
        delta += told
        ids |= change_ids(r)
        named += r["action"].split(";")[0].split(":")[1:]
        named += [c["id"] for c in r["changes"] if c["kind"] == "follow" or c.get("with")]
    here = o.facts.where(PLAYER)
    people = {x for x in o.seen if x in u.agents and o.facts.where(x) == here}
    speakers = [x for x in dict.fromkeys(named) if x in people]
    # A companion who stayed is out of sight once the player has gone, so where they stayed is where the player
    # left; reading it from the view gave None and broke the narration (qa_test/runs/play-3-talker 33).
    went = next((c["from"] for c in changes if c["kind"] == "move" and c["id"] == PLAYER), None)
    left = {c["id"]: q for c in changes
            if c["kind"] == "follow" and c["state"] == "stop" and (q := o.facts.where(c["id"]) or went) and q != here}
    joined = tuple(c["id"] for c in changes if c["kind"] == "follow" and c["state"] == "start")
    tags = [{"index": i, "slot": atom[4], "owner": atom[1], "name": name}
            for i, (atom, t, name) in enumerate(p["tags"])
            if turn["t0"] <= t <= turn["t1"] and o.facts.mark_.get((atom[1], atom[4])) == tuple(atom[2:4])]
    kinds = {c["kind"] for c in changes}
    paced = tuple(dict.fromkeys(c["id"] for c in changes if c["kind"] == "fill" and c["id"] in u.obstacles
                                and u.obstacles[c["id"]].sub in ("clock", "deadline")
                                and pace(c["from"], u.boxes(c["id"])) != pace(c["to"], u.boxes(c["id"]))))
    ending = next((c["id"] for c in changes if c["kind"] == "ending"), None)
    previous = [p["narration"][str(m)]["text"] for m in range(max(1, n - PREVIOUS_TURNS), n)
                if str(m) in p["narration"]]
    grown = all(r["action"].startswith("grow:") for r in turn["steps"])
    progress = {c["id"]: c["to"] >= u.boxes(c["id"]) for c in changes
                if c["kind"] == "fill" and c["to"] > c["from"]}
    blocked = tuple(r["label"] for r in turn["steps"] if r["result"] == "blocked")
    came = [c for c in changes if c["kind"] in ("crisis", "arrival")]
    struck = tuple(dict.fromkeys(c["name"] for c in came if not c["id"].startswith("deadline.")))
    missed = tuple(dict.fromkeys(c["name"] for c in came if c["id"].startswith("deadline.")))
    asked = tuple(tuple(c["choices"]) for c in changes if c["kind"] == "fork")
    # A blocked step rolls nothing, so nothing was leaned on (rule.md 3.4).
    relied = tuple(dict.fromkeys(rely_label(u, p, o.facts, x) for r in turn["steps"]
                                 if r["result"] != "blocked" and (x := parse(r["action"]).get("rely"))))
    looked = tuple(dict.fromkeys(r["action"].split(":")[1] for r in turn["steps"]
                                 if r["action"].startswith("look:") and r["result"] != "blocked"))
    actions = [parse(r["action"]) for r in turn["steps"]]
    shown = tuple(dict.fromkeys(u.name(a.intent[0]) for a, r in zip(actions, turn["steps"])
                                if a.schema == "show" and r["result"] != "blocked"))
    tried = bool(turn["text"]) and any(a.schema == "try" and a.intent[0] != PLAYER and r["roll"]
                                       for a, r in zip(actions, turn["steps"]))
    reply, hint = "act", None
    if all(small_talk(a) for a in actions) and not blocked:
        reply = "talk"
    elif any(r.get("within") for r in turn["steps"]):
        reply, happened = "within", [ko.fill(ko.HAPPENED_WITHIN, place=u.name(here))]
    elif all(a.schema == "try" and a.intent[0] == PLAYER for a in actions):
        # the idle label would leak ("말한 대로 행동을 이어갑니다"), and anyone here may answer (engine.md 5.2)
        reply, happened, speakers = "muse", [ko.HAPPENED_MUSE], sorted(people, key=u.rank)
        # a player who talks to themself mostly does not know what to do next (engine.md 5.2)
        hinted = {p["narration"].get(str(m), {}).get("hint") for m in range(max(1, n - PREVIOUS_TURNS), n)}
        forward = recommend(u, o)
        if way := next((a for a in forward if str(a) not in hinted), forward[0] if forward else None):
            hint = (str(way), action_label(u, o, p, way))
            ids |= {x for x in way.intent if x in u.places or x in u.agents or x in u.obstacles or x in u.things}
    # What each speaker said before the previous narration, which alone let an answer drift (engine.md 5.1).
    texts = {x["n"]: x.get("text") or "" for x in p["turns"]}
    said: dict[str, list] = {}
    for m in range(1, n - PREVIOUS_TURNS):
        for x, lines in p["narration"].get(str(m), {}).get("said", {}).items():
            if x in speakers:
                said.setdefault(x, []).append((texts.get(m, ""), lines))
    said = {x: rows[-SAID:] for x, rows in said.items()}
    shared = lived(u, o, [m for m in p["turns"] if m["n"] < n - PREVIOUS_TURNS], speakers)
    size = {"sentences": GROWN_SENTENCES, "chars": GROWN_CHARS} if grown else \
        dict(zip(("sentences", "chars"), REPLY_SIZE[reply])) if reply != "act" and not kinds & {"chapter", "ending"} \
        else {"chars": SHORT_CHARS if kinds & {"chapter", "ending"} else Job.chars}
    return Job(u, o, p, happened, delta, {PLAYER, here, *people, *ids}, text=turn["text"], tags=tags,
               previous=previous, ending=u.endings[ending].frame if ending else None, speakers=speakers, left=left,
               joined=joined, unfinished=turn.get("unfinished"), grown=grown, progress=progress, blocked=blocked,
               relied=relied, looked=looked, asked=asked, struck=struck, missed=missed, reply=reply, said=said, shared=shared,
               hint=hint, arrived=went is not None, paced=paced, tried=tried, shown=shown, **size)

def recap_job(u: Universe, g: Game, k: int) -> Job | None:
    p = g.presentation
    chapter, notable, closing, closer = 1, [], None, None
    for turn in p["turns"]:
        for r in turn["steps"]:
            if chapter == k and notable_step(u, r):
                notable.append(r)
            kinds = {c["kind"]: c for c in r["changes"]}
            if chapter == k and ("chapter" in kinds or "ending" in kinds):
                closing, closer = turn, r
            if "chapter" in kinds:
                chapter = kinds["chapter"]["to"]
    if closing is None:
        return None
    o = observed(u, g, closing["t1"])
    # What passed with people comes first, whether or not a roll marked it; told from the notable steps alone,
    # the scenery won (qa_test/runs/goal-6-bold 9).
    people = [x["text"] for ch in ledger(u, p) if ch["chapter"] == k for x in ch["lines"]][:RECAP_PEOPLE]
    people += [ko.fill(ko.RECAP_CHOICE, name=c["name"]) for c in p.get("choices", []) if c["chapter"] == k]
    # The step that closed the chapter goes last: without it a recap credited the oil, not the punch that lit
    # the lamp, and told the sky darkening at the ending (qa_test/runs/play-3-bold 21, ui-5).
    chosen = ("choose:", "pay:")       # told by their choice line above
    steps = [*[r for r in notable if r is not closer and not r["action"].startswith(chosen)][1 - RECAP_NOTABLE:], closer]
    lines = [*people, *(x for r in steps for x in step_lines(u, r)[0])]
    task = ko.fill(ko.RECAP_TASK, title=u.chapter_of(k).title, sentences=RECAP_SENTENCES, chars=RECAP_CHARS)
    return Job(u, o, p, lines, lines, {PLAYER, o.facts.where(PLAYER)}, chars=RECAP_CHARS,
               sentences=RECAP_SENTENCES, task=task)


def lived(u, o, turns: list[dict], speakers: list[str]) -> dict[str, list[str]]:
    """Each speaker's events of shared(g), older than the previous narration, as step lines (ontology.md 3.4)."""
    witnessed = {s.t: s.witnesses for s in o.memory}
    out: dict[str, list[str]] = {}
    for turn in turns:
        for r in turn["steps"]:
            for x in speakers:
                if x in witnessed.get(r["t"], ()) and marks(u, r):
                    out.setdefault(x, []).append(". ".join(step_lines(u, r)[0]))
    return {x: lines[-SHARED:] for x, lines in out.items()}


def marks(u, r: dict) -> bool:
    """An event that marks its witnesses: notable, done to a person with a change or a roll, or the player hurt
    (ontology.md 3.4). A refused favor changes nothing, yet left out, 윤슬 later told of the key being lent
    (qa_test/runs/loop-1/long-after r0 t21)."""
    kinds = {c["kind"] for c in r["changes"]}
    person = any(a in u.agents for a in r["action"].split(";")[0].split(":")[1:])
    acted = person and (kinds & {"move", "follow", "promise", "regards", "reveal"} or r["roll"] is not None)
    return notable_step(u, r) or bool(acted) or ("wound" in kinds)


def notable_step(u, r: dict) -> bool:
    schema = r["action"].split(":")[0]
    if schema in ("declare", "choose", "pay") or ";claim=" in r["action"]:
        return True
    # An obstacle overcome is the chapter's work; left out, a recap skipped the door the player broke (play-3-bold 6).
    return any(c["kind"] in ("promise", "wound", "arrival")
               or (c["kind"] == "fill" and (c["to"] - c["from"] >= 2 or c["to"] >= u.boxes(c["id"]) > c["from"]))
               for c in r["changes"])
