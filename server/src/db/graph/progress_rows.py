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
    return GameProgress(game_id=row.game_id, **payload)
