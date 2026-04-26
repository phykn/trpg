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
    skill_id: str | None = None  # racial + learned 의미 매칭 (§2.6 S2)


class FleeAction(_StrictAction):
    action: Literal["flee"]


class LevelUpAction(_StrictAction):
    action: Literal["level_up"]
    stat_up: StatKey
    stat_down: StatKey


class LearnSkillAction(_StrictAction):
    action: Literal["learn_skill"]
    index: int = Field(ge=0)


class BuyAction(_StrictAction):
    action: Literal["buy"]
    npc_id: str
    item_id: str


class SellAction(_StrictAction):
    action: Literal["sell"]
    npc_id: str
    item_id: str


class ClarifyAction(_StrictAction):
    action: Literal["clarify"]
    question: str = Field(min_length=1)


class RollAction(_StrictAction):
    action: Literal["roll"]
    tier: Tier
    stat: StatKey
    targets: list[str] = Field(min_length=1)
    reason: str = Field(min_length=1, max_length=80)


class RestAction(_StrictAction):
    action: Literal["rest"]


class UseAction(_StrictAction):
    action: Literal["use"]
    item_id: str  # surroundings.inventory 의 id
    target_id: str | None = None


class EquipAction(_StrictAction):
    action: Literal["equip"]
    item_id: str  # surroundings.inventory 의 weapon/armor


class UnequipAction(_StrictAction):
    action: Literal["unequip"]
    item_id: str  # surroundings.equipment 안 어디에 박혀 있는 것


JudgeOutput = Annotated[
    PassAction
    | RejectAction
    | CombatAction
    | FleeAction
    | ClarifyAction
    | RollAction
    | RestAction
    | UseAction
    | EquipAction
    | UnequipAction
    | LevelUpAction
    | LearnSkillAction
    | BuyAction
    | SellAction,
    Field(discriminator="action"),
]

output_adapter: TypeAdapter[JudgeOutput] = TypeAdapter(JudgeOutput)
