from functools import cached_property

from pydantic import BaseModel, ConfigDict, Field

from src.game.domain.content import RuntimeContent
from src.game.domain.graph import Graph
from src.game.domain.graph.query import GraphIndex
from src.game.domain.memory import ExchangePair, LogEntry, TurnLogEntry
from src.game.domain.progress import GameProgress


class GameRuntimeState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    graph: Graph
    progress: GameProgress
    content: RuntimeContent = Field(default_factory=RuntimeContent)
    log_entries: list[LogEntry] = Field(default_factory=list)
    turn_log: list[TurnLogEntry] = Field(default_factory=list)
    recent_exchanges: list[ExchangePair] = Field(default_factory=list)

    @cached_property
    def graph_index(self) -> GraphIndex:
        return GraphIndex(self.graph)
