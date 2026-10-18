"""Authored story format and the fixed engine vocabulary it is written against."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Approach = Literal["force", "finesse", "wits", "charm"]
Attitude = Literal["polite", "empathy", "persuade", "threaten", "deceive"]
Risk = Literal["low", "normal", "high"]
Plausibility = Literal["natural", "stretch", "impossible"]
Purpose = Literal["overcome", "setup", "clear"]
Grade = Literal["hit", "mixed", "miss"]
TagKind = Literal["edge", "snag"]
TagLife = Literal["scene", "chapter"]
Trace = Literal["wanted", "suspicion", "reputation"]

APPROACHES: tuple[Approach, ...] = ("force", "finesse", "wits", "charm")
ATTITUDES: tuple[Attitude, ...] = ("polite", "empathy", "persuade", "threaten", "deceive")
RISKS: tuple[Risk, ...] = ("low", "normal", "high")
PLAYER = "player"


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Condition(Model):
    kind: Literal[
        "at", "knows", "carries", "relation", "flag", "progress", "trace", "quest", "turn", "chapter", "gold"
    ]
    target: str = ""
    source: str = PLAYER
    value: str | int | bool = True
    op: Literal["eq", "gte", "lt"] | None = None
    negate: bool = False


class Effect(Model):
    kind: Literal[
        "flag", "flag_add", "learn", "give", "take", "move", "companion", "relation",
        "open", "close", "tag", "reveal", "progress", "danger", "chapter", "ending", "gold",
    ]
    target: str = ""
    source: str = PLAYER
    key: str = ""
    value: str | int | bool = True


class Labels(Model):
    approaches: dict[Approach, str] = Field(default_factory=dict)
    wound: str = ""
    gold: str = ""


class Creation(Model):
    choose: bool = False
    approaches: dict[Approach, int]
    traits: list[str]


class Trait(Model):
    id: str
    name: str
    text: str


class Exit(Model):
    to: str
    open: bool = True


class Place(Model):
    name: str
    text: str
    chapter: str
    senses: list[str]
    exits: list[Exit] = Field(default_factory=list)


class Character(Model):
    name: str
    role: str
    place: str = ""
    desire: str
    fear: str
    contradiction: str
    voice: str
    boundary: str
    knows: list[str] = Field(default_factory=list)
    relation: int = Field(default=0, ge=-3, le=3)
    companion: bool = False
    gifts: dict[str, list[Effect]] = Field(default_factory=dict)


class Item(Model):
    name: str
    text: str
    place: str = ""
    holder: str = ""
    reveals: str = ""


class Knowledge(Model):
    title: str
    summary: str


class Skill(Model):
    name: str
    text: str
    approach: Approach


class Topic(Model):
    id: str
    character: str
    knowledge: str
    title: str
    free_when: list[list[Condition]]
    mods: dict[Attitude, int] = Field(default_factory=dict)


class Cost(Model):
    kind: Literal["snag", "gold", "item", "wound"]
    value: int = Field(default=1, ge=1)
    item: str = ""


class Solution(Model):
    label: str
    approach: Approach
    risk: Risk = "normal"
    requires: list[Condition] = Field(default_factory=list)


class Obstacle(Model):
    name: str
    place: str
    boxes: int = Field(ge=2, le=6)
    fits: list[Approach] = Field(min_length=1)
    clashes: list[Approach] = Field(default_factory=list)
    costs: list[Cost] = Field(min_length=1)
    on_full: list[Effect] = Field(min_length=1)
    solutions: list[Solution]
    foe: bool = False
    hidden: bool = False
    guards: list[str] = Field(default_factory=list)


class Danger(Model):
    name: str
    boxes: int = Field(ge=6, le=8)
    tick_every: int | None = Field(default=None, ge=1)
    on_full: list[Effect] = Field(min_length=1)


class Chapter(Model):
    id: str
    title: str
    place: str = ""
    danger: Danger
    goal: list[Condition] = Field(min_length=1)
    next: str = ""


class Quest(Model):
    title: str
    text: str
    chapter: str
    done_when: list[Condition] = Field(min_length=1)


class SceneAction(Model):
    id: str
    label: str
    place: str
    show: list[Condition] = Field(default_factory=list)
    requires: list[Condition] = Field(default_factory=list)
    check: Solution | None = None
    hit: list[Effect] = Field(min_length=1)
    miss: list[Effect] = Field(default_factory=list)
    once: bool = True


class Ending(Model):
    id: str
    title: str
    when: list[Condition] = Field(min_length=1)
    text: str


class Start(Model):
    place: str
    chapter: str
    items: list[str] = Field(default_factory=list)
    knows: list[str] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    gold: int = Field(default=0, ge=0)


class Story(Model):
    id: str
    version: int = Field(ge=1)
    title: str
    synopsis: str
    intro: str
    labels: Labels = Field(default_factory=Labels)
    creation: Creation
    traits: list[Trait]
    start: Start
    places: dict[str, Place]
    characters: dict[str, Character]
    items: dict[str, Item] = Field(default_factory=dict)
    knowledge: dict[str, Knowledge] = Field(default_factory=dict)
    skills: dict[str, Skill] = Field(default_factory=dict)
    topics: list[Topic] = Field(default_factory=list)
    obstacles: dict[str, Obstacle]
    chapters: list[Chapter] = Field(min_length=1)
    quests: dict[str, Quest] = Field(default_factory=dict)
    actions: list[SceneAction] = Field(default_factory=list)
    downed: list[Effect] = Field(min_length=1)
    endings: list[Ending] = Field(min_length=1)

    def chapter(self, chapter_id: str) -> Chapter:
        return next(c for c in self.chapters if c.id == chapter_id)

    def topic(self, topic_id: str) -> Topic:
        return next(t for t in self.topics if t.id == topic_id)

    def action(self, action_id: str) -> SceneAction:
        return next(a for a in self.actions if a.id == action_id)

    def trait(self, trait_id: str) -> Trait:
        return next(t for t in self.traits if t.id == trait_id)

    def name(self, node_id: str) -> str:
        """Display name of any authored id, or the id itself for unknown ones."""
        for table in (self.places, self.characters, self.items, self.skills, self.obstacles):
            if node_id in table:
                return table[node_id].name
        if node_id in self.knowledge:
            return self.knowledge[node_id].title
        return node_id
