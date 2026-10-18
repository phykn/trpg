"""Static checks on a story: ids, references, play rules, and optimistic reachability."""

import re
from collections import Counter

from .schema import PLAYER, Condition, Effect, Story

ID = re.compile(r"^[a-z][a-z0-9_]*$")
TAG_KEYS = {"edge", "snag", "wanted", "suspicion", "reputation"}
TRACES = {"wanted", "suspicion", "reputation"}


def validate(story: Story) -> list[str]:
    errors: list[str] = []
    _ids(story, errors)
    _references(story, errors)
    if not errors:
        errors += _reachability(story)
    return errors


def _ids(story: Story, errors: list[str]) -> None:
    nodes = [*story.places, *story.characters, *story.items, *story.knowledge, *story.skills, *story.quests]
    groups = {
        "node": nodes,
        "obstacle": list(story.obstacles),
        "topic": [t.id for t in story.topics],
        "chapter": [c.id for c in story.chapters],
        "ending": [e.id for e in story.endings],
        "action": [a.id for a in story.actions],
        "trait": [t.id for t in story.traits],
    }
    for group, ids in groups.items():
        for value, count in Counter(ids).items():
            if count > 1:
                errors.append(f"duplicate {group} id: {value}")
        for value in ids:
            if not ID.match(value) or value == PLAYER:
                errors.append(f"invalid {group} id: {value}")


def _references(story: Story, errors: list[str]) -> None:
    def need(table, key, what: str) -> None:
        if key not in table:
            errors.append(f"{what}: unknown id {key!r}")

    chapters = {c.id for c in story.chapters}
    characters = {*story.characters, PLAYER}
    for pid, place in story.places.items():
        need(chapters, place.chapter, f"place {pid}")
        if not 3 <= len(place.senses) <= 5:
            errors.append(f"place {pid}: needs 3 to 5 senses")
        for ex in place.exits:
            need(story.places, ex.to, f"place {pid} exit")
    for cid, c in story.characters.items():
        if c.place:
            need(story.places, c.place, f"character {cid}")
        for kid in c.knows:
            need(story.knowledge, kid, f"character {cid} knows")
        for iid, effects in c.gifts.items():
            need(story.items, iid, f"character {cid} gift")
            _effects(story, effects, f"character {cid} gift", errors)
    for iid, item in story.items.items():
        if item.place and item.holder:
            errors.append(f"item {iid}: has both place and holder")
        if item.place:
            need(story.places, item.place, f"item {iid}")
        if item.holder:
            need(characters, item.holder, f"item {iid} holder")
        if item.reveals:
            need(story.knowledge, item.reveals, f"item {iid} reveals")
    s = story.start
    need(story.places, s.place, "start")
    need(chapters, s.chapter, "start")
    if s.place in story.places and story.places[s.place].chapter != s.chapter:
        errors.append("start: place is not in the start chapter")
    for iid in s.items:
        need(story.items, iid, "start item")
    for kid in s.knows:
        need(story.knowledge, kid, "start knowledge")
    for sid in s.skills:
        need(story.skills, sid, "start skill")
    if len(story.traits) != 6:
        errors.append("story needs exactly 6 traits")
    spread = sorted(story.creation.approaches.get(a, 0) for a in ("force", "finesse", "wits", "charm"))
    if spread != [0, 1, 1, 2]:
        errors.append("creation: approaches must spread +2, +1, +1, 0")
    if len(set(story.creation.traits)) != 2:
        errors.append("creation: needs two different traits")
    for tid in story.creation.traits:
        need({t.id for t in story.traits}, tid, "creation trait")
    for topic in story.topics:
        need(story.characters, topic.character, f"topic {topic.id}")
        need(story.knowledge, topic.knowledge, f"topic {topic.id}")
        if len(topic.free_when) < 2:
            errors.append(f"topic {topic.id}: needs 2 or more free_when paths")
        for alt in topic.free_when:
            _conditions(story, alt, f"topic {topic.id}", errors)
    for oid, o in story.obstacles.items():
        where = f"obstacle {oid}"
        need(story.places, o.place, where)
        if len(o.solutions) < 2:
            errors.append(f"{where}: needs 2 or more solutions")
        for cost in o.costs:
            if cost.kind == "item":
                need(story.items, cost.item, f"{where} cost")
        for iid in o.guards:
            need(story.items, iid, f"{where} guards")
        for sol in o.solutions:
            _conditions(story, sol.requires, where, errors)
        _effects(story, o.on_full, where, errors)
    for ch in story.chapters:
        where = f"chapter {ch.id}"
        if ch.next:
            need(chapters, ch.next, where)
        if ch.place:
            need(story.places, ch.place, where)
        _conditions(story, ch.goal, where, errors)
        _effects(story, ch.danger.on_full, f"{where} danger", errors)
    for qid, q in story.quests.items():
        need(chapters, q.chapter, f"quest {qid}")
        _conditions(story, q.done_when, f"quest {qid}", errors)
    for a in story.actions:
        need(story.places, a.place, f"action {a.id}")
        _conditions(story, [*a.show, *a.requires], f"action {a.id}", errors)
        _effects(story, [*a.hit, *a.miss], f"action {a.id}", errors)
    _effects(story, story.downed, "downed", errors)
    for e in story.endings:
        _conditions(story, e.when, f"ending {e.id}", errors)


