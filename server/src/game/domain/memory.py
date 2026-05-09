from typing import Annotated, Literal

from pydantic import BaseModel, Field

from .types import StatKey, Tier
from .verb import Verb


class Memory(BaseModel):
    content: str
    importance: int = Field(ge=1, le=3)
    turn: int
    target_id: str | None = None


class TurnLogEntry(BaseModel):
    turn: int
    target: str | None = None
    summary: str


class DialoguePair(BaseModel):
    turn: int
    player: str
    narrator: str


class PendingCheck(BaseModel):
    player_input: str
    kind: Literal["stat", "recruit", "steal"] = "stat"
    tier: Tier
    stat: StatKey
    target: str
    targets: list[str]
    dc: int
    mod: int
    required_roll: int = Field(ge=1, le=20)
    reason: str
    created_at: str
    triggering_verb: Verb | None = None
    pending_verbs: list[Verb] = Field(default_factory=list)


class GMLogEntry(BaseModel):
    id: int
    kind: Literal["gm"]
    text: str


class PlayerLogEntry(BaseModel):
    id: int
    kind: Literal["player"]
    text: str


class ActLogEntry(BaseModel):
    id: int
    kind: Literal["act"]
    text: str


class BonusItem(BaseModel):
    label: str
    value: int


class RollLogEntry(BaseModel):
    id: int
    kind: Literal["roll"]
    check: str
    roll: int
    margin: int
    result: Literal["success", "partial", "fail"]
    # Player-facing breakdown of (die + bonuses) → total. Stat is folded
    # into required_roll on the engine side; we surface the equivalent
    # +mod here so the result label tells the same story.
    bonus_breakdown: list[BonusItem] = []


LogEntry = Annotated[
    GMLogEntry | PlayerLogEntry | ActLogEntry | RollLogEntry,
    Field(discriminator="kind"),
]
