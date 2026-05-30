from __future__ import annotations

from src.game.domain.graph import GraphEdge

from .coerce import optional_str, record_id, str_list
from .properties import record_properties
from .types import SeedRecord, SeedRecords


def add_effect_edge(
    add_edge,
    record: SeedRecord,
    source_type: str,
    effects: SeedRecords,
) -> None:
    effect_id = optional_str(record.get("effect"))
    if effect_id is None or effect_id not in effects:
        return
    source_id = record_id(record)
    add_edge(
        "uses_effect",
        source_id,
        effect_id,
        {"source_type": source_type},
    )


def add_slot_edge(
    add_edge,
    item: SeedRecord,
    slots: SeedRecords,
) -> None:
    slot_id = optional_str(item.get("slot"))
    if slot_id is None or slot_id not in slots:
        return
    add_edge("uses_slot", record_id(item), slot_id)


def add_action_edge(
    add_edge,
    skill: SeedRecord,
    actions: SeedRecords,
) -> None:
    action = optional_str(skill.get("action"))
    if action is None or action not in actions:
        return
    add_edge("uses_action", record_id(skill), action)


def add_knowledge_edges(
    add_edge,
    record: SeedRecord,
    knowledge: SeedRecords,
) -> None:
    source_id = record_id(record)
    for knowledge_id in str_list(record.get("knowledge")):
        if knowledge_id not in knowledge:
            continue
        add_edge("has_knowledge", source_id, knowledge_id)


def add_quest_target_edge(
    edges: dict[str, GraphEdge],
    trigger: SeedRecord,
    quest_id: str,
    outcome: str,
) -> None:
    target = optional_str(trigger.get("target"))
    trigger_id = optional_str(trigger.get("id"))
    if target is None or trigger_id is None:
        return
    prefix = "target_of" if outcome == "success" else "target_of:fail"
    edge_id = f"{prefix}:{trigger_id}:{target}:{quest_id}"
    edges[edge_id] = GraphEdge(
        id=edge_id,
        type="target_of",
        from_node_id=target,
        to_node_id=quest_id,
        properties=record_properties(trigger, exclude={"target"}) | {"outcome": outcome},
    )
