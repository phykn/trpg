from __future__ import annotations

import operator
from typing import Protocol

from .atoms import AXES, KINDS, State

Cond = tuple
TRUE: Cond = ("all", ())
OPS = {"=": operator.eq, ">=": operator.ge, "<=": operator.le, ">": operator.gt, "<": operator.lt}


class Context(Protocol):
    def fail(self, msg: str) -> None: ...
    def ref(self, x, kinds: tuple[str, ...], where: str) -> str: ...
    def boxes(self, o: str) -> int: ...
    def flag_value(self, name: str, v, where: str): ...
    def pattern(self, prefix: str, result: str | None, where: str) -> int: ...


def compile_cond(raw, ctx: Context, where: str) -> Cond:
    if not isinstance(raw, dict) or len(raw) != 1:
        ctx.fail(f"{where}: a condition is a map with one key")
    (key, args), = raw.items()
    if key in ("all", "any"):
        if not isinstance(args, list):
            ctx.fail(f"{where}: {key} takes a list")
        return (key, tuple(compile_cond(a, ctx, f"{where}.{key}") for a in args))
    if key == "not":
        return ("not", compile_cond(args, ctx, f"{where}.not"))
    if not isinstance(args, list):
        ctx.fail(f"{where}: {key} takes a list")
    n = {"at": 2, "link": 2, "believes": 2, "fill": 3, "regards": 5, "mark": 2, "owes": 3, "flag": 2}
    if key == "did":
        if len(args) not in (1, 2) or not isinstance(args[0], str):
            ctx.fail(f"{where}: did takes [action prefix] or [action prefix, result]")
        result = args[1] if len(args) == 2 else None
        if result is not None and result not in ("success", "mixed", "fail", "none", "blocked"):
            ctx.fail(f"{where}: unknown result {result}")
        return ("did", ctx.pattern(args[0], result, where))
    if key not in n:
        ctx.fail(f"{where}: unknown condition {key}")
    if len(args) != n[key]:
        ctx.fail(f"{where}: {key} takes {n[key]} arguments")
    agent, place, ent = ("agent",), ("place",), ("agent", "thing", "obstacle", "place")
    if key == "at":
        return ("at", ctx.ref(args[0], ("agent", "thing", "obstacle"), where),
                ctx.ref(args[1], ("place", "agent"), where))
    if key == "link":
        return ("link", ctx.ref(args[0], place, where), ctx.ref(args[1], place, where))
    if key == "believes":
        return ("believes", ctx.ref(args[0], agent, where), ctx.ref(args[1], ("prop",), where))
    if key == "fill":
        o = ctx.ref(args[0], ("obstacle",), where)
        v = ctx.boxes(o) if args[2] == "full" else _int(ctx, args[2], where)
        return ("fill", o, _op(ctx, args[1], where), v)
    if key == "regards":
        if args[2] not in AXES:
            ctx.fail(f"{where}: unknown axis {args[2]}")
        return ("regards", ctx.ref(args[0], agent, where), ctx.ref(args[1], agent, where), args[2],
                _op(ctx, args[3], where), _int(ctx, args[4], where))
    if key == "mark":
        if args[1] not in KINDS:
            ctx.fail(f"{where}: unknown tag kind {args[1]}")
        return ("mark", ctx.ref(args[0], ent, where), args[1])
    if key == "owes":
        if args[2] not in ("promise", "kindness"):
            ctx.fail(f"{where}: owes takes promise or kindness")
        return ("owes", ctx.ref(args[0], agent, where), ctx.ref(args[1], agent, where), args[2])
    return ("flag", args[0], ctx.flag_value(args[0], args[1], where))


def _op(ctx, op, where):
    if op not in OPS:
        ctx.fail(f"{where}: unknown comparison {op}")
    return op


def _int(ctx, v, where):
    if not isinstance(v, int) or isinstance(v, bool):
        ctx.fail(f"{where}: expected an integer, got {v!r}")
    return v


def holds(c: Cond, facts: State, hist: frozenset) -> bool:
    """World (S, h) and visible (F, hᵥ) evaluation share this evaluator, so they differ only by the atoms passed."""
    k = c[0]
    if k == "all":
        return all(holds(x, facts, hist) for x in c[1])
    if k == "any":
        return any(holds(x, facts, hist) for x in c[1])
    if k == "not":
        return not holds(c[1], facts, hist)
    if k == "at":
        return facts.where(c[1]) == c[2]
    if k in ("link", "believes"):
        return facts.has(k, c[1], c[2])
    if k == "owes":
        return facts.has("owes", c[1], c[2], c[3])
    if k == "fill":
        v = facts.fill(c[1])
        return v is not None and OPS[c[2]](v, c[3])
    if k == "regards":
        v = facts.regards(c[1], c[2], c[3])
        return v is not None and OPS[c[4]](v, c[5])
    if k == "mark":
        return any(kind == c[2] for _, kind, _ in facts.marks(c[1]))
    if k == "flag":
        return facts.flag(c[1]) == c[2]
    if k == "did":
        return c[1] in hist
    raise ValueError(f"unknown condition {k}")


def atoms_of(c: Cond) -> list[Cond]:
    """The leaf conditions of c; V3 uses them to check which atoms a visible condition reads."""
    if c[0] in ("all", "any"):
        return [leaf for x in c[1] for leaf in atoms_of(x)]
    if c[0] == "not":
        return atoms_of(c[1])
    return [c]


def conj(*cs: Cond) -> Cond:
    parts = tuple(c for c in cs if c is not None and c != TRUE)
    return parts[0] if len(parts) == 1 else ("all", parts)
