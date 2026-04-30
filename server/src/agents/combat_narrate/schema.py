"""Schema for combat_narrate — fight-shaped trace.

The auto-combat sim runs the entire fight (or up to the round cap) in one
shot, accumulates per-round events, and hands the whole trace to this agent.
The agent streams a single 5-10 sentence Korean cinematic that walks the
reader through every round in order.
"""
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class CombatRoundEvent(BaseModel):
    """One actor's action in a specific round."""

    model_config = ConfigDict(extra="forbid")

    round_no: int = Field(ge=1)
    actor: str  # Korean name
    target: str | None = None
    action: Literal["attack", "skill", "pass", "miss", "flee"]
    skill_name: str | None = None
    damage: int = 0
    grade: Literal[
        "critical_success", "success", "partial_success", "failure", "critical_failure"
    ] | None = None
    killed: bool = False


class CombatStateSnapshot(BaseModel):
    """Per-actor HP snapshot — used for fight start and end."""

    model_config = ConfigDict(extra="forbid")

    name: str
    hp: int
    max_hp: int
    alive: bool


CombatOutcome = Literal[
    "victory",   # all enemies down or fled
    "defeat",    # player dead
    "downed",    # player hit 0 HP, death-save resolved this fight (auto)
    "fled",      # player flee succeeded (or hard-cap safety fallback)
]


class CombatNarrateInput(BaseModel):
    """Whole-fight narration input. The agent streams 5-10 Korean sentences
    that cover every round in order."""

    world: str
    location: dict
    player_intent: str  # the original player_input that drove this fight
    rounds_run: int = Field(ge=1)
    outcome: CombatOutcome
    player_start: CombatStateSnapshot
    player_end: CombatStateSnapshot
    enemies_start: list[CombatStateSnapshot]
    enemies_end: list[CombatStateSnapshot]
    events: list[CombatRoundEvent]
