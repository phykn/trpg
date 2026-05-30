import asyncio
import json

from pydantic import BaseModel, TypeAdapter, ValidationError

from src.db._supabase_http import _PostgREST
from src.db.graph.progress_rows import (
    GameProgressRow,
    progress_from_row,
    progress_to_row,
)
from src.db.graph.rows import (
    GraphEdgeRow,
    GraphNodeRow,
    graph_edge_rows,
    graph_from_rows,
    graph_node_rows,
    graph_to_rows,
)
from src.game.domain.errors import PersistenceFailed
from src.game.domain.graph import Graph
from src.game.domain.memory import ExchangePair, LogEntry, Memory, TurnLogEntry
from src.game.domain.progress import GameProgress
from src.game.domain.story_patch_ledger import StoryPatchLedgerEntry
from src.game.rules import RULES


_LOG_ADAPTER: TypeAdapter[LogEntry] = TypeAdapter(LogEntry)


class SupabaseGraphRepo:
    def __init__(self, *, url: str, service_key: str) -> None:
        self._db = _PostgREST(url, service_key)

    async def save_graph(self, game_id: str, graph: Graph) -> None:
        node_rows, edge_rows = graph_to_rows(game_id, graph)
        await self._db.upsert(
            "graph_nodes",
            [row.model_dump(mode="json") for row in node_rows],
            on_conflict="game_id,node_id",
        )
        await self._db.upsert(
            "graph_edges",
            [row.model_dump(mode="json") for row in edge_rows],
            on_conflict="game_id,edge_id",
        )
        await self._delete_stale_rows(
            "graph_edges",
            "edge_id",
            game_id,
            [row.edge_id for row in edge_rows],
        )
        await self._delete_stale_rows(
            "graph_nodes",
            "node_id",
            game_id,
            [row.node_id for row in node_rows],
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
        node_rows = graph_node_rows(game_id, graph, changed_node_ids)
        edge_rows = graph_edge_rows(game_id, graph, changed_edge_ids)
        await self._db.upsert(
            "graph_nodes",
            [row.model_dump(mode="json") for row in node_rows],
            on_conflict="game_id,node_id",
        )
        await self._db.upsert(
            "graph_edges",
            [row.model_dump(mode="json") for row in edge_rows],
            on_conflict="game_id,edge_id",
        )
        await self._delete_rows_by_ids(
            "graph_edges",
            "edge_id",
            game_id,
            removed_edge_ids,
        )

    async def _delete_stale_rows(
        self,
        table: str,
        id_column: str,
        game_id: str,
        live_ids: list[str],
    ) -> None:
        filters = {"game_id": f"eq.{game_id}"}
        if live_ids:
            filters[id_column] = f"not.in.({','.join(live_ids)})"
        await self._db.delete(table, filters=filters)

    async def _delete_rows_by_ids(
        self,
        table: str,
        id_column: str,
        game_id: str,
        ids: list[str],
    ) -> None:
        if not ids:
            return
        await self._db.delete(
            table,
            filters={"game_id": f"eq.{game_id}", id_column: f"in.({','.join(ids)})"},
        )

    async def load_graph(self, game_id: str) -> Graph:
        try:
            node_data, edge_data = await asyncio.gather(
                self._db.select(
                    "graph_nodes",
                    filters={"game_id": f"eq.{game_id}"},
                    select="game_id,node_id,node_type,properties",
                ),
                self._db.select(
                    "graph_edges",
                    filters={"game_id": f"eq.{game_id}"},
                    select="game_id,edge_id,edge_type,from_node_id,to_node_id,properties",
                ),
            )
            if not node_data:
                raise FileNotFoundError(game_id)
            node_rows = [GraphNodeRow.model_validate(row) for row in node_data]
            edge_rows = [GraphEdgeRow.model_validate(row) for row in edge_data]
            return graph_from_rows(node_rows, edge_rows)
        except ValidationError as e:
            raise PersistenceFailed(str(e)) from e

    async def save_progress(self, progress: GameProgress) -> None:
        row = progress_to_row(progress)
        await self._db.upsert(
            "game_progress",
            [row.model_dump(mode="json")],
            on_conflict="game_id",
        )

    async def load_progress(self, game_id: str) -> GameProgress:
        row = await self._db.select_one(
            "game_progress",
            filters={"game_id": f"eq.{game_id}"},
            select="game_id,progress",
        )
        if row is None:
            raise FileNotFoundError(game_id)
        try:
            return progress_from_row(GameProgressRow.model_validate(row))
        except ValidationError as e:
            raise PersistenceFailed(str(e)) from e

    async def append_log_entries(self, game_id: str, entries: list[LogEntry]) -> None:
        if not entries:
            return
        rows = [
            {
                "game_id": game_id,
                "log_id": entry.id,
                "entry": json.loads(entry.model_dump_json()),
            }
            for entry in entries
        ]
        await self._db.insert("log_entries", rows)

    async def _append_seq_rows(
        self, table: str, game_id: str, entries: list[BaseModel]
    ) -> None:
        if not entries:
            return
        rows = [
            {"game_id": game_id, "entry": json.loads(entry.model_dump_json())}
            for entry in entries
        ]
        await self._db.insert(table, rows)

    async def append_history_entries(
        self, game_id: str, entries: list[TurnLogEntry]
    ) -> None:
        await self._append_seq_rows("history_entries", game_id, list(entries))

    async def append_memory_entries(
        self, game_id: str, entries: list[Memory]
    ) -> None:
        if not entries:
            return
        rows = [
            {
                "game_id": game_id,
                "target_id": entry.target,
                "turn": entry.turn,
                "importance": entry.importance,
                "entry": json.loads(entry.model_dump_json()),
            }
            for entry in entries
        ]
        await self._db.insert("memory_entries", rows)

    async def append_exchange_entries(
        self, game_id: str, entries: list[ExchangePair]
    ) -> None:
        await self._append_seq_rows("exchange_entries", game_id, list(entries))

    async def append_story_patch_entries(
        self, game_id: str, entries: list[StoryPatchLedgerEntry]
    ) -> None:
        await self._append_seq_rows("world_patch_entries", game_id, list(entries))

    async def load_log_entries(self, game_id: str) -> list[LogEntry]:
        rows = await self._db.select(
            "log_entries",
            filters={"game_id": f"eq.{game_id}"},
            select="entry",
            order="log_id.desc",
            limit=RULES.log.display_turns,
        )
        return [_LOG_ADAPTER.validate_python(row["entry"]) for row in reversed(rows)]

    async def load_history_entries(self, game_id: str) -> list[TurnLogEntry]:
        rows = await self._db.select(
            "history_entries",
            filters={"game_id": f"eq.{game_id}"},
            select="entry",
            order="seq.desc",
            limit=RULES.memory.turn_log_size,
        )
        return [TurnLogEntry.model_validate(row["entry"]) for row in reversed(rows)]

    async def load_memory_entries(
        self, game_id: str, *, target: str | None = None
    ) -> list[Memory]:
        filters = {"game_id": f"eq.{game_id}"}
        if target is not None:
            filters["target_id"] = f"eq.{target}"
        rows = await self._db.select(
            "memory_entries",
            filters=filters,
            select="entry,target_id,turn,importance",
            order="seq.desc",
            limit=RULES.memory.cap,
        )
        return [Memory.model_validate(row["entry"]) for row in reversed(rows)]

    async def load_exchange_entries(self, game_id: str) -> list[ExchangePair]:
        rows = await self._db.select(
            "exchange_entries",
            filters={"game_id": f"eq.{game_id}"},
            select="entry",
            order="seq.desc",
            limit=RULES.memory.recent_exchange_turns,
        )
        return [ExchangePair.model_validate(row["entry"]) for row in reversed(rows)]

    async def load_story_patch_entries(
        self, game_id: str
    ) -> list[StoryPatchLedgerEntry]:
        rows = await self._db.select(
            "world_patch_entries",
            filters={"game_id": f"eq.{game_id}"},
            select="entry",
            order="seq.desc",
        )
        return [
            StoryPatchLedgerEntry.model_validate(row["entry"])
            for row in reversed(rows)
        ]
