"""Authored adventures: graph facts, choices, and a versioned turn snapshot."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .combat_types import CombatState
from .graph import Graph


class IncompatibleSave(ValueError):
    pass


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Condition(Model):
    kind: Literal["at", "knows", "carries", "property", "relation"]
    target: str
    source: str = "player"
    key: str = ""
    value: str | int | bool = True
    op: Literal["eq", "gte", "lt"] = "eq"
    negate: bool = False


class Effect(Model):
    kind: Literal["set", "add", "learn", "give", "move", "companion", "relation"]
    target: str
    source: str = "player"
    key: str = ""
    value: str | int | bool = True


class Result(Model):
    text: str
    effects: list[Effect] = Field(default_factory=list)


class Check(Model):
    stat: Literal["body", "agility", "mind", "presence"]
    dc: int = Field(ge=2, le=20)


class Choice(Model):
    id: str
    target: str
    label: str
    description: str
    show: list[Condition] = Field(default_factory=list)
    requires: list[Condition] = Field(default_factory=list)
    blocked: str = ""
    ticks: int = Field(default=1, ge=0, le=3)
    gold: int = Field(default=0, ge=0)
    mp: int = Field(default=0, ge=0)
    system: bool = False
    once: bool = True
    confirm: bool = False
    check: Check | None = None
    success: Result
    failure: Result | None = None
    enemy: str | None = None

    @model_validator(mode="after")
    def check_result(self):
        if self.check is not None and self.failure is None:
            raise ValueError("a check requires a failure result")
        return self


class Description(Model):
    name: str
    text: str = ""


class Role(Description):
    stat: Literal["body", "agility", "mind", "presence"]
    skill: str
    item: str | None = None


class Milestone(Model):
    id: str
    tick: int = Field(ge=1)
    result: Result


class Reaction(Model):
    target: str
    when: list[Condition]
    text: str


class Story(Model):
    id: str
    version: int = Field(ge=1)
    title: str
    synopsis: str
    intro: str
    deadline: int = Field(ge=1)
    graph: Graph
    descriptions: dict[str, Description]
    roles: dict[str, Role]
    choices: list[Choice]
    milestones: list[Milestone] = Field(default_factory=list)
    reactions: list[Reaction] = Field(default_factory=list)
    endings: dict[str, Description]


class JournalEntry(Model):
    turn: int
    kind: Literal["story", "action", "roll", "world"]
    text: str = ""
    key: str = ""
    values: dict[str, str | int] = Field(default_factory=dict)


class Receipt(Model):
    action: str
    revision: int


class GameState(Model):
    schema_version: Literal[1] = 1
    content_version: int
    game_id: str
    profile: str = "harbor"
    role: str
    graph: Graph
    revision: int = 0
    rng_seed: int
    rng_step: int = 0
    combat: CombatState | None = None
    journal: list[JournalEntry] = Field(default_factory=list)
    receipts: dict[str, Receipt] = Field(default_factory=dict)


def chapter(state: GameState) -> dict:
    return state.graph.nodes["chapter"].properties
