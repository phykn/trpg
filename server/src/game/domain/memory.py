from typing import Annotated, Literal

from pydantic import BaseModel, Field, model_serializer


class Memory(BaseModel):
    content: str
    importance: int = Field(ge=1, le=3)
    turn: int
    target_id: str | None = None


class TurnLogEntry(BaseModel):
    turn: int
    target: str | None = None
    summary: str
    importance: int = Field(default=1, ge=1, le=3)


class DialoguePair(BaseModel):
    turn: int
    player: str
    narrator: str
    target_id: str | None = None


class GMLogEntry(BaseModel):
    id: int
    kind: Literal["gm"]
    text: str
    outcome: Literal["success", "failure", "neutral"] | None = None

    @model_serializer(mode="wrap")
    def _serialize(self, handler):
        data = handler(self)
        if data.get("outcome") is None:
            data.pop("outcome", None)
        return data


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
    result: Literal["success", "fail"]
    # Player-facing breakdown of (die + bonuses) → total. Stat is folded
    # into required_roll on the engine side; we surface the equivalent
    # +mod here so the result label tells the same story.
    bonus_breakdown: list[BonusItem] = []


LogEntry = Annotated[
    GMLogEntry | PlayerLogEntry | ActLogEntry | RollLogEntry,
    Field(discriminator="kind"),
]
