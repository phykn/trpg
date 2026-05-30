from dataclasses import dataclass
from typing import Any

from src.game.domain.action import Action
from src.game.domain.memory import NarrationCue, RollLogEntry

from ...request_result import GraphResultOutcome
from ...state import GameRuntimeState


class GraphRollError(ValueError):
    pass


class GraphRollExpected(GraphRollError):
    pass


class GraphRollActive(GraphRollError):
    pass


@dataclass
class ResolvedGraphRoll:
    runtime: GameRuntimeState
    action: Action
    pending: dict[str, Any]
    roll_entry: RollLogEntry
    grade: str
    outcome: GraphResultOutcome
    completed_quest_ids: list[str]
    affinity_cues: list[NarrationCue]
