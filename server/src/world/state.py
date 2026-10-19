"""Saved game state, interpreted steps, and per-turn records."""

from typing import Annotated, Literal

from pydantic import Field

from src.content.schema import (
    Approach,
    Attitude,
    Grade,
    Model,
    Plausibility,
    Purpose,
    Risk,
    TagKind,
    TagLife,
    Trace,
)

from .graph import Graph


class IncompatibleSave(ValueError):
    pass


class Tag(Model):
    id: str
    kind: TagKind
    target: str | None = None
    life: TagLife = "scene"
    trace: Trace | None = None
    name: str = ""
    turn: int


class Memory(Model):
    turn: int
    kind: Literal["claim", "threat", "help", "exposed", "promise"]
    text: str


ChangeKind = Literal[
    "progress", "danger", "tag_add", "tag_use", "tag_drop", "relation", "learn", "gain",
    "lose", "gold", "wound", "move", "open", "close", "quest", "complication", "downed",
    "claim", "exposed", "chapter", "ending", "flag", "reveal", "companion", "inspect", "grow",
]


class Change(Model):
    kind: ChangeKind
    target: str = ""
    before: int | str | None = None
    after: int | str | None = None


class Uses(Model):
    tag: str | None = None
    thing: str | None = None
    trait: str | None = None


class ActionStep(Model):
    kind: Literal["action"] = "action"
    action_id: str
    uses: Uses = Field(default_factory=Uses)  # a trait the words call on helps an authored action's check


class ImproviseStep(Model):
    kind: Literal["improvise"] = "improvise"
    purpose: Purpose = "overcome"
    target: str | None = None
    approach: Approach
    risk: Risk = "normal"
    plausibility: Plausibility = "natural"
    check: bool = True
    uses: Uses = Field(default_factory=Uses)
    label: str = ""  # an authored solution's own words, shown instead of the generic "approach vs obstacle"


class TalkStep(Model):
    kind: Literal["talk"] = "talk"
    character: str
    topic: str = "chat"
    attitude: Attitude = "polite"
    claim: bool = False
    touch: Literal["desire", "fear", "none"] = "none"
    contradicts: str | None = None
    uses: Uses = Field(default_factory=Uses)


Step = Annotated[ActionStep | ImproviseStep | TalkStep, Field(discriminator="kind")]


class Roll(Model):
    dice: tuple[int, int]
    modifier: int
    total: int
    grade: Grade


class StepResult(Model):
    kind: Literal["move", "inspect", "take", "give", "act", "improvise", "talk", "flavor"]
    label: str
    target: str = ""
    roll: Roll | None = None
    effect: int = 0
    changes: list[Change] = Field(default_factory=list)


class TurnRecord(Model):
    n: int
    input: str = ""
    steps: list[StepResult] = Field(default_factory=list)
    changes: list[Change] = Field(default_factory=list)
    notable: list[str] = Field(default_factory=list)
    hint: str | None = None
    recap: bool = False
    narration: str | None = None
    tag_names: dict[str, str] = Field(default_factory=dict)


class Pending(Model):
    id: str
    kind: Literal["confirm", "growth"]
    steps: list[Step] = Field(default_factory=list)
    input: str = ""


class Receipt(Model):
    fingerprint: str
    kind: str
    turn: int | None = None


class Progress(Model):
    value: int = 0
    known: bool = False
    revealed: bool = True
    fired: bool = False


class Sheet(Model):
    approaches: dict[Approach, int]
    traits: list[str]
    skills: list[str] = Field(default_factory=list)
    wounds: int = 0
    gold: int = 0
    trait_used: list[str] = Field(default_factory=list)


class GameState(Model):
    schema_version: Literal[1] = 1
    game_id: str
    story_id: str
    story_version: int
    revision: int = 0
    seed: int
    turn: int = 0
    graph: Graph
    player: Sheet
    chapter: str
    danger: int = 0
    complicated: bool = False
    obstacles: dict[str, Progress] = Field(default_factory=dict)
    tags: dict[str, list[Tag]] = Field(default_factory=dict)
    traces: list[Tag] = Field(default_factory=list)
    flags: dict[str, int | bool | str] = Field(default_factory=dict)
    quests_done: list[str] = Field(default_factory=list)
    actions_done: list[str] = Field(default_factory=list)
    stall: int = 0
    ending: str | None = None
    pending: Pending | None = None
    turns: list[TurnRecord] = Field(default_factory=list)
    receipts: dict[str, Receipt] = Field(default_factory=dict)
