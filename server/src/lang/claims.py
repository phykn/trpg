"""Claim extraction κ (engine.md 5.3): the literals of Σ a narrated sentence states.

The present frames of 𝔗 (at, link) become patterns over names and aliases, so κ reads back every fact
line ρ writes; possession verbs add the literals narration most often gets wrong (taking what is not
held, handing over what is). Sentences that state nothing in Σ (smell, weather, faces) yield nothing.
"""

from __future__ import annotations

import re

from ..locale import ko
from ..onto.atoms import PLAYER, Atom, State

JOSA = {"을": "(?:을|를)", "이": "(?:이|가)", "은": "(?:은|는)", "와": "(?:과|와)", "으로": "(?:으로|로)"}
YOU = "당신"


def words(u, x: str) -> tuple[str, ...]:
    return (YOU,) if x == PLAYER else (u.name(x), *u.aliases(x))


_CACHE: dict[tuple[str, str], object] = {}


def _cached(kind: str):
    def wrap(f):
        def get(u):
            key = (kind, u.digest)
            if key not in _CACHE:
                _CACHE[key] = f(u)
            return _CACHE[key]
        return get
    return wrap


@_cached("names")
def _names(u) -> dict[str, str]:
    """Every name and alias → its entity, longest first so '등대 열쇠' wins over '열쇠'."""
    ids = [PLAYER, *u.places, *u.agents, *u.things, *u.obstacles]
    pairs = {w: x for x in ids for w in words(u, x) if w}
    return dict(sorted(pairs.items(), key=lambda kv: -len(kv[0])))


def _slot(u, key: str) -> str:
    return f"(?P<{key}>{'|'.join(re.escape(w) for w in _names(u))})"


@_cached("frames")
def _frames(u) -> list[tuple[str, re.Pattern]]:
    out = []
    for frame in ("at_place", "at_agent", "link"):
        parts, i, text = [], 0, ko.FRAME[frame]
        for m in re.finditer(r"\{([^}]+)\}", text):
            parts.append(re.escape(text[i:m.start()]))
            key = m[1]
            parts.append(JOSA[key] if key in JOSA else _slot(u, key))
            i = m.end()
        parts.append(re.escape(text[i:]))
        out.append((frame, re.compile("".join(parts))))
    return out


def mentioned(u, sentence: str) -> list[tuple[int, str]]:
    """(position, entity) for each name or alias standing in the sentence, longest names first."""
    out, taken = [], []
    for w, x in _names(u).items():
        for m in re.finditer(re.escape(w), sentence):
            if not any(a <= m.start() < b for a, b in taken):
                out.append((m.start(), x))
                taken.append((m.start(), m.end()))
    return sorted(out)


def claims(u, sentence: str) -> list[tuple[bool, Atom]]:
    """κ(sentence): (positive, atom) literals."""
    names = _names(u)
    out: list[tuple[bool, Atom]] = []
    for frame, pattern in _frames(u):
        for m in pattern.finditer(sentence):
            g = {k: names[v] for k, v in m.groupdict().items()}
            if frame == "at_place" and u.kind(g["y"]) == "place" or frame == "at_agent":
                out.append((True, ("at", g["x"], g["y"])))
            elif frame == "link":
                out.append((True, ("link", g["p"], g["q"])))
    here = mentioned(u, sentence)
    if any(v in sentence for v in ko.OPENS):
        out += [(True, ("fill", x, u.boxes(x))) for _, x in here
                if x in u.obstacles and u.obstacles[x].sub == "plain"]
    things = [x for _, x in here if x in u.things]
    if things:
        holder = _subject(u, sentence) or PLAYER
        if any(v in sentence for v in ko.GETS):
            out += [(True, ("at", x, holder)) for x in things]
        if holder == PLAYER and any(v in sentence for v in ko.GIVES):
            out += [(False, ("at", x, PLAYER)) for x in things]
    return list(dict.fromkeys(out))


def _subject(u, sentence: str) -> str | None:
    """The first person standing as a subject ('도해가', '당신은'), if any."""
    for w, x in _names(u).items():
        if (x == PLAYER or x in u.agents) and re.search(re.escape(w) + "(?:이|가|은|는)(?![가-힣])", sentence):
            return x
    return None


def accepts(facts: State, positive: bool, atom: Atom) -> bool:
    """φ only when φ ∈ F'; ¬φ only when F' and C entail it (an at elsewhere, by C1)."""
    if positive:
        if atom[0] == "at":
            return facts.where(atom[1]) == atom[2]
        if atom[0] == "fill":
            return facts.fill(atom[1]) == atom[2]
        return facts.has(*atom)
    if atom[0] == "at":
        where = facts.where(atom[1])
        return where is not None and where != atom[2]
    return False


__all__ = ["accepts", "claims", "mentioned"]
