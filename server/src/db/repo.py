"""Persistence repository Protocols."""

from typing import Protocol

from src.game.domain.graph import Graph
from src.game.domain.memory import ExchangePair, LogEntry, Memory, TurnLogEntry
from src.game.domain.progress import GameProgress
from src.game.domain.story_patch_ledger import StoryPatchLedgerEntry


class GraphRepo(Protocol):
    """Graph-native runtime persistence."""

    async def save_graph(self, game_id: str, graph: Graph) -> None: ...

    async def save_graph_changes(
        self,
        game_id: str,
        graph: Graph,
        *,
        changed_node_ids: list[str],
        changed_edge_ids: list[str],
        removed_edge_ids: list[str],
    ) -> None: ...

    async def load_graph(self, game_id: str) -> Graph: ...

    async def save_progress(self, progress: GameProgress) -> None: ...

    async def load_progress(self, game_id: str) -> GameProgress: ...

    async def append_log_entries(
        self, game_id: str, entries: list[LogEntry]
    ) -> None: ...

    async def append_history_entries(
        self, game_id: str, entries: list[TurnLogEntry]
    ) -> None: ...

    async def append_memory_entries(
        self, game_id: str, entries: list[Memory]
    ) -> None: ...

    async def append_exchange_entries(
        self, game_id: str, entries: list[ExchangePair]
    ) -> None: ...

    async def append_story_patch_entries(
        self, game_id: str, entries: list[StoryPatchLedgerEntry]
    ) -> None: ...

    async def load_log_entries(self, game_id: str) -> list[LogEntry]: ...

    async def load_history_entries(self, game_id: str) -> list[TurnLogEntry]: ...

    async def load_memory_entries(
        self, game_id: str, *, target: str | None = None
    ) -> list[Memory]: ...

    async def load_exchange_entries(self, game_id: str) -> list[ExchangePair]: ...

    async def load_story_patch_entries(
        self, game_id: str
    ) -> list[StoryPatchLedgerEntry]: ...


class ScenarioRepo(Protocol):
    """Read-only scenario seed access."""

    async def profile_exists(self, profile: str) -> bool: ...

    async def list_profiles(self) -> list[dict]: ...

    async def read_world_md(self, profile: str, *, missing_ok: bool = False) -> str: ...

    async def read_contract_json(
        self, profile: str, *, missing_ok: bool = False
    ) -> dict | None: ...

    async def read_start_json(self, profile: str) -> dict: ...

    async def read_player(self, profile: str) -> dict: ...

    async def load_seed_records(self, profile: str, kind: str) -> dict[str, dict]: ...
