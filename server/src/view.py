from __future__ import annotations

from .locale import ko
from .onto.atoms import APPROACHES, PLAYER, State
from .onto.view import Obs, Seen, observe
from .rules.acts import Action, parse
from .rules.candidates import (
    active_threats,
    blockers,
    candidates,
    held_clock,
    solution_label,
    topic_of,
)
from .rules.recommend import recommend
from .rules.roll import DC, band, risk, rolls

# The order clocks show in, most pressing first.
CLOCK_ORDER = ("clock", "deadline", "threat", "fork")


def tag_name(p: dict, atom) -> str:
    key = list(atom)
    for a, _, name in reversed(p.get("tags", [])):
        if a == key:
            return name
    return ko.TAG_DEFAULT[atom[2]]


def default_tag_name(name: str | None, kind: str) -> str:
    if name is None:
        return ko.TAG_DEFAULT[kind]
    return ko.TAG_KEYS.get(name, name)


def name(u, x: str) -> str:
    return ko.YOU if x == PLAYER else u.name(x)


def prop_label(u, pid: str) -> str:
    for a in u.agents.values():
        for t in a.topics:
            if t.prop == pid and t.id == pid:
                return t.title
    if pid in u.latents:
        return u.latents[pid].name
    p = u.props[pid]
    if p.title:
        return p.title
    return ko.fill(ko.CLUE, name=u.name(p.about[0])) if p.about else p.text.rstrip(".")


def holders(u, pid: str) -> list[str]:
    """Whose words a proposition is: a topic's holder, or the person a desire belongs to."""
    if u.props[pid].source == "desire":
        return [pid[:-len(".desire")]]
    return [a.id for a in u.agents.values() if any(t.prop == pid for t in a.topics)]


def rely_label(u, p: dict, facts: State, rely: str) -> str:
    kind, _, rest = rely.partition(":")
    if kind == "tag":
        x, _, slot = rest.rpartition(":")
        life = facts.mark_.get((x, int(slot)), ("edge", "scene"))[1]
        return tag_name(p, ("mark", x, "edge", life, int(slot)))
    if kind == "trait":
        return u.traits[rest][0]
    if kind == "thing":
        return u.name(rest)
    if kind == "prop":
        return prop_label(u, rest)
    return ko.fill(ko.HELPER if kind == "with" else ko.BOND, h=u.name(rest))


def atom_label(u, p: dict, atom) -> str:
    k = atom[0]
    if k == "mark":
        return tag_name(p, atom)
    if k == "stat":
        return ko.APPROACHES.get(atom[2]) or u.traits[atom[2]][0]
    if k == "at":
        return u.name(atom[1])
    if k == "believes":
        return prop_label(u, atom[2])
    # A help chip carries the roll card option's name, so the card can show its value beside it.
    if k == "regards" and atom[3] == "trust" and atom[4] == 3:
        return ko.fill(ko.BOND, h=u.name(atom[1]))
    if k == "regards":
        word = ko.TRUST_WORDS.get(atom[4], "") if atom[3] == "trust" else ko.UNAFRAID if atom[4] < 0 else ko.FEAR_WORD
        return f"{u.name(atom[1])} {word}"
    if k == "follows":
        return ko.fill(ko.HELPER, h=u.name(atom[1]))
    return str(atom)


def chips(u, p: dict, mods) -> list[dict]:
    out = []
    for kind, atoms, value in mods:
        label = "·".join(atom_label(u, p, a) for a in atoms)
        out.append({"kind": kind, "label": label, "value": value})
    return out


def chips_of_atoms(u, p: dict, mods: tuple, guarded: bool = False) -> list[dict]:
    if not mods:
        return []
    stat, rest = mods[0], mods[1:]
    groups = [("stat", (stat,), stat[3])]
    hinders = [m for m in rest if (m[0] == "mark" and m[2] == "snag") or (m[0] == "regards" and m[4] < 0)]
    helps = [m for m in rest if m not in hinders]
    if helps:
        groups.append(("guard", tuple(helps), 0) if guarded else ("help", tuple(helps), 1))
    if hinders:
        groups.append(("hinder", tuple(hinders), -1))
    return chips(u, p, groups)


