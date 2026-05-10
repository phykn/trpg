from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from src.game.domain.combat import GraphCombatState
from src.game.domain.content import RuntimeContent


class GameProgress(BaseModel):
    model_config = ConfigDict(extra="forbid")

    game_id: str
    player_id: str
    profile_id: str | None = None
    runtime_content: RuntimeContent = Field(default_factory=RuntimeContent)
    locale: str = "ko"
    active_subject_id: str | None = None
    active_quest_id: str | None = None
    turn_count: int = 0
    pending_confirmation: dict[str, Any] | None = None
    pending_roll: dict[str, Any] | None = None
    graph_combat_state: GraphCombatState | None = None
    next_log_id: int = Field(default=1, ge=1)
