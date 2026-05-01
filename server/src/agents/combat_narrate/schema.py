"""Schema for combat_narrate — fight-shaped trace.

The auto-combat sim runs the entire fight (or up to the round cap) in one
shot, accumulates per-round events, and hands the whole trace to this agent.
The agent streams a single 5-10 sentence Korean cinematic that walks the
reader through every round in order.

Numeric fields (hp, max_hp, damage) are deliberately absent from the LLM
input. The prompt forbids exposing numbers in the body, and blocking the
data at the schema layer is a hard constraint — the soft prompt rule alone
isn't enough. Engine-internal damage tracking happens in combat_auto.py
without going through these types.
"""
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class CombatRoundEvent(BaseModel):
    """One actor's action in a specific round."""

    model_config = ConfigDict(extra="forbid")

    round_no: int = Field(ge=1)
    actor: str  # Korean name
    target: str | None = None
    action: Literal["attack", "skill", "pass", "miss", "flee"]
    skill_name: str | None = None
    grade: Literal[
        "critical_success", "success", "partial_success", "failure", "critical_failure"
    ] | None = None
    killed: bool = False


class PlayerNarrateSnapshot(BaseModel):
    """Player snapshot for combat_narrate. Player identity travels in
    CombatNarrateInput.player_view, so this only carries the alive flag —
    enough for the cinematic's downed/defeat tone."""

    model_config = ConfigDict(extra="forbid")

    name: str
    alive: bool


class EnemyNarrateSnapshot(BaseModel):
    """Per-enemy snapshot for combat_narrate. Enemies have no side-channel
    for identity, so race / appearance / description / gender ride here.
    HP / max_hp are kept out — the prompt's grade-tone mapping covers
    intensity, and numerics never belong in the cinematic body."""

    model_config = ConfigDict(extra="forbid")

    name: str
    alive: bool
    race: dict[str, Any] | None = None
    appearance: str | None = None
    description: str | None = None
    gender: str | None = None


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
    player_view: dict[str, Any]
    player_intent: str  # the original player_input that drove this fight
    rounds_run: int = Field(ge=1)
    outcome: CombatOutcome
    player_start: PlayerNarrateSnapshot
    player_end: PlayerNarrateSnapshot
    enemies_start: list[EnemyNarrateSnapshot]
    enemies_end: list[EnemyNarrateSnapshot]
    events: list[CombatRoundEvent]