def action_label(u, o: Obs, p: dict, a: Action) -> str:
    s, i = a.schema, a.intent
    if s == "go":
        return ko.fill(ko.ACTION["go"], q=u.name(i[0]))
    if s == "look":
        return ko.fill(ko.ACTION["look"], x=u.name(i[0]))
    if s == "take":
        return ko.fill(ko.ACTION["take"], x=u.name(i[0]))
    if s in ("give", "show"):
        return ko.fill(ko.ACTION[s], h=u.name(i[1]), x=u.name(i[0]))
    if s == "talk":
        h, topic = i
        claim = a.get("claim")
        if claim:
            text = ko.fill(ko.ACTION["claim"], h=u.name(h), claim=u.props[claim].text)
        elif topic == "chat":
            text = ko.fill(ko.ACTION["chat"], h=u.name(h))
        elif topic == "favor":
            text = ko.fill(ko.ACTION["favor"], h=u.name(h), label=u.agents[h].favor.label)
        elif topic in ("come", "stay"):
            text = ko.fill(ko.ACTION[topic], h=u.name(h))
        else:
            t = topic_of(u, h, topic)
            text = ko.fill(ko.ACTION["talk"], h=u.name(h), title=t.title)
        tone = a.get("tone")
        text = text if tone == "polite" or claim else f"{ko.TONES[tone]} {text}"
        return _relying(u, o, p, a) + text
    if s == "try":
        x, ap = i
        if x == PLAYER:
            return ko.ACTION["try_self"]
        sol = solution_label(u, o, a)
        if sol:
            return sol
        forced = a.get("strain") == "forced"
        # A forced way of the story's solution keeps its label: "무리해서 어깨로 문을 들이받는다".
        sol = forced and solution_label(u, o, a.with_(strain=None))
        if sol:
            return f"{ko.STRAINS['forced']} {sol}"
        text = ko.fill(ko.ACTION["try_agent" if u.kind(x) == "agent" else "try"], x=u.name(x), approach=ko.APPROACHES[ap])
        text = f"{ko.STRAINS['forced']} {text}" if forced else text
        return _relying(u, o, p, a) + text
    if s == "declare":
        return ko.fill(ko.ACTION["declare"], name=u.latents[i[0]].name)
    if s == "cut":
        return ko.ACTION[i[0]]
    if s == "choose":
        return next(n for c, n, _ in u.obstacles[i[0]].choices if c == i[1])
    if s == "grow":
        kind, name = growth_name(u, o, p, a)
        return name if kind == "approach" else ko.fill(ko.ACTION[f"grow_{kind}"], name=name)
    return str(a)


def growth_name(u, o, p, a) -> tuple[str, str]:
    """A growth's kind and the short name the growth card lists it by, under that kind."""
    i = a.intent
    if i[0] == "trait":
        return "trait", ko.fill(ko.SWAP, old=u.traits[i[1]][0], new=u.traits[i[2]][0])
    if i[0] == "scar":
        return "scar", tag_name(p, ("mark", PLAYER, "snag", "scar", int(i[1])))
    v = o.facts.stat(PLAYER, i[0]) or 0
    return "approach", ko.fill(ko.ACTION["grow"], approach=ko.APPROACHES[i[0]], before=v, after=v + 1)


def _relying(u, o: Obs, p: dict, a: Action) -> str:
    rely = a.get("rely")
    return ko.fill(ko.RELYING, rely=rely_label(u, p, o.facts, rely)) if rely else ""


def effect_names(u, effects) -> list[str]:
    out = []
    for e in effects:
        k = e[0]
        if k == "move":
            if e[1] == PLAYER:
                out.append(ko.fill(ko.EFFECT["move_player"], y=u.name(e[2])))
            elif e[2] == PLAYER:
                out.append(ko.fill(ko.EFFECT["gain"], x=u.name(e[1])))
            else:
                key = "move_agent" if u.kind(e[2]) == "agent" else "move"
                out.append(ko.fill(ko.EFFECT[key], x=u.name(e[1]), y=u.name(e[2])))
        elif k == "set" and e[1] == "fill":
            out.append(ko.fill(ko.EFFECT["fill"], o=u.name(e[2][0]), v=e[3]))
        elif k == "set" and e[1] == "regards":
            out.append(ko.fill(ko.EFFECT["regards"], g=u.name(e[2][0])))
        elif k == "tag":
            out.append(ko.fill(ko.EFFECT["tag"], name=default_tag_name(e[4], e[2])))
        elif k == "retire":
            out.append(ko.fill(ko.EFFECT["retire"], o=u.name(e[1])))
        elif k in ko.EFFECT:
            out.append(ko.EFFECT[k] if "{" not in ko.EFFECT[k] else ko.EFFECT["flag"])
        elif k == "set":
            out.append(ko.EFFECT["flag"])
    return out


