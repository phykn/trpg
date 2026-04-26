from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter

from ....domain.types import StatKey, Tier


class JudgeInput(BaseModel):
    player_input: str
    surroundings: dict[str, Any]


class _StrictAction(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PassAction(_StrictAction):
    action: Literal["pass"]


class RejectAction(_StrictAction):
    action: Literal["reject"]


class CombatAction(_StrictAction):
    action: Literal["combat"]
    targets: list[str] = Field(min_length=1)


class ClarifyAction(_StrictAction):
    action: Literal["clarify"]
    question: str = Field(min_length=1)


class RollAction(_StrictAction):
    action: Literal["roll"]
    tier: Tier
    stat: StatKey
    targets: list[str] = Field(min_length=1)
    reason: str = Field(min_length=1, max_length=80)


JudgeOutput = Annotated[
    PassAction | RejectAction | CombatAction | ClarifyAction | RollAction,
    Field(discriminator="action"),
]

output_adapter: TypeAdapter[JudgeOutput] = TypeAdapter(JudgeOutput)