def _conditions(story: Story, conds: list[Condition], where: str, errors: list[str]) -> None:
    tables = {
        "at": story.places, "knows": story.knowledge, "carries": story.items,
        "relation": story.characters, "progress": story.obstacles, "quest": story.quests,
        "chapter": {c.id for c in story.chapters}, "trace": TRACES,
    }
    for c in conds:
        if c.kind in tables and c.target not in tables[c.kind]:
            errors.append(f"{where}: {c.kind} condition has unknown target {c.target!r}")
        if c.kind == "flag" and not c.target:
            errors.append(f"{where}: flag condition needs a name")
        if c.kind == "progress" and c.value != "full" and not isinstance(c.value, int):
            errors.append(f"{where}: progress value must be a number or 'full'")


def _effects(story: Story, effects: list[Effect], where: str, errors: list[str]) -> None:
    tables = {
        "learn": story.knowledge, "give": story.items, "take": story.items,
        "companion": story.characters, "relation": story.characters, "reveal": story.obstacles,
        "progress": story.obstacles, "chapter": {c.id for c in story.chapters},
        "ending": {e.id for e in story.endings},
    }
    for e in effects:
        if e.kind in tables and e.target not in tables[e.kind]:
            errors.append(f"{where}: {e.kind} effect has unknown target {e.target!r}")
        if e.kind in ("flag", "flag_add") and not e.target:
            errors.append(f"{where}: flag effect needs a name")
        if e.kind == "move" and (e.target and e.target not in story.places):
            errors.append(f"{where}: move effect has unknown place {e.target!r}")
        exits = story.places[e.source].exits if e.source in story.places else []
        if e.kind in ("open", "close") and not any(ex.to == e.target for ex in exits):
            errors.append(f"{where}: {e.kind} effect needs an exit {e.source}->{e.target}")
        if e.kind == "tag" and (e.key not in TAG_KEYS or (e.target and e.target not in story.obstacles)):
            errors.append(f"{where}: tag effect needs key in {sorted(TAG_KEYS)} and an obstacle or empty target")