def step_record(u, p: dict, seen: Seen, label: str, ending: str | None) -> dict:
    a = parse(seen.action)
    mods = chips_of_atoms(u, p, seen.mods, ("guard",) in seen.happen)
    roll = {"d1": seen.roll[0], "d2": seen.roll[1]} if seen.roll else None
    total = decisive = None
    level = risk(u, a)
    dc = DC[level]
    if roll:
        total = roll["d1"] + roll["d2"] + sum(c["value"] for c in mods)
        decisive = [i for i, c in enumerate(mods) if c["value"] and band(total - c["value"], dc) != seen.result]
    return {"t": seen.t, "action": seen.action, "label": label, "result": seen.result,
            "risk": level, "dc": dc if roll else None, "roll": roll, "mods": mods if roll else [], "total": total,
            "decisive": decisive or [], "changes": changes(u, p, seen, a, ending)}


def changes(u, p: dict, seen: Seen, a: Action, ending: str | None) -> list[dict]:
    add, rem = seen.delta.add, seen.delta.remove
    out: list[dict] = []
    if seen.result == "blocked":
        # The blocker comes to light by name; the beat the step spent still runs on, and a scene end it brought
        # went untold (qa_test/runs/narr-3 turn 6: the sunset went to 1/3).
        found = {at for at in add if at[0] == "believes" and at[2].endswith(".hidden")}
        for at in sorted(found, key=str):
            x = at[2][:-len(".hidden")]
            out.append({"kind": "reveal", "id": x, "name": u.name(x)})
        add = add - found

    def value(atoms, pred, *key):
        for at in atoms:
            if at[0] == pred and at[1:1 + len(key)] == key:
                return at[-1]
        return None

    # A scene end moves every threat at once; without its line three clocks moved with no cause the player could read.
    # It comes after the step's own progress and before the clocks it moved.
    fills = sorted({at[1] for at in add | rem if at[0] == "fill"}, key=lambda o: (u.obstacles[o].sub != "plain", u.rank(o)))
    scene = ("scene_end",) in seen.happen
    for o in fills:
        if scene and u.obstacles[o].sub != "plain":
            out.append({"kind": "scene_end"})
            scene = False
        before, after = value(rem, "fill", o), value(add, "fill", o)
        if before is None or after is None:
            continue
        ob = u.obstacles[o]
        if ob.sub == "plain":
            fit = int(a.schema == "try" and a.intent[0] == o and a.intent[1] in ob.fits and after - before >= 2)
            out.append({"kind": "fill", "id": o, "name": ob.name, "from": before, "to": after, "fit": fit})
        elif ob.sub == "clock" and after < before:
            out.append({"kind": "crisis", "id": o, "name": ob.name, "from": before, "to": after})
        else:
            out.append({"kind": "clock", "id": o, "name": ob.name, "from": before, "to": after})
    if scene:
        out.append({"kind": "scene_end"})
    for at in sorted(rem, key=str):
        if at[0] == "at" and at[2] == PLAYER and u.obstacles.get(at[1]) and u.obstacles[at[1]].sub in ("threat", "fork", "deadline"):
            o = at[1]
            if ("fill", o, u.boxes(o)) in add and a.schema != "choose":
                out.append({"kind": "arrival", "id": o, "name": u.name(o)})
    for at in sorted(add, key=str):
        if at[0] == "at" and at[2] == PLAYER and u.obstacles.get(at[1]) and u.obstacles[at[1]].sub == "fork":
            out.append({"kind": "fork", "id": at[1], "name": u.name(at[1]),
                        "choices": [n for _, n, _ in u.obstacles[at[1]].choices]})
    replaced = {(h[1], h[2]) for h in seen.happen if h[0] == "tag_replaced"}
    for at in sorted(add, key=str):
        if at[0] == "mark":
            kind = "scar" if at[3] == "scar" else "tag_add"
            c = {"kind": kind, "owner": at[1], "slot": at[4], "tag": at[2], "life": at[3], "name": tag_name(p, at)}
            old = next((b for b in rem if b[0] == "mark" and (b[1], b[4]) == (at[1], at[4])), None)
            if (at[1], at[4]) in replaced and old:
                c["replaced"] = tag_name(p, old)
            out.append(c)
    for at in sorted(rem, key=str):
        if at[0] == "mark" and not any(b[0] == "mark" and b[1] == at[1] and b[4] == at[4] for b in add):
            out.append({"kind": "tag_remove", "owner": at[1], "slot": at[4], "tag": at[2], "life": at[3],
                        "name": tag_name(p, at)})
    w0, w1 = value(rem, "stat", PLAYER, "wounds"), value(add, "stat", PLAYER, "wounds")
    if ("fall",) in seen.happen:
        out.append({"kind": "fall"})        # the wounds reset with it, which read as a heal
    elif w0 is not None and w1 is not None:
        out.append({"kind": "wound", "from": w0, "to": w1})
    went = value(add, "at", PLAYER)
    for at in sorted(add, key=str):
        if at[0] == "at" and u.kind(at[1]) in ("agent", "thing"):
            before = value(rem, "at", at[1])
            out.append({"kind": "move", "id": at[1], "name": name(u, at[1]), "to": at[2], "to_name": name(u, at[2]),
                        "from": before, "with": at[1] != PLAYER and u.kind(at[1]) == "agent" and at[2] == went})
        elif at[0] == "believes" and at[1] == PLAYER:
            pid = at[2]
            x = pid[:-len(".hidden")] if pid.endswith(".hidden") else None
            out.append({"kind": "reveal", "id": x or pid, "name": u.name(x) if x else prop_label(u, pid),
                        "text": u.props[pid].text})
        elif at[0] == "link":
            out.append({"kind": "link", "from": at[1], "to": at[2], "name": u.name(at[2]), "open": True})
    for at in sorted(rem, key=str):
        if at[0] == "link":
            out.append({"kind": "link", "from": at[1], "to": at[2], "name": u.name(at[2]), "open": False})
    for at in sorted(add, key=str):
        if at[0] == "regards" and at[2] == PLAYER:
            before = value(rem, "regards", at[1], PLAYER, at[3])
            if before is not None:
                out.append({"kind": "regards", "id": at[1], "name": u.name(at[1]), "axis": at[3],
                            "from": before, "to": at[4]})
    for at in sorted(add | rem, key=str):
        if at[0] == "follows" and at[2] == PLAYER:
            out.append({"kind": "follow", "id": at[1], "name": u.name(at[1]), "state": "start" if at in add else "stop"})
    for at in sorted(add | rem, key=str):
        if at[0] == "owes":
            g, h, k = at[1:]
            other = h if g == PLAYER else g
            state = "made" if at in add else _closing(p, seen) if k == "promise" else "closed"
            out.append({"kind": "promise", "id": other, "name": u.name(other), "owes": k, "debtor": g,
                        "state": state, "promise": _promise(u, other, k)})
    for at in add:
        if at[0] == "at" and at[1].startswith("clock.") and at[2] == PLAYER:
            k = int(at[1].split(".")[1])
            if k > 1:
                out.append({"kind": "chapter", "from": k - 1, "to": k, "name": u.chapter_of(k).title})
    if ending:
        out.append({"kind": "ending", "id": ending, "name": u.endings[ending].title})
    return out


