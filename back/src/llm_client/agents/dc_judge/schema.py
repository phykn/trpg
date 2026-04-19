from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter

Tier = Literal["easy", "normal", "hard"]
Stat = Literal["STR", "DEX", "CON", "INT", "WIS", "CHA"]


class JudgeInput(BaseModel):
    player_input: str
    surroundings: dict[str, Any]


class _StrictAction(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SkipAction(_StrictAction):
    action: Literal["skip"]


class CombatAction(_StrictAction):
    action: Literal["combat"]
    targets: list[str] = Field(min_length=1)


class ClarifyAction(_StrictAction):
    action: Literal["clarify"]
    question: str = Field(min_length=1)


class RollAction(_StrictAction):
    action: Literal["roll"]
    tier: Tier
    stat: Stat
    targets: list[str] = Field(min_length=1)


JudgeOutput = Annotated[
    SkipAction | CombatAction | ClarifyAction | RollAction,
    Field(discriminator="action"),
]

output_adapter: TypeAdapter[JudgeOutput] = TypeAdapter(JudgeOutput)
