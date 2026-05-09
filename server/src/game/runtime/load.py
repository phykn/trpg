from __future__ import annotations

import asyncio

from src.db._schema import _resolve_next_log_id
from src.db.repo import GraphRepo
from src.game.runtime.state import GameRuntimeState


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
