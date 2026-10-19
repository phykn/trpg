"""Atoms and the immutable State (ontology.md 1)."""

from __future__ import annotations

from collections.abc import Iterable, Iterator

Atom = tuple

PLAYER = "player"
APPROACHES = ("force", "finesse", "wits", "charm")
AXES = ("trust", "fear")
KINDS = ("edge", "snag")
LIVES = ("scene", "chapter", "scar")
SLOTS = (1, 2, 3)
SET_PREDS = ("link", "believes", "owes", "due", "spent")
PREDICATES = ("at", "mark", "regards", "fill", "stat", "flag") + SET_PREDS


class ConformError(ValueError):
    """An atom set that breaks C1 or C2."""


class State:
    """An immutable set of atoms, indexed by predicate (ontology.md 1.1)."""

    __slots__ = ("_atoms", "_hash", "at_", "fill_", "flag_", "mark_", "regards_", "sets_", "stat_")

    def __init__(self, at=None, mark=None, regards=None, fill=None, stat=None, flag=None, sets=None):
        self.at_: dict[str, str] = at or {}
        self.mark_: dict[tuple[str, int], tuple[str, str]] = mark or {}
        self.regards_: dict[tuple[str, str, str], int] = regards or {}
        self.fill_: dict[str, int] = fill or {}
        self.stat_: dict[tuple[str, str], int] = stat or {}
        self.flag_: dict[str, object] = flag or {}
        self.sets_: dict[str, frozenset] = sets or {p: frozenset() for p in SET_PREDS}
        self._atoms: frozenset | None = None
        self._hash: int | None = None

    @classmethod
    def of(cls, atoms: Iterable[Atom]) -> State:
        """Index atoms; a second value for a functional key breaks C1 or C2."""
        at, mark, regards, fill, stat, flag = {}, {}, {}, {}, {}, {}
        sets: dict[str, set] = {p: set() for p in SET_PREDS}

        def put(index: dict, key, value, atom):
            if key in index and index[key] != value:
                raise ConformError(f"two values for {atom[0]} {key}")
            index[key] = value

        for a in atoms:
            p = a[0]
            if p == "at":
                put(at, a[1], a[2], a)
            elif p == "mark":
                put(mark, (a[1], a[4]), (a[2], a[3]), a)
            elif p == "regards":
                put(regards, (a[1], a[2], a[3]), a[4], a)
            elif p == "fill":
                put(fill, a[1], a[2], a)
            elif p == "stat":
                put(stat, (a[1], a[2]), a[3], a)
            elif p == "flag":
                put(flag, a[1], a[2], a)
            elif p in sets:
                sets[p].add(tuple(a[1:]))
            else:
                raise ConformError(f"unknown predicate {p}")
        return cls(at, mark, regards, fill, stat, flag, {p: frozenset(v) for p, v in sets.items()})

    def atoms(self) -> frozenset:
        if self._atoms is None:
            out = [("at", x, y) for x, y in self.at_.items()]
            out += [("mark", x, k, life, i) for (x, i), (k, life) in self.mark_.items()]
            out += [("regards", g, h, ax, n) for (g, h, ax), n in self.regards_.items()]
            out += [("fill", o, n) for o, n in self.fill_.items()]
            out += [("stat", g, s, n) for (g, s), n in self.stat_.items()]
            out += [("flag", f, v) for f, v in self.flag_.items()]
            for p, rows in self.sets_.items():
                out += [(p, *r) for r in rows]
            self._atoms = frozenset(out)
        return self._atoms

    def __iter__(self) -> Iterator[Atom]:
        return iter(self.atoms())

    def __contains__(self, atom: Atom) -> bool:
        p = atom[0]
        if p == "at":
            return self.at_.get(atom[1]) == atom[2]
        if p == "mark":
            return self.mark_.get((atom[1], atom[4])) == (atom[2], atom[3])
        if p == "regards":
            return self.regards_.get((atom[1], atom[2], atom[3])) == atom[4]
        if p == "fill":
            return self.fill_.get(atom[1]) == atom[2]
        if p == "stat":
            return self.stat_.get((atom[1], atom[2])) == atom[3]
        if p == "flag":
            return self.flag_.get(atom[1]) == atom[2]
        return tuple(atom[1:]) in self.sets_.get(p, ())

    def __eq__(self, other) -> bool:
        return isinstance(other, State) and self.atoms() == other.atoms()

    def __hash__(self) -> int:
        if self._hash is None:
            self._hash = hash(self.atoms())
        return self._hash

    def __len__(self) -> int:
        return len(self.atoms())

    # Lookups used by rules and views.
    def where(self, x: str) -> str | None:
        return self.at_.get(x)

    def held_by(self, y: str) -> list[str]:
        return sorted(x for x, at in self.at_.items() if at == y)

    def fill(self, o: str) -> int | None:
        return self.fill_.get(o)

    def stat(self, g: str, s: str) -> int | None:
        return self.stat_.get((g, s))

    def flag(self, f: str):
        return self.flag_.get(f)

    def regards(self, g: str, h: str, axis: str) -> int | None:
        return self.regards_.get((g, h, axis))

    def marks(self, x: str) -> list[tuple[int, str, str]]:
        """(slot, kind, life) of x's tags, by slot."""
        return sorted((i, k, life) for (y, i), (k, life) in self.mark_.items() if y == x)

    def rows(self, pred: str) -> frozenset:
        return self.sets_[pred]

    def has(self, pred: str, *args) -> bool:
        return tuple(args) in self.sets_[pred]

    def filter(self, keep) -> State:
        return State.of(a for a in self.atoms() if keep(a))


def apply(s: State, add: Iterable[Atom], remove: Iterable[Atom]) -> State:
    """S ⊕ Δ = (S ∖ Δ⁻) ∪ Δ⁺."""
    return State.of((s.atoms() - frozenset(remove)) | frozenset(add))
