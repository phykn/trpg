"""Snapshots and rebuilding from the log (ontology.md 6). The log is the source; state is a cache."""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from .atoms import State, apply
from .log import Event, Log
from .universe import Universe, conforms, initial
from .view import record

SCHEMA_VERSION = 2


class SaveError(RuntimeError):
    """A save that cannot be loaded: missing, another schema or story digest, or broken."""


@dataclass
class Game:
    id: str
    story: str
    seed: int
    creation: dict
    state: State
    log: Log = field(default_factory=Log)
    presentation: dict = field(default_factory=dict)


def new_game(u: Universe, game_id: str, seed: int, creation: dict) -> Game:
    return Game(game_id, u.id, seed, creation, initial(u, creation))


def to_json(u: Universe, g: Game) -> dict:
    return {"schema_version": SCHEMA_VERSION,
            "story": {"id": u.id, "version": u.version, "digest": u.digest},
            "seed": g.seed, "creation": g.creation, "game_id": g.id,
            "log": [e.to_json() for e in g.log.events], "presentation": g.presentation}


def write(path: Path, data: dict) -> None:
    """Write to a temporary file, fsync, then rename: one atomic change per request."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=path.name, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def save(u: Universe, g: Game, path: Path) -> None:
    write(path, to_json(u, g))


def rebuild(u: Universe, data: dict) -> Game:
    """S₀ = initial(U, creation), then apply each event's delta, checking C after every step."""
    if data.get("schema_version") != SCHEMA_VERSION:
        raise SaveError("incompatible schema_version")
    if data.get("story", {}).get("digest") != u.digest:
        raise SaveError("incompatible story")
    s = initial(u, data["creation"])
    g = Game(data["game_id"], u.id, data["seed"], data["creation"], s, presentation=data.get("presentation", {}))
    for raw in data["log"]:
        e = Event.from_json(raw)
        after = apply(s, e.delta.add, e.delta.remove)
        problems = conforms(u, after)
        if problems:
            raise SaveError(f"event {e.t} breaks C: {problems[0]}")
        record(u, g.log, s, after, e)
        s = after
    g.state = s
    return g


def load(u: Universe, path: Path) -> Game:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise SaveError(str(e)) from None
    return rebuild(u, data)
