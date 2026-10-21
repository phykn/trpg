from __future__ import annotations

from dataclasses import dataclass

from ..locale import ko
from ..onto.atoms import PLAYER, Atom
from ..onto.view import Obs
from ..view import name, prop_label, tag_name

MEMORY = 3


@dataclass(frozen=True)
class Line:
    section: str              # fact, belief, memory, public
    text: str
    atom: Atom | None = None


def fact_line(u, p: dict, atom: Atom) -> str | None:
    """None for atoms the context leaves out."""
    k = atom[0]
    if k == "at":
        x, y = atom[1], atom[2]
        if u.kind(y) == "place":
            return ko.fill(ko.FRAME["at_place"], x=name(u, x), y=u.name(y))
        if x in u.obstacles:
            return None                      # a carried clock or threat speaks through its fill
        return ko.fill(ko.FRAME["at_agent"], y=name(u, y), x=u.name(x))
    if k == "link":
        return ko.fill(ko.FRAME["link"], p=u.name(atom[1]), q=u.name(atom[2]))
    if k == "mark":
        frame = "mark_agent" if atom[1] == PLAYER or atom[1] in u.agents else "mark"
        return ko.fill(ko.FRAME[frame], x=name(u, atom[1]), name=tag_name(u, p, atom))
    if k == "fill":
        return ko.fill(ko.FRAME["fill"], o=u.name(atom[1]), n=atom[2], boxes=u.boxes(atom[1]))
    if k == "regards" and atom[2] == PLAYER:
        g, axis, n = atom[1], atom[3], atom[4]
        if axis == "trust":
            return ko.fill(ko.FRAME["trust"], g=u.name(g), word=ko.TRUST_VERBS[n])
        return ko.fill(ko.FRAME["fear"], g=u.name(g), word=ko.FEAR_VERBS[n]) if n else None
    if k == "stat" and atom[1] == PLAYER:
        s = atom[2]
        if s in u.traits:
            return ko.fill(ko.FRAME["trait"], name=u.traits[s][0])
        if s in ko.APPROACHES:
            return ko.fill(ko.FRAME["stat"], item=ko.APPROACHES[s], n=atom[3])
        if s == "wounds":
            return ko.fill(ko.FRAME["stat"], item=ko.SHEET[s], n=atom[3])
        return None
    if k == "owes":
        g, h, kind = atom[1:]
        if kind == "promise" and g == PLAYER and u.agents[h].favor:
            return ko.fill(ko.FRAME["promise"], h=u.name(h), name=u.agents[h].favor.promise)
        if kind == "kindness" and h == PLAYER:
            return ko.fill(ko.FRAME["kindness"], g=u.name(g))
    if k == "follows":
        return ko.fill(ko.FRAME["follows"], h=u.name(atom[1]))
    return None


def context(u, o: Obs, focus, p: dict) -> list[Line]:
    """X = focus ∩ E. A fact touches X and names only E: the player is in every focus, and F holds the player's ties
    to people anywhere, so the decision model read an absent companion's regard and a latent person's (qa_test/runs/
    decision-2/parity-context.txt)."""
    x = set(focus) & set(o.seen)
    out: list[Line] = []
    for atom in sorted(o.facts.atoms(), key=lambda a: (a[0], str(a[1:]))):
        if atom[0] in ("due", "spent", "believes"):
            continue
        slots = [a for a in atom[1:] if isinstance(a, str) and u.kind(a) is not None or a == PLAYER]
        if not any(a in x for a in slots) or not set(slots) <= o.seen:
            continue
        text = fact_line(u, p, atom)
        if text:
            out.append(Line("fact", text, atom))
    for pid in o.beliefs:
        prop = u.props[pid]
        holders = {a.id for a in u.agents.values() if any(t.prop == pid for t in a.topics)}
        if x & set(prop.about) or x & holders or (not prop.about and not holders):
            out.append(Line("belief", ko.fill(ko.FRAME["belief"], text=prop.text)))
    for seen in o.memory[-MEMORY:]:
        names = set(seen.action.replace(";", ":").split(":")) | {a[1] for a in seen.delta.add | seen.delta.remove}
        if names & x:
            out.append(Line("memory", ko.fill(ko.FRAME["memory"], label=_past(u, seen))))
    for e in sorted(x, key=u.rank):
        out += about(u, o, e)
    return out


