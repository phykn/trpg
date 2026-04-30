from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter

from ...domain.types import StatKey, Tier


class JudgeInput(BaseModel):
    player_input: str
    surroundings: dict[str, Any]


class _StrictAction(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PassAction(_StrictAction):
    action: Literal["pass"]
    targets: list[str] = []


class RejectAction(_StrictAction):
    action: Literal["reject"]


class CombatAction(_StrictAction):
    action: Literal["combat"]
    targets: list[str] = Field(min_length=1)
    skill_id: str | None = None  # semantic match against racial + learned (§2.6 S2)


class SummonCombatAction(_StrictAction):
    """Player references an enemy not in `entities` but contextually plausible
    for the location — flow lazy-spawns one matching the role then enters
    combat. `role` is the Korean hint to pin the summoned name."""

    action: Literal["summon_combat"]
    role: str = Field(min_length=1, max_length=20)
    skill_id: str | None = None


class FleeAction(_StrictAction):
    action: Literal["flee"]


class LevelUpAction(_StrictAction):
    action: Literal["level_up"]
    stat_up: StatKey
    stat_down: StatKey
    tail_intent: str | None = None


class LearnSkillAction(_StrictAction):
    action: Literal["learn_skill"]
    index: int = Field(ge=0)
    tail_intent: str | None = None


class BuyAction(_StrictAction):
    action: Literal["buy"]
    npc_id: str
    item_id: str
    tail_intent: str | None = None


class SellAction(_StrictAction):
    action: Literal["sell"]
    npc_id: str
    item_id: str
    tail_intent: str | None = None


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
    item_id: str  # id from surroundings.inventory
    target_id: str | None = None
    tail_intent: str | None = None


class EquipAction(_StrictAction):
    action: Literal["equip"]
    item_id: str  # weapon/armor in surroundings.inventory
    tail_intent: str | None = None


class UnequipAction(_StrictAction):
    action: Literal["unequip"]
    item_id: str  # whichever slot it currently occupies in surroundings.equipment
    tail_intent: str | None = None


# Sub-actions allowed inside a ChainAction. Combat / rest / flee / roll /
# reject / summon_combat are excluded — they trigger phase changes or
# pending state that doesn't compose with sequential dispatch.
ChainPart = Annotated[
    UseAction
    | EquipAction
    | UnequipAction
    | BuyAction
    | SellAction
    | LevelUpAction
    | LearnSkillAction
    | PassAction,
    Field(discriminator="action"),
]


class ChainAction(_StrictAction):
    """Sequential engine actions for compound input ("약초 먹고 검 든다").
    Each `parts[i]` runs in order; turn_count bumps and finalize fire once
    at the end. The last `pass` part (if any) runs through narrate so
    flavor descriptions ("한숨 돌린다") still get prose."""

    action: Literal["chain"]
    parts: list[ChainPart] = Field(min_length=2, max_length=4)


JudgeOutput = Annotated[
    PassAction
    | RejectAction
    | CombatAction
    | SummonCombatAction
    | FleeAction
    | RollAction
    | RestAction
    | UseAction
    | EquipAction
    | UnequipAction
    | LevelUpAction
    | LearnSkillAction
    | BuyAction
    | SellAction
    | ChainAction,
    Field(discriminator="action"),
]

output_adapter: TypeAdapter[JudgeOutput] = TypeAdapter(JudgeOutput)
