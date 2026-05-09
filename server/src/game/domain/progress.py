from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from src.game.domain.combat import GraphCombatState
from src.game.domain.memory import PendingCheck
from src.game.domain.state import CombatState


class GameProgress(BaseModel):
    model_config = ConfigDict(extra="forbid")

    game_id: str
    player_id: str
    locale: str = "ko"
    active_subject_id: str | None = None
    active_quest_id: str | None = None
    turn_count: int = 0
    pending_check: PendingCheck | None = None
    pending_confirmation: dict[str, Any] | None = None
    combat_state: CombatState | None = None
    graph_combat_state: GraphCombatState | None = None
    previous_phase_signal: str | None = None
    next_log_id: int = Field(default=1, ge=1)
