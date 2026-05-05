"""Verb-grammar primitives.

Lives in `game/domain/` so `game.domain.memory.PendingCheck` can carry `Verb` directly
without depending on `llm/calls/classify` (cycle through wire/labels →
game/domain/entities → game/domain/memory). `llm/calls/classify/schema.py` re-exports
these for call-site convenience.
"""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

VerbName = Literal[
    "move", "transfer", "use", "attack", "cast",
    "speak", "alter", "perceive", "rest", "wait",
]
RefuseCategory = Literal["out_of_game", "meta_breaking"]


class Verb(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: VerbName
    target_ids: list[str] = Field(default_factory=list, max_length=8)
    modifiers: dict[str, Any] = Field(default_factory=dict)


class RefuseReason(BaseModel):
    model_config = ConfigDict(extra="forbid")
    category: RefuseCategory
    message_hint: str = Field(min_length=1, max_length=120)


class JudgeOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    actions: list[Verb] | None = Field(default=None, max_length=4)
    refuse: RefuseReason | None = None

    @model_validator(mode="after")
    def _exactly_one(self) -> "JudgeOutput":
        actions_set = self.actions is not None
        refuse_set = self.refuse is not None
        if actions_set == refuse_set:
            raise ValueError(
                f"JudgeOutput must set exactly one of {{actions, refuse}}; "
                f"got actions={actions_set}, refuse={refuse_set}"
            )
        if actions_set and len(self.actions) == 0:
            raise ValueError(
                "actions, if set, must contain >=1 verb (use 'wait' for no-op)"
            )
        return self