def _promise(u, other: str, kind: str) -> str:
    favor = u.agents[other].favor
    return favor.promise if kind == "promise" and favor else ""


def _attitude(f: State, h: str) -> str:
    return ko.attitude(f.regards(h, PLAYER, "trust") or 0, f.regards(h, PLAYER, "fear") or 0)


def _closing(p: dict, seen: Seen) -> str:
    # Trust is clamped, so a kept promise at full trust may change nothing; a break always tags the player.
    broken = ko.TAG_KEYS["@broken_promise"]
    if any(at[0] == "mark" and at[1] == PLAYER and tag_name(p, at) == broken for at in seen.delta.add):
        return "broken"
    return "kept"


def chapter_k(u, facts: State) -> int:
    c = held_clock(u, facts)
    return int(c.split(".")[1]) if c else len(u.chapters)


def game_view(u, g) -> dict:
    p = g.presentation
    o = observe(u, g.state, g.log)
    f = o.facts
    here = f.where(PLAYER)
    k = chapter_k(u, f)
    ending = p.get("ending")
    last = p["turns"][-1] if p.get("turns") else None
    return {
        "revision": p.get("revision", 0),
        "story": {"id": u.id, "title": u.title, "premise": u.premise},
        "chapter": {"k": k, "title": u.chapter_of(k).title, "aim": u.chapter_of(k).aim},
        "scene": _scene(u, o, p, here),
        "player": {"name": g.creation.get("name", ""), **_player(u, o, p)},
        "clocks": [{"id": c, "name": u.name(c), "fill": f.fill(c), "boxes": u.boxes(c), "kind": u.obstacles[c].sub}
                   for c in sorted(filter(None, [held_clock(u, f), *active_threats(u, f)]),
                                   key=lambda c: CLOCK_ORDER.index(u.obstacles[c].sub))],
        "journal": _journal(u, o, p),
        "buttons": [] if ending else [
            {"action": str(a), "label": action_label(u, o, p, a), "rolls": rolls(u, f, o.hist, a)}
            for a in recommend(u, o)],
        "growth": [] if ending or (f.stat(PLAYER, "growth") or 0) < 1 else [
            {"action": str(a), "label": action_label(u, o, p, a), **dict(zip(("kind", "name"), growth_name(u, o, p, a))),
             "text": u.traits[a.intent[2]][1] if a.intent[0] == "trait" else ko.SCAR_GROWTH if a.intent[0] == "scar" else ""}
            for a in candidates(u, o) if a.schema == "grow"],
        "card": (p.get("card") or {}).get("public"),
        "last": None if last is None else {
            "turn": last["n"], "steps": last["steps"], "narrated": str(last["n"]) in p.get("narration", {})},
        "recaps": sorted(int(x) for x in p.get("recap", {})),
        "ending": {"id": ending, "title": u.endings[ending].title} if ending else None,
    }


