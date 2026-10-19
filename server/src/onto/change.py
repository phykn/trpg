from __future__ import annotations

from .atoms import PLAYER, SET_PREDS, State


class Work:
    """Every operation keeps C (ontology.md 1.4)."""

    def __init__(self, u, s: State):
        self.u = u
        self.at = dict(s.at_)
        self.mark = dict(s.mark_)
        self.regards = dict(s.regards_)
        self.fill = dict(s.fill_)
        self.stat = dict(s.stat_)
        self.flag = dict(s.flag_)
        self.sets = {p: set(v) for p, v in s.sets_.items()}
        self.names: list[tuple[str, int, str | None]] = []   # tags placed this step: (x, slot, default name)
        self._frozen: State | None = None

    def state(self) -> State:
        if self._frozen is None:
            self._frozen = State(dict(self.at), dict(self.mark), dict(self.regards), dict(self.fill),
                                 dict(self.stat), dict(self.flag), {p: frozenset(v) for p, v in self.sets.items()})
        return self._frozen

    def _touch(self):
        self._frozen = None

    def move(self, x: str, y: str) -> None:
        if x == PLAYER and self.u.kind(y) != "place":
            raise ValueError(f"the player can only move to a place, not {y}")
        self._touch()
        self.at[x] = y

    def set_(self, pred: str, key: tuple, v) -> None:
        index = {"regards": self.regards, "fill": self.fill, "stat": self.stat, "flag": self.flag}[pred]
        k = key if pred in ("regards", "stat") else key[0]
        if isinstance(v, str) and v[:1] in "+-" and v[1:].isdigit():
            cur = index.get(k, 0)
            v = cur + int(v)
        lim = self.u.limit(pred, key)
        if pred == "flag":
            if lim is None or v not in lim:
                raise ValueError(f"flag {key[0]} cannot take {v!r}")
        elif lim is not None:
            v = max(lim[0], min(lim[1], v))
        if index.get(k) == v:
            return
        self._touch()
        index[k] = v

    def drop_stat(self, g: str, s: str) -> None:
        """Only growth's trait swap removes a sheet entry (rule.md 6)."""
        if (g, s) in self.stat:
            self._touch()
            del self.stat[(g, s)]

    def reveal(self, g: str, p: str) -> None:
        self.insert(("believes", g, p))

    def tag(self, x: str, kind: str, life: str, name: str | None = None) -> int | None:
        """Lowest empty slot; when full, replace the lowest non-scar slot; all scars: nothing."""
        used = {i: self.mark[(y, i)] for (y, i) in self.mark if y == x}
        free = [i for i in (1, 2, 3) if i not in used]
        if free:
            slot = free[0]
        else:
            open_ = [i for i in (1, 2, 3) if used[i][1] != "scar"]
            if not open_:
                return None
            slot = open_[0]
        self._touch()
        self.mark[(x, slot)] = (kind, life)
        self.names.append((x, slot, name))
        return slot

    def untag(self, x: str, slot: int) -> None:
        if (x, slot) in self.mark:
            self._touch()
            del self.mark[(x, slot)]

    def link(self, p: str, q: str) -> None:
        self.insert(("link", p, q))

    def unlink(self, p: str, q: str) -> None:
        self.retract(("link", p, q))

    def retire(self, o: str) -> None:
        if o in self.at:
            self._touch()
            del self.at[o]
        if self.u.obstacles[o].sub in ("threat", "fork"):
            self.set_("flag", (f"fired_appear.{o}",), 1)

    def expire(self, life: str) -> None:
        gone = [k for k, (_, lf) in self.mark.items() if lf == life]
        if gone:
            self._touch()
            for k in gone:
                del self.mark[k]

    def insert(self, atom: tuple) -> None:
        if atom[0] not in SET_PREDS:
            raise ValueError(f"insert takes a set predicate, not {atom[0]}")
        row = tuple(atom[1:])
        if row not in self.sets[atom[0]]:
            self._touch()
            self.sets[atom[0]].add(row)

    def retract(self, atom: tuple) -> None:
        row = tuple(atom[1:])
        if row in self.sets[atom[0]]:
            self._touch()
            self.sets[atom[0]].discard(row)

    def clear_spent(self, g: str) -> None:
        gone = {r for r in self.sets["spent"] if r[0] == g}
        if gone:
            self._touch()
            self.sets["spent"] -= gone

    def apply_effect(self, e: tuple) -> None:
        """One compiled story effect (story.md 2.4); engine macros are applied by the rules."""
        k = e[0]
        if k == "move":
            self.move(e[1], e[2])
        elif k == "set":
            self.set_(e[1], e[2], e[3])
        elif k == "reveal":
            self.reveal(e[1], e[2])
        elif k == "tag":
            self.tag(e[1], e[2], e[3], e[4])
        elif k == "link":
            self.link(e[1], e[2])
        elif k == "unlink":
            self.unlink(e[1], e[2])
        elif k == "retire":
            self.retire(e[1])
        else:
            raise ValueError(f"not a story effect: {k}")
