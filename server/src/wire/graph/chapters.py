from src.game.runtime.state import GameRuntimeState
from src.wire.models import ChapterPayload

from .values import optional_str, static_value


def active_chapter_payload(runtime: GameRuntimeState) -> ChapterPayload | None:
    for chapter in runtime.graph_index.nodes.values():
        if chapter.type != "chapter":
            continue
        status = chapter.properties.get("status")
        if status != "active":
            continue
        return ChapterPayload(
            id=chapter.id,
            title=optional_str(static_value(chapter, "title", runtime.content))
            or chapter.id,
            summary=optional_str(static_value(chapter, "summary", runtime.content))
            or optional_str(static_value(chapter, "description", runtime.content))
            or "",
            status="active",
        )
    return None