def _scene(u, o: Obs, p: dict, here: str) -> dict:
    f = o.facts
    seen = sorted(o.seen, key=u.rank)
    people = [h for h in seen if h in u.agents and f.where(h) == here]
    return {
        "place": {"id": here, "name": u.name(here), "senses": list(u.places[here].senses)},
        "people": [{"id": h, "name": u.name(h),
                    "attitude": _attitude(f, h),
                    "with": f.has("follows", h, PLAYER)}
                   for h in people],
        "things": [{"id": x, "name": u.name(x)} for x in seen if x in u.things and f.where(x) == here],
        "obstacles": [{"id": x, "name": u.name(x), "fill": f.fill(x), "boxes": u.boxes(x),
                       "blocks": [u.name(b) for b in u.obstacles[x].blocks]}
                      for x in seen if x in u.obstacles and u.obstacles[x].sub == "plain" and f.where(x) == here],
        "exits": [{"id": q, "name": u.name(q),
                   "blocked": any(b in o.seen for b in blockers(u, f, q))}
                  for q in seen if u.kind(q) == "place" and f.has("link", here, q)],
        "tags": [{"owner": x, "slot": i, "kind": kind, "life": life, "name": tag_name(p, ("mark", x, kind, life, i))}
                 for x in seen if x != PLAYER for i, kind, life in f.marks(x)],
    }


def _player(u, o: Obs, p: dict) -> dict:
    f = o.facts
    return {
        "approaches": [{"id": ap, "name": ko.APPROACHES[ap], "value": f.stat(PLAYER, ap) or 0} for ap in APPROACHES],
        "traits": [{"id": t, "name": u.traits[t][0], "spent": f.has("spent", PLAYER, t)}
                   for t in u.traits if f.stat(PLAYER, t) == 1],
        "tags": [{"slot": i, "kind": kind, "life": life, "name": tag_name(p, ("mark", PLAYER, kind, life, i))}
                 for i, kind, life in f.marks(PLAYER)],
        "things": [{"id": x, "name": u.name(x), "spent": f.has("spent", PLAYER, x)}
                   for x in sorted(o.seen, key=u.rank) if x in u.things and f.where(x) == PLAYER],
        "wounds": f.stat(PLAYER, "wounds") or 0, "wound_boxes": u.wound_boxes,
        "beats": f.stat(PLAYER, "beats") or 0, "beats_max": u.beats,
        "growth": f.stat(PLAYER, "growth") or 0,
    }


def _journal(u, o: Obs, p: dict) -> dict:
    f = o.facts
    near = set(o.seen)
    beliefs = []
    for n, pid in enumerate(o.beliefs):
        prop = u.props[pid]
        beliefs.append({"id": pid, "text": prop.text, "order": n, "spent": f.has("spent", PLAYER, pid),
                        "here": bool(near & set(prop.about)) or bool(near & set(holders(u, pid)))})
    owes = []
    for gg, h, k in sorted(f.rows("owes")):
        other = h if gg == PLAYER else gg
        owes.append({"debtor": gg, "creditor": h, "kind": k, "name": u.name(other), "promise": _promise(u, other, k)})
    relations = [{"id": h, "name": u.name(h), "trust": f.regards(h, PLAYER, "trust"),
                  "fear": f.regards(h, PLAYER, "fear"),
                  "attitude": _attitude(f, h)}
                 for h in u.agents if h in near or any(s.action.startswith(f"talk:{h}:") for s in o.memory)]
    return {"beliefs": beliefs, "owes": owes, "relations": relations, "choices": p.get("choices", [])}