def _reachability(story: Story) -> list[str]:
    """Saturate everything that could happen if every check succeeds; negations are assumed avoidable."""
    s = story.start
    places = {s.place}
    exits = {(pid, ex.to) for pid, p in story.places.items() for ex in p.exits if ex.open}
    learned, items = set(s.knows), set(s.items) | {i for i, it in story.items.items() if it.holder == PLAYER}
    flags: dict[str, set] = {}
    filled: set[str] = set()
    revealed = {oid for oid, o in story.obstacles.items() if not o.hidden}
    chapters, quests, endings = {s.chapter}, set(), set()
    whereabouts = {cid: {c.place} if c.place else set() for cid, c in story.characters.items()}

    def holds(c: Condition) -> bool:
        if c.negate or c.kind in ("relation", "trace", "turn", "gold"):
            return True
        if c.kind == "at":
            return c.target in (places if c.source == PLAYER else whereabouts.get(c.source, set()))
        if c.kind == "knows":
            return c.target in learned if c.source == PLAYER else c.target in story.characters[c.source].knows
        if c.kind == "carries":
            return c.target in items
        if c.kind == "flag":
            seen = flags.get(c.target, set()) | {0}
            if c.op == "gte":
                return "many" in seen or any(isinstance(v, int) and v >= c.value for v in seen)
            return c.op == "lt" or c.value in seen
        if c.kind == "progress":
            return c.target in filled or (c.value != "full" and c.target in revealed)
        if c.kind == "quest":
            return c.target in quests
        return c.target in chapters

    def fire(effects: list[Effect]) -> None:
        for e in effects:
            if e.kind == "learn":
                learned.add(e.target)
            elif e.kind == "give" and e.source == PLAYER:
                items.add(e.target)
            elif e.kind == "open":
                exits.update({(e.source, e.target), (e.target, e.source)})
            elif e.kind == "move":
                (places if e.source == PLAYER else whereabouts.setdefault(e.source, set())).add(e.target)
            elif e.kind == "reveal":
                revealed.add(e.target)
            elif e.kind == "progress":
                filled.add(e.target)
            elif e.kind in ("flag", "flag_add"):
                flags.setdefault(e.target, set()).add("many" if e.kind == "flag_add" else e.value)
            elif e.kind == "chapter":
                chapters.add(e.target)
            elif e.kind == "ending":
                endings.add(e.target)

    before = None
    while before != (len(places), len(exits), len(learned), len(items), len(filled), len(chapters),
                     len(quests), len(endings), len(revealed), sum(map(len, flags.values()))):
        before = (len(places), len(exits), len(learned), len(items), len(filled), len(chapters),
                  len(quests), len(endings), len(revealed), sum(map(len, flags.values())))
        for ch in story.chapters:
            if ch.id in chapters:
                if ch.place:
                    places.add(ch.place)
                fire(ch.danger.on_full)
                if ch.next and all(map(holds, ch.goal)):
                    chapters.add(ch.next)
        places |= {b for a, b in exits if a in places}
        for oid, o in story.obstacles.items():
            if o.place in places and oid in revealed and any(all(map(holds, sol.requires)) for sol in o.solutions):
                filled.add(oid)
                fire(o.on_full)
        for iid, it in story.items.items():
            guard_ok = all(oid in filled for oid, o in story.obstacles.items() if iid in o.guards)
            if it.place in places and guard_ok:
                items.add(iid)
            if it.reveals and (iid in items or it.place in places):
                learned.add(it.reveals)
        for cid, c in story.characters.items():
            if whereabouts[cid] & places or c.companion:
                for iid, effects in c.gifts.items():
                    if iid in items:
                        fire(effects)
        for topic in story.topics:
            if whereabouts[topic.character] & places or story.characters[topic.character].companion:
                learned.add(topic.knowledge)
        for a in story.actions:
            if a.place in places and all(map(holds, [*a.show, *a.requires])):
                fire([*a.hit, *a.miss])
        fire(story.downed)
        quests |= {qid for qid, q in story.quests.items() if q.chapter in chapters and all(map(holds, q.done_when))}
        endings |= {e.id for e in story.endings if all(map(holds, e.when))}
    errors = [f"ending {e.id}: cannot be reached" for e in story.endings if e.id not in endings]
    errors += [f"chapter {c.id}: cannot be reached" for c in story.chapters if c.id not in chapters]
    return errors
