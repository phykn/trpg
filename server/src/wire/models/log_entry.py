from typing import Annotated

from pydantic import Field, RootModel

from ...game.domain.memory import (
    ActLogEntry,
    BonusItem,
    GMLogEntry,
    PlayerLogEntry,
    RollLogEntry,
)

__all__ = [
    "ActLogEntry",
    "BonusItem",
    "GMLogEntry",
    "LogEntryPayload",
    "PlayerLogEntry",
    "RollLogEntry",
]


class LogEntryPayload(RootModel):
    """SSE `log_entry` event payload — discriminated union over `kind`.
    Wraps domain.memory's 4 sub-classes (GMLogEntry / PlayerLogEntry /
    ActLogEntry / RollLogEntry) + BonusItem (RollLogEntry sub-shape).
    Same RootModel pattern as JudgePayload (sub-round 2.6) — codegen
    emits a clean union alias on the client side."""

    root: Annotated[
        GMLogEntry | PlayerLogEntry | ActLogEntry | RollLogEntry,
        Field(discriminator="kind"),
    ]