def _past(u, seen) -> str:
    result = ko.RESULTS.get(seen.result, "")
    head = seen.action.split(";")[0].split(":")
    words = [w for w in (_word(u, a) for a in head[1:]) if w]
    text = ko.SCHEMA_DESC.get(head[0], head[0]) + (f"({', '.join(words)})" if words else "")
    return f"{text}: {result}" if result else text


def _word(u, a: str) -> str | None:
    """An action argument in words; ids with no words (such as a bare chat) are left out."""
    if a in u.props:
        return prop_label(u, a)
    if a == PLAYER or u.kind(a):
        return name(u, a)
    return ko.APPROACHES.get(a)


def scene(u, o: Obs, focus, p: dict) -> list[Line]:
    """The narrator's ρ (engine.md 2): only the people in the scene, the ways out of it, and words for numbers."""
    x = set(focus) & set(o.seen)
    out: list[Line] = []
    for ln in context(u, o, focus, p):
        a = ln.atom
        if a is not None:
            if any(isinstance(s, str) and s in u.agents and s not in x for s in a[1:]):
                continue
            if a[0] == "link" and a[1] not in x:
                continue
            # A neutral regard says nothing, and its wording reads as a temperament that fights the persona.
            if a[0] == "regards" and a[4] == 0:
                continue
            if a[0] == "fill" and a[1] in u.obstacles and u.obstacles[a[1]].sub not in ("clock", "deadline"):
                if a[2] == 0:
                    continue
                n, boxes = a[2], u.boxes(a[1])
                word = ko.OVERCOME[2 if n >= boxes else 1 if n >= boxes - 1 else 0]
                ln = Line("fact", ko.fill(ko.FRAME["pace"], o=u.name(a[1]), word=word), a)
            if a[0] == "stat":
                if a[2] == "wounds" and a[3] > 0:
                    ln = Line("fact", ko.FRAME["wounded"], a)
                elif a[2] not in u.traits:
                    continue
        out.append(ln)
    for c in o.facts.held_by(PLAYER):
        if c in u.obstacles and u.obstacles[c].sub in ("clock", "deadline") and c in o.seen:
            n, boxes = o.facts.fill(c) or 0, u.boxes(c)
            word = ko.PACE[0 if n == 0 else 2 if n >= boxes - 1 else 1]
            out.append(Line("fact", ko.fill(ko.FRAME["pace"], o=u.name(c), word=word), ("fill", c, n)))
    return out


def about(u, o: Obs, x: str) -> list[Line]:
    out = []
    if x in u.places:
        out.append(Line("public", ko.fill(ko.FRAME["senses"], x=u.name(x), text=", ".join(u.places[x].senses))))
    elif x in u.agents:
        a = u.agents[x]
        out.append(Line("public", ko.fill(ko.FRAME["persona"], x=a.name, type=a.persona, text=ko.PERSONAS[a.persona])))
        out += [Line("public", ko.fill(ko.FRAME[k], x=a.name, text=v))
                for k, v in (("voice", a.voice), ("desire", a.desire), ("fear_of", a.fear))]
        if a.topics:
            out.append(Line("public", ko.fill(ko.FRAME["topics"], x=a.name, text=", ".join(t.title for t in a.topics))))
        wants = [u.name(w) for w in a.wants if not _hidden_from_player(u, o, w)]
        if wants:
            out.append(Line("public", ko.fill(ko.FRAME["wants"], x=a.name, text=", ".join(wants))))
    elif x in u.things:
        out.append(Line("public", ko.fill(ko.FRAME["look"], x=u.name(x), text=u.things[x].look)))
    elif x in u.obstacles and u.obstacles[x].look:
        out.append(Line("public", ko.fill(ko.FRAME["look"], x=u.name(x), text=u.obstacles[x].look)))
    return out


def _hidden_from_player(u, o: Obs, x: str) -> bool:
    props = u.shows.get(x)
    return bool(props) and not any(p in o.beliefs for p in props)


def render(lines: list[Line]) -> str:
    out = []
    for section, head in ko.SECTIONS.items():
        part = [ln.text for ln in lines if ln.section == section]
        if part:
            out.append(head)
            out += [f"- {t}" for t in part]
    return "\n".join(out)


__all__ = ["Line", "about", "context", "fact_line", "prop_label", "render", "scene"]
