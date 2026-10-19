from __future__ import annotations

from dataclasses import dataclass

# Schema → number of intent arguments (None: grow, whose shape depends on the item).
SCHEMAS: dict[str, int | None] = {
    "go": 1, "look": 1, "take": 1, "give": 2, "talk": 2, "try": 2,
    "declare": 1, "cut": 1, "choose": 2, "pay": 1, "grow": None,
}
JUDGE = {"talk": ("claim", "rely", "tone"), "try": ("rely", "strain")}
# ν₀ per judgment key; None means the argument is absent.
NEUTRAL = {"tone": "polite", "strain": "natural", "claim": None, "rely": None}
TONES = ("polite", "friendly", "plead", "threaten", "deceive")
STRAINS = ("natural", "forced")


@dataclass(frozen=True)
class Action:
    schema: str
    intent: tuple[str, ...]
    judge: tuple[tuple[str, str], ...] = ()   # non-neutral judgment arguments, sorted by key

    def get(self, key: str):
        for k, v in self.judge:
            if k == key:
                return v
        return NEUTRAL[key]

    def with_(self, **judge) -> Action:
        """None or ν₀ removes a judgment argument."""
        d = dict(self.judge)
        d.update(judge)
        return make(self.schema, self.intent, d)

    @property
    def target(self) -> str | None:
        return self.intent[0] if self.intent else None

    def __str__(self) -> str:
        return format(self)


def make(schema: str, intent, judge: dict | None = None) -> Action:
    """Canonical form: neutral judgment values dropped, keys sorted (story.md 3.12)."""
    if schema not in SCHEMAS:
        raise ValueError(f"unknown schema {schema}")
    intent = tuple(str(x) for x in intent)
    n = SCHEMAS[schema]
    if n is not None and len(intent) != n:
        raise ValueError(f"{schema} takes {n} intent arguments")
    if n is None and not _grow_shape(intent):
        raise ValueError(f"bad grow item {':'.join(intent)}")
    if any(not x or ";" in x or "=" in x for x in intent):
        raise ValueError("bad intent argument")
    pairs = []
    for k, v in (judge or {}).items():
        if k not in JUDGE.get(schema, ()):
            raise ValueError(f"{schema} takes no {k}")
        if v is None or v == NEUTRAL[k]:
            continue
        if not isinstance(v, str) or not v or ";" in v:
            raise ValueError(f"bad value for {k}")
        pairs.append((k, v))
    return Action(schema, intent, tuple(sorted(pairs)))


def _grow_shape(intent) -> bool:
    if len(intent) == 1:
        return True
    if intent[0] == "trait":
        return len(intent) == 3
    if intent[0] == "scar":
        return len(intent) == 2 and intent[1] in ("1", "2", "3")
    return False


def parse(s: str) -> Action:
    if not isinstance(s, str) or not s:
        raise ValueError("empty action id")
    head, *judge = s.split(";")
    schema, *intent = head.split(":")
    pairs = {}
    for j in judge:
        k, eq, v = j.partition("=")
        if not eq or k in pairs:
            raise ValueError(f"bad judgment argument {j}")
        pairs[k] = v
    a = make(schema, intent, pairs)
    if any(dict(a.judge).get(k) != v for k, v in pairs.items() if v != NEUTRAL.get(k)):
        raise ValueError(f"bad action id {s}")
    return a


def format(a: Action) -> str:
    return ":".join((a.schema, *a.intent)) + "".join(f";{k}={v}" for k, v in a.judge)

