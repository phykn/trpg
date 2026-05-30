from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict

from src.game.domain.content import RuntimeContent
from src.game.domain.graph import Graph
from src.game.domain.progress import GameProgress

SeedRecord = dict[str, Any]
SeedRecords = dict[str, SeedRecord]

STATIC_CONTENT_KEYS = frozenset(
    {
        "name",
        "title",
        "description",
        "background",
        "summary",
        "role",
        "gender",
        "memorable",
        "memories",
        "props",
    }
)


class SeedGraphBundle(BaseModel):
    model_config = ConfigDict(extra="forbid")

    graph: Graph
    progress: GameProgress
    content: RuntimeContent
