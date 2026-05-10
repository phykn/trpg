from __future__ import annotations

import asyncio

from src.db.repo import GraphRepo
from src.game.domain.memory import LogEntry
from src.game.runtime.state import GameRuntimeState


def _resolve_next_log_id(next_log_id: int, log_entries: list[LogEntry]) -> int:
    if not log_entries:
        return next_log_id
    return max(next_log_id, max(entry.id for entry in log_entries) + 1)


async def load_runtime_state(repo: GraphRepo, game_id: str) -> GameRuntimeState:
    graph, progress, log_entries, turn_log, recent_dialogue = await asyncio.gather(
        repo.load_graph(game_id),
        repo.load_progress(game_id),
        repo.load_log_entries(game_id),
        repo.load_history_entries(game_id),
        repo.load_dialogue_entries(game_id),
    )
    progress = progress.model_copy(
        update={"next_log_id": _resolve_next_log_id(progress.next_log_id, log_entries)}
    )
    return GameRuntimeState(
        graph=graph,
        progress=progress,
        log_entries=log_entries,
        turn_log=turn_log,
        recent_dialogue=recent_dialogue,
    )
