"""Dispatch result types."""

from pydantic import BaseModel, ConfigDict, Field

from src.game.domain.combat import GraphCombatTraceEvent
from src.game.runtime.state import GameRuntimeState


class GraphActionDispatchError(ValueError):
    pass


class GraphActionDispatchResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    runtime: GameRuntimeState
    kind: str
    applied: int
    changed_node_ids: list[str]
    changed_edge_ids: list[str]
    removed_edge_ids: list[str]
    outcome: str | None = None
    combat_trace: list[GraphCombatTraceEvent] = Field(default_factory=list)
