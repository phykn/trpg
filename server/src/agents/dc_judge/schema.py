import json
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


# Phase-changing actions are excluded from ChainPart because they trigger
# state transitions (combat phase, pending roll, rest sleep, flee resolution,
# reject halt, summon spawn) that don't compose with sequential dispatch.
_PHASE_CHANGING_ACTIONS = frozenset(
    {"combat", "roll", "rest", "flee", "reject", "summon_combat"}
)

# Generic Korean fallback for RollAction.reason when the LLM omits it.
# Keeps schema strict (min_length=1) while absorbing a recurring miss the
# 5-shot self-correction loop fails to fix.
_ROLL_REASON_FALLBACK = "행동 판정"


def coerce_judge_output(raw: dict) -> dict:
    """Last-mile fixes for two LLM patterns the prompt + retry loop cannot
    eliminate (observed across QA passes):

    1. `chain.parts` containing a phase-changing action. Promote the first
       such part to be the top-level action; remaining parts are dropped
       (the player's compound intent reduces to its phase-changing core,
       which is what they cared about).
    2. `roll` missing `reason`. Inject a generic Korean fallback so the
       strict `min_length=1` field still validates.

    Recursion handles nested fixes (e.g. a promoted roll part still needs
    its reason filled).
    """
    if not isinstance(raw, dict):
        return raw
    action = raw.get("action")

    if action == "chain":
        parts = raw.get("parts") or []
        for part in parts:
            if (
                isinstance(part, dict)
                and part.get("action") in _PHASE_CHANGING_ACTIONS
            ):
                return coerce_judge_output(part)

    if action == "roll" and not raw.get("reason"):
        raw = {**raw, "reason": _ROLL_REASON_FALLBACK}

    return raw


def validate_judge_output(answer: str) -> JudgeOutput:
    """Parse + coerce + validate. On JSON parse failure, defer to
    `validate_json` so Pydantic raises ValidationError canonically into the
    retry loop."""
    try:
        raw = json.loads(answer)
    except json.JSONDecodeError:
        return output_adapter.validate_json(answer)
    if isinstance(raw, dict):
        raw = coerce_judge_output(raw)
    return output_adapter.validate_python(raw)
