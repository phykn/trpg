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
    skill_id: str | None = None


class SummonCombatAction(_StrictAction):
    """Lazy-spawn an enemy matching `role` (Korean hint), then enter combat."""

    action: Literal["summon_combat"]
    role: str = Field(min_length=1, max_length=20)
    skill_id: str | None = None


class FleeAction(_StrictAction):
    action: Literal["flee"]


class MoveAction(_StrictAction):
    action: Literal["move"]
    destination: str
    tail_intent: str | None = None


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


class GiveAction(_StrictAction):
    """Free item transfer between two characters. Covers gift / lend / hand-over / corpse loot — bidirectional via from_id / to_id. Engine validates affinity (live NPC source) + carry capacity, auto-unequips if equipped."""

    action: Literal["give"]
    from_id: str
    to_id: str
    item_id: str
    tail_intent: str | None = None


class RollAction(_StrictAction):
    action: Literal["roll"]
    tier: Tier
    stat: StatKey
    targets: list[str] = Field(min_length=1)
    # Default absorbs LLM omits when validate_json bypasses the coerce hook (e.g. answer wrapped in markdown).
    reason: str = Field(default="행동 판정", min_length=1, max_length=80)


class RestAction(_StrictAction):
    action: Literal["rest"]


class UseAction(_StrictAction):
    action: Literal["use"]
    item_id: str
    target_id: str | None = None
    tail_intent: str | None = None


class EquipAction(_StrictAction):
    action: Literal["equip"]
    item_id: str
    tail_intent: str | None = None


class UnequipAction(_StrictAction):
    action: Literal["unequip"]
    item_id: str
    tail_intent: str | None = None


# Phase-changing actions (combat / rest / flee / roll / reject / summon_combat) can't compose sequentially.
ChainPart = Annotated[
    UseAction
    | EquipAction
    | UnequipAction
    | BuyAction
    | SellAction
    | GiveAction
    | MoveAction
    | LevelUpAction
    | LearnSkillAction
    | PassAction,
    Field(discriminator="action"),
]


class ChainAction(_StrictAction):
    """Sequential engine actions for compound input. Trailing `pass` part runs through narrate for flavor."""

    action: Literal["chain"]
    parts: list[ChainPart] = Field(min_length=2, max_length=4)


JudgeOutput = Annotated[
    PassAction
    | RejectAction
    | CombatAction
    | SummonCombatAction
    | FleeAction
    | MoveAction
    | RollAction
    | RestAction
    | UseAction
    | EquipAction
    | UnequipAction
    | LevelUpAction
    | LearnSkillAction
    | BuyAction
    | SellAction
    | GiveAction
    | ChainAction,
    Field(discriminator="action"),
]

output_adapter: TypeAdapter[JudgeOutput] = TypeAdapter(JudgeOutput)


_PHASE_CHANGING_ACTIONS = frozenset(
    {"combat", "roll", "rest", "flee", "reject", "summon_combat"}
)

_ROLL_REASON_FALLBACK = "행동 판정"


def coerce_judge_output(raw: dict) -> dict:
    """Last-mile fixes the prompt + retry loop can't eliminate: promote phase-changers out of chains, fill missing roll reason."""
    if not isinstance(raw, dict):
        return raw
    action = raw.get("action")

    if action == "chain":
        parts = raw.get("parts") or []
        for part in parts:
            if isinstance(part, dict) and part.get("action") in _PHASE_CHANGING_ACTIONS:
                return coerce_judge_output(part)

    if action == "roll" and not raw.get("reason"):
        raw = {**raw, "reason": _ROLL_REASON_FALLBACK}

    return raw


def validate_judge_output(answer: str) -> JudgeOutput:
    """Parse + coerce + validate. JSON parse failure defers to `validate_json` so Pydantic owns the error path."""
    try:
        raw = json.loads(answer)
    except json.JSONDecodeError:
        return output_adapter.validate_json(answer)
    if isinstance(raw, dict):
        raw = coerce_judge_output(raw)
    return output_adapter.validate_python(raw)
