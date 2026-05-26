from src.game.domain.graph import AddEdgeChange, AddNodeChange, Graph, GraphChange
from src.game.domain.graph.models import GraphEdge, GraphNode
from src.game.domain.story_patch import (
    AddCharacterPatch,
    AddCluePatch,
    AddItemPatch,
    AddQuestBeatPatch,
    AddLocationPatch,
    AddMemoryPatch,
    StoryPatch,
)


def story_patches_to_graph_changes(
    patches: list[StoryPatch],
    *,
    graph: Graph,
    player_id: str,
    turn_id: int,
) -> list[GraphChange]:
    changes: list[GraphChange] = []
    for patch in patches:
        if isinstance(patch, AddMemoryPatch):
            changes.extend(_memory_changes(patch, player_id=player_id, turn_id=turn_id))
        elif isinstance(patch, AddCluePatch):
            anchor_id = patch.anchor_id or _player_location_id(graph, player_id) or player_id
            changes.extend(
                _clue_changes(
                    patch,
                    anchor_id=anchor_id,
                    turn_id=turn_id,
                )
            )
        elif isinstance(patch, AddLocationPatch):
            changes.extend(_location_changes(patch, turn_id=turn_id))
        elif isinstance(patch, AddCharacterPatch):
            changes.extend(_character_changes(patch, turn_id=turn_id))
        elif isinstance(patch, AddItemPatch):
            changes.extend(_item_changes(patch, turn_id=turn_id))
        elif isinstance(patch, AddQuestBeatPatch):
            changes.append(_quest_beat_change(patch, turn_id=turn_id))
    return changes


def _memory_changes(
    patch: AddMemoryPatch,
    *,
    player_id: str,
    turn_id: int,
) -> list[GraphChange]:
    node = GraphNode(
        id=patch.id,
        type="knowledge",
        properties={
            "kind": "memory",
            "title": patch.summary,
            "summary": patch.summary,
            "stability": patch.stability,
            "visibility": patch.visibility,
            "turn_id": turn_id,
        },
    )
    return [
        AddNodeChange(type="add_node", node=node),
        AddEdgeChange(
            type="add_edge",
            edge=GraphEdge(
                id=f"has_knowledge:{player_id}:{patch.id}",
                type="has_knowledge",
                from_node_id=player_id,
                to_node_id=patch.id,
            ),
        ),
    ]


def _clue_changes(
    patch: AddCluePatch,
    *,
    anchor_id: str,
    turn_id: int,
) -> list[GraphChange]:
    node = GraphNode(
        id=patch.id,
        type="knowledge",
        properties={
            "kind": "clue",
            "title": patch.title,
            "summary": patch.summary,
            "stability": patch.stability,
            "visibility": patch.visibility,
            "turn_id": turn_id,
            "anchor_id": anchor_id,
        },
    )
    return [
        AddNodeChange(type="add_node", node=node),
        AddEdgeChange(
            type="add_edge",
            edge=GraphEdge(
                id=f"has_knowledge:{anchor_id}:{patch.id}",
                type="has_knowledge",
                from_node_id=anchor_id,
                to_node_id=patch.id,
            ),
        ),
    ]


def _location_changes(
    patch: AddLocationPatch,
    *,
    turn_id: int,
) -> list[GraphChange]:
    node = GraphNode(
        id=patch.id,
        type="location",
        properties={
            "name": patch.name,
            "description": patch.description,
            "stability": patch.stability,
            "turn_id": turn_id,
        },
    )
    return [
        AddNodeChange(type="add_node", node=node),
        AddEdgeChange(
            type="add_edge",
            edge=GraphEdge(
                id=f"connects_to:{patch.connect_from}:{patch.id}",
                type="connects_to",
                from_node_id=patch.connect_from,
                to_node_id=patch.id,
            ),
        ),
    ]


def _character_changes(
    patch: AddCharacterPatch,
    *,
    turn_id: int,
) -> list[GraphChange]:
    node = GraphNode(
        id=patch.id,
        type="character",
        properties={
            "name": patch.name,
            "role": patch.role,
            "alive": True,
            "stability": patch.stability,
            "turn_id": turn_id,
        },
    )
    return [
        AddNodeChange(type="add_node", node=node),
        AddEdgeChange(
            type="add_edge",
            edge=GraphEdge(
                id=f"located_at:{patch.id}:{patch.location_id}",
                type="located_at",
                from_node_id=patch.id,
                to_node_id=patch.location_id,
            ),
        ),
    ]


def _item_changes(
    patch: AddItemPatch,
    *,
    turn_id: int,
) -> list[GraphChange]:
    node = GraphNode(
        id=patch.id,
        type="item",
        properties={
            "name": patch.name,
            "description": patch.description,
            "stability": patch.stability,
            "turn_id": turn_id,
        },
    )
    if patch.owner_id is not None:
        edge = GraphEdge(
            id=f"carries:{patch.owner_id}:{patch.id}",
            type="carries",
            from_node_id=patch.owner_id,
            to_node_id=patch.id,
        )
    else:
        edge = GraphEdge(
            id=f"located_at:{patch.id}:{patch.location_id}",
            type="located_at",
            from_node_id=patch.id,
            to_node_id=patch.location_id or "",
        )
    return [
        AddNodeChange(type="add_node", node=node),
        AddEdgeChange(type="add_edge", edge=edge),
    ]


def _quest_beat_change(
    patch: AddQuestBeatPatch,
    *,
    turn_id: int,
) -> GraphChange:
    node = GraphNode(
        id=patch.id,
        type="quest",
        properties={
            "title": patch.title,
            "description": patch.summary,
            "status": "pending",
            "stability": patch.stability,
            "turn_id": turn_id,
        },
    )
    return AddNodeChange(type="add_node", node=node)


def _player_location_id(graph: Graph, player_id: str) -> str | None:
    for edge in graph.edges.values():
        if edge.type == "located_at" and edge.from_node_id == player_id:
            return edge.to_node_id
    return None
