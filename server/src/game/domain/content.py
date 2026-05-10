from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from src.game.domain.graph import GraphNode


SeedRecord = dict[str, Any]
SeedRecords = dict[str, SeedRecord]

_NODE_COLLECTIONS = {
    "character": "characters",
    "item": "items",
    "location": "locations",
    "quest": "quests",
    "skill": "skills",
    "race": "races",
    "chapter": "chapters",
}


class RuntimeContent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    races: SeedRecords = Field(default_factory=dict)
    locations: SeedRecords = Field(default_factory=dict)
    items: SeedRecords = Field(default_factory=dict)
    skills: SeedRecords = Field(default_factory=dict)
    characters: SeedRecords = Field(default_factory=dict)
    quests: SeedRecords = Field(default_factory=dict)
    chapters: SeedRecords = Field(default_factory=dict)


def runtime_content_from_records(
    *,
    races: SeedRecords,
    locations: SeedRecords,
    items: SeedRecords,
    skills: SeedRecords,
    characters: SeedRecords,
    quests: SeedRecords,
    chapters: SeedRecords,
) -> RuntimeContent:
    return RuntimeContent(
        races=races,
        locations=locations,
        items=items,
        skills=skills,
        characters=characters,
        quests=quests,
        chapters=chapters,
    )


def merge_content(base: RuntimeContent, overlay: RuntimeContent) -> RuntimeContent:
    return RuntimeContent(
        races={**base.races, **overlay.races},
        locations={**base.locations, **overlay.locations},
        items={**base.items, **overlay.items},
        skills={**base.skills, **overlay.skills},
        characters={**base.characters, **overlay.characters},
        quests={**base.quests, **overlay.quests},
        chapters={**base.chapters, **overlay.chapters},
    )


def node_record(content: RuntimeContent, node: GraphNode) -> SeedRecord:
    collection_name = _NODE_COLLECTIONS.get(node.type)
    if collection_name is None:
        return {}
    collection = getattr(content, collection_name)
    source_id = _source_id(node)
    record = collection.get(source_id)
    return record if isinstance(record, dict) else {}


def node_value(content: RuntimeContent, node: GraphNode, key: str) -> Any:
    value = node.properties.get(key)
    if value is not None:
        return value
    return node_record(content, node).get(key)


def node_label(content: RuntimeContent, node: GraphNode) -> str:
    for key in ("name", "title"):
        value = node_value(content, node, key)
        if isinstance(value, str) and value:
            return value
    return node.id


def node_text(content: RuntimeContent, node: GraphNode, key: str) -> str | None:
    value = node_value(content, node, key)
    return value if isinstance(value, str) and value else None


def _source_id(node: GraphNode) -> str:
    value = node.properties.get("source_id")
    return value if isinstance(value, str) and value else node.id
