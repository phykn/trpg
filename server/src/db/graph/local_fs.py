import asyncio
import json
from pathlib import Path

from pydantic import ValidationError

from src.db.graph import store
from src.db.graph.progress_rows import (
    GameProgressRow,
    progress_from_row,
    progress_to_row,
)
from src.db.graph.rows import (
    GraphEdgeRow,
    GraphNodeRow,
    graph_from_rows,
    graph_to_rows,
)
from src.game.domain.errors import PersistenceFailed
from src.game.domain.graph import Graph
from src.game.domain.memory import ExchangePair, LogEntry, TurnLogEntry
from src.game.domain.progress import GameProgress
from src.game.rules import RULES


class LocalFsGraphRepo:
    def __init__(self, saves_dir: str) -> None:
        self.saves_dir = saves_dir

    def _game_dir(self, game_id: str) -> Path:
        return Path(self.saves_dir) / "games" / game_id

    def _graph_dir(self, game_id: str) -> Path:
        return self._game_dir(game_id) / "graph"

    async def save_graph(self, game_id: str, graph: Graph) -> None:
        node_rows, edge_rows = graph_to_rows(game_id, graph)
        graph_dir = self._graph_dir(game_id)
        nodes_payload = json.dumps(
            [row.model_dump(mode="json") for row in node_rows],
            ensure_ascii=False,
        )
        edges_payload = json.dumps(
            [row.model_dump(mode="json") for row in edge_rows],
            ensure_ascii=False,
        )
        await asyncio.to_thread(
            store._atomic_write,
            graph_dir / "nodes.json",
            nodes_payload,
        )
        await asyncio.to_thread(
            store._atomic_write,
            graph_dir / "edges.json",
            edges_payload,
        )

    async def save_graph_changes(
        self,
        game_id: str,
        graph: Graph,
        *,
        changed_node_ids: list[str],
        changed_edge_ids: list[str],
        removed_edge_ids: list[str],
    ) -> None:
        del changed_node_ids, changed_edge_ids, removed_edge_ids
        await self.save_graph(game_id, graph)

    async def load_graph(self, game_id: str) -> Graph:
        graph_dir = self._graph_dir(game_id)
        nodes_path = graph_dir / "nodes.json"
        edges_path = graph_dir / "edges.json"
        if not nodes_path.exists() or not edges_path.exists():
            raise FileNotFoundError(game_id)
        try:
            node_rows = [
                GraphNodeRow.model_validate(row)
                for row in json.loads(nodes_path.read_text(encoding="utf-8"))
            ]
            edge_rows = [
                GraphEdgeRow.model_validate(row)
                for row in json.loads(edges_path.read_text(encoding="utf-8"))
            ]
            return graph_from_rows(node_rows, edge_rows)
        except (ValidationError, OSError, json.JSONDecodeError, ValueError) as e:
            raise PersistenceFailed(str(e)) from e

    async def save_progress(self, progress: GameProgress) -> None:
        path = self._game_dir(progress.game_id) / "progress.json"
        row = progress_to_row(progress)
        await asyncio.to_thread(store._atomic_write, path, row.model_dump_json())

    async def load_progress(self, game_id: str) -> GameProgress:
        path = self._game_dir(game_id) / "progress.json"
        if not path.exists():
            raise FileNotFoundError(game_id)
        try:
            row = GameProgressRow.model_validate_json(path.read_text(encoding="utf-8"))
            return progress_from_row(row)
        except (ValidationError, OSError, json.JSONDecodeError, ValueError) as e:
            raise PersistenceFailed(str(e)) from e

    async def append_log_entries(self, game_id: str, entries: list[LogEntry]) -> None:
        await store.append_log_entries(self.saves_dir, game_id, entries)

    async def append_history_entries(
        self, game_id: str, entries: list[TurnLogEntry]
    ) -> None:
        await store.append_history_entries(self.saves_dir, game_id, entries)

    async def append_exchange_entries(
        self, game_id: str, entries: list[ExchangePair]
    ) -> None:
        await store.append_exchange_entries(self.saves_dir, game_id, entries)

    async def load_log_entries(self, game_id: str) -> list[LogEntry]:
        return await asyncio.to_thread(
            store._load_jsonl_tail,
            store._log_path(self.saves_dir, game_id),
            RULES.log.display_turns,
            store._LOG_ADAPTER.validate_json,
        )

    async def load_history_entries(self, game_id: str) -> list[TurnLogEntry]:
        return await asyncio.to_thread(
            store._load_jsonl_tail,
            store._history_path(self.saves_dir, game_id),
            RULES.memory.turn_log_size,
            TurnLogEntry.model_validate_json,
        )

    async def load_exchange_entries(self, game_id: str) -> list[ExchangePair]:
        return await asyncio.to_thread(
            store._load_jsonl_tail,
            store._exchange_path(self.saves_dir, game_id),
            RULES.memory.recent_exchange_turns,
            ExchangePair.model_validate_json,
        )
