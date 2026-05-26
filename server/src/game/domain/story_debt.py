from pydantic import BaseModel, ConfigDict, Field

from src.game.domain.graph import Graph


class StoryDebtEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    title: str
    turn: int | None = None
    reason: str = Field(min_length=1)


class StoryDebtReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    unresolved_clues: list[StoryDebtEntry] = Field(default_factory=list)
    orphan_characters: list[StoryDebtEntry] = Field(default_factory=list)
    orphan_items: list[StoryDebtEntry] = Field(default_factory=list)
    dangling_quest_beats: list[StoryDebtEntry] = Field(default_factory=list)


def build_story_debt_report(graph: Graph) -> StoryDebtReport:
    located_or_hidden = {
        edge.from_node_id
        for edge in graph.edges.values()
        if edge.type in {"located_at", "hidden_at"}
    }
    carried = {
        edge.to_node_id for edge in graph.edges.values() if edge.type == "carries"
    }

    unresolved_clues: list[StoryDebtEntry] = []
    orphan_characters: list[StoryDebtEntry] = []
    orphan_items: list[StoryDebtEntry] = []
    dangling_quest_beats: list[StoryDebtEntry] = []

    for node in graph.nodes.values():
        props = node.properties
        if node.type == "knowledge" and props.get("kind") == "clue":
            if not _is_resolved(props):
                unresolved_clues.append(
                    _entry(node.id, props, "generated clue is not marked resolved")
                )
        elif node.type == "character" and _is_generated(props):
            if props.get("is_player") is not True and node.id not in located_or_hidden:
                orphan_characters.append(
                    _entry(node.id, props, "generated character has no location")
                )
        elif node.type == "item" and _is_generated(props):
            if node.id not in located_or_hidden and node.id not in carried:
                orphan_items.append(
                    _entry(node.id, props, "generated item has no location or owner")
                )
        elif node.type == "quest" and _is_generated(props):
            if props.get("status") in {"pending", "active"}:
                dangling_quest_beats.append(
                    _entry(node.id, props, "generated quest beat is still open")
                )

    return StoryDebtReport(
        unresolved_clues=sorted(unresolved_clues, key=_sort_key),
        orphan_characters=sorted(orphan_characters, key=_sort_key),
        orphan_items=sorted(orphan_items, key=_sort_key),
        dangling_quest_beats=sorted(dangling_quest_beats, key=_sort_key),
    )


def _is_generated(props: dict[str, object]) -> bool:
    return props.get("stability") in {"scene", "chapter", "campaign"}


def _is_resolved(props: dict[str, object]) -> bool:
    return props.get("resolved") is True or props.get("status") in {
        "resolved",
        "completed",
    }


def _entry(node_id: str, props: dict[str, object], reason: str) -> StoryDebtEntry:
    title = props.get("title") or props.get("name") or props.get("description") or node_id
    turn = props.get("turn_id")
    return StoryDebtEntry(
        id=node_id,
        title=title if isinstance(title, str) else node_id,
        turn=turn if isinstance(turn, int) else None,
        reason=reason,
    )


def _sort_key(entry: StoryDebtEntry) -> tuple[int, str]:
    return (entry.turn if entry.turn is not None else -1, entry.id)
