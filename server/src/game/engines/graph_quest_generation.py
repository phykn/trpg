from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict

from src.game.domain.graph import (
    AddEdgeChange,
    AddNodeChange,
    Graph,
    GraphChange,
    GraphEdge,
    GraphNode,
)
from src.game.domain.graph_query import characters_at, edges_from, location_of, nodes_of_type


class GraphQuestOfferPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    quest_id: str
    changes: list[GraphChange]


def plan_missing_quest_offer(
    graph: Graph,
    player_id: str,
) -> GraphQuestOfferPlan | None:
    location_id = location_of(graph, player_id)
    if location_id is None or _has_open_work(graph, location_id):
        return None

    index = _next_auto_index(graph)
    quest_id = f"auto_quest_{index:03d}"
    giver_id = f"auto_giver_{index:03d}"
    enemy_id = f"auto_enemy_{index:03d}"
    reward_id = f"auto_reward_{index:03d}"
    changes: list[GraphChange] = [
        AddNodeChange(type="add_node", node=_giver(giver_id)),
        AddNodeChange(type="add_node", node=_enemy(enemy_id)),
        AddNodeChange(type="add_node", node=_reward(reward_id)),
        AddNodeChange(type="add_node", node=_quest(quest_id, enemy_id, reward_id)),
        AddEdgeChange(type="add_edge", edge=_edge("located_at", giver_id, location_id)),
        AddEdgeChange(type="add_edge", edge=_edge("located_at", enemy_id, location_id)),
        AddEdgeChange(type="add_edge", edge=_edge("gives_quest", giver_id, quest_id)),
        AddEdgeChange(type="add_edge", edge=_edge("target_of", enemy_id, quest_id)),
        AddEdgeChange(type="add_edge", edge=_edge("reward_of", reward_id, quest_id)),
    ]
    return GraphQuestOfferPlan(quest_id=quest_id, changes=changes)


def _has_open_work(graph: Graph, location_id: str) -> bool:
    for quest in nodes_of_type(graph, "quest"):
        if _quest_status(quest) == "active":
            return True

    visible_sources = {*characters_at(graph, location_id), location_id}
    for source_id in visible_sources:
        for edge in edges_from(graph, source_id, "gives_quest"):
            quest = graph.nodes.get(edge.to_node_id)
            if quest is not None and _quest_status(quest) in {"locked", "pending"}:
                return True
    return False


def _quest_status(quest: GraphNode) -> str:
    status = quest.properties.get("status")
    return status if isinstance(status, str) else "locked"


def _next_auto_index(graph: Graph) -> int:
    highest = 0
    for node_id in graph.nodes:
        match = re.fullmatch(r"auto_(?:quest|giver|enemy|reward)_(\d+)", node_id)
        if match is not None:
            highest = max(highest, int(match.group(1)))
    return highest + 1


def _giver(giver_id: str) -> GraphNode:
    return GraphNode(
        id=giver_id,
        type="character",
        properties={
            "name": "마을 주민",
            "hp": 10,
            "max_hp": 10,
            "mp": 0,
            "max_mp": 0,
            "alive": True,
            "stats": {"body": 0, "agility": 0, "mind": 1, "presence": 1},
            "status": [],
        },
    )


def _enemy(enemy_id: str) -> GraphNode:
    return GraphNode(
        id=enemy_id,
        type="character",
        properties={
            "name": "떠돌이 적",
            "hp": 28,
            "max_hp": 28,
            "mp": 0,
            "max_mp": 0,
            "alive": True,
            "stats": {"body": 2, "agility": 1, "mind": 0, "presence": 0},
            "status": [],
        },
    )


def _reward(reward_id: str) -> GraphNode:
    return GraphNode(
        id=reward_id,
        type="item",
        properties={
            "name": "작은 보상",
            "description": "의뢰를 마치면 받을 수 있는 보상입니다.",
            "consumable": False,
        },
    )


def _quest(quest_id: str, enemy_id: str, reward_id: str) -> GraphNode:
    return GraphNode(
        id=quest_id,
        type="quest",
        properties={
            "title": "마을의 부탁",
            "summary": "마을 주민은 주변을 위협하는 적을 처리해 달라고 부탁합니다.",
            "difficulty": "normal",
            "status": "pending",
            "triggers": [
                {
                    "id": f"trigger_{quest_id}_defeat",
                    "name": "떠돌이 적 물리치기",
                    "type": "character_defeat",
                    "target_id": enemy_id,
                }
            ],
            "triggers_met": [False],
            "rewards": {"gold": 5, "exp": 10, "items": [reward_id]},
        },
    )


def _edge(
    edge_type: Literal["located_at", "gives_quest", "target_of", "reward_of"],
    from_node_id: str,
    to_node_id: str,
) -> GraphEdge:
    return GraphEdge(
        id=f"{edge_type}:{from_node_id}:{to_node_id}",
        type=edge_type,
        from_node_id=from_node_id,
        to_node_id=to_node_id,
    )
