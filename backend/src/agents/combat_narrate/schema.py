"""Schema for combat_narrate — one round's structured trace fed to the LLM
to produce a 1-2 sentence cinematic blurb."""
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class CombatRoundEvent(BaseModel):
    """One actor's action this round (attack / skill / miss / pass / kill)."""

    model_config = ConfigDict(extra="forbid")

    actor: str  # Korean name
    target: str | None = None
    action: Literal["attack", "skill", "pass", "miss"]
    skill_name: str | None = None
    damage: int = 0
    grade: Literal[
        "critical_success", "success", "partial_success", "failure", "critical_failure"
    ] | None = None
    killed: bool = False


class CombatStateSnapshot(BaseModel):
    """Per-actor HP snapshot at the start of this round."""

    model_config = ConfigDict(extra="forbid")

    name: str
    hp: int
    max_hp: int
    alive: bool


class CombatNarrateInput(BaseModel):
    """Per-round narration input. The agent streams 1-2 Korean sentences."""

    world: str
    location: dict
    player_intent: str  # the original player_input that started this fight
    round_no: int
    is_first_round: bool
    is_final_round: bool  # combat ends this round (all enemies dead or player down)
    player: CombatStateSnapshot
    enemies: list[CombatStateSnapshot]
    events: list[CombatRoundEvent]
    history_summary: str = Field(default="", max_length=400)
