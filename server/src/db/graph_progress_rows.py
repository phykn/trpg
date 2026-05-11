from copy import deepcopy
from typing import Any

from pydantic import BaseModel, ConfigDict

from src.game.domain.progress import GameProgress


class GameProgressRow(BaseModel):
    model_config = ConfigDict(extra="forbid")

    game_id: str
    progress: dict[str, Any]


def progress_to_row(progress: GameProgress) -> GameProgressRow:
    payload = progress.model_dump(mode="json", exclude={"game_id"})
    return GameProgressRow(game_id=progress.game_id, progress=payload)


def progress_from_row(row: GameProgressRow) -> GameProgress:
    payload = deepcopy(row.progress)
    _backfill_graph_combat_state(payload)
    return GameProgress(game_id=row.game_id, **payload)


def _backfill_graph_combat_state(payload: dict[str, Any]) -> None:
    state = payload.get("graph_combat_state")
    if not isinstance(state, dict):
        return

    enemy_ids = state.get("enemy_ids")
    if "active_enemy_id" not in state and isinstance(enemy_ids, list) and enemy_ids:
        first_enemy = enemy_ids[0]
        if isinstance(first_enemy, str):
            state["active_enemy_id"] = first_enemy
    state.setdefault("player_hearts", 3)
    state.setdefault("enemy_hearts", 3)
