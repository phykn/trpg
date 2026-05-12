import re
from typing import Literal

from pydantic import BaseModel, ConfigDict

from src.game.domain.content import RuntimeContent
from src.game.domain.graph import (
    AddEdgeChange,
    AddNodeChange,
    Graph,
    GraphChange,
    GraphEdge,
    GraphNode,
)
from src.game.domain.graph_query import (
    characters_at,
    edges_from,
    location_of,
    nodes_of_type,
)
from src.locale.render import render


class GraphQuestOfferPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    quest_id: str
    changes: list[GraphChange]
    content: RuntimeContent


def plan_missing_quest_offer(
    graph: Graph,
    player_id: str,
    locale: str = "ko",
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
        AddNodeChange(type="add_node", node=_giver(giver_id, locale)),
        AddNodeChange(type="add_node", node=_enemy(enemy_id, locale)),
        AddNodeChange(type="add_node", node=_reward(reward_id, locale)),
        AddNodeChange(
            type="add_node", node=_quest(quest_id, enemy_id, reward_id, locale)
        ),
        AddEdgeChange(type="add_edge", edge=_edge("located_at", giver_id, location_id)),
        AddEdgeChange(type="add_edge", edge=_edge("located_at", enemy_id, location_id)),
        AddEdgeChange(type="add_edge", edge=_edge("gives_quest", giver_id, quest_id)),
        AddEdgeChange(type="add_edge", edge=_edge("target_of", enemy_id, quest_id)),
        AddEdgeChange(type="add_edge", edge=_edge("reward_of", reward_id, quest_id)),
    ]
    return GraphQuestOfferPlan(
        quest_id=quest_id,
        changes=changes,
        content=_content(
            quest_id=quest_id,
            giver_id=giver_id,
            enemy_id=enemy_id,
            reward_id=reward_id,
            locale=locale,
        ),
    )


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


def _giver(giver_id: str, locale: str) -> GraphNode:
    del locale
    return GraphNode(
        id=giver_id,
        type="character",
        properties={
            **_source(giver_id),
            "alive": True,
            "stats": {"body": 0, "agility": 0, "mind": 1, "presence": 1},
            "status": [],
        },
    )


def _enemy(enemy_id: str, locale: str) -> GraphNode:
    del locale
    return GraphNode(
        id=enemy_id,
        type="character",
        properties={
            **_source(enemy_id),
            "alive": True,
            "stats": {"body": 2, "agility": 1, "mind": 0, "presence": 0},
            "status": [],
            "combat_behavior": {
                "attack_priority": "nearest",
            },
        },
    )


def _reward(reward_id: str, locale: str) -> GraphNode:
    del locale
    return GraphNode(
        id=reward_id,
        type="item",
        properties={
            **_source(reward_id),
            "consumable": False,
        },
    )


def _quest(quest_id: str, enemy_id: str, reward_id: str, locale: str) -> GraphNode:
    del locale
    return GraphNode(
        id=quest_id,
        type="quest",
        properties={
            **_source(quest_id),
            "difficulty": "normal",
            "status": "pending",
            "triggers": [
                {
                    "id": f"trigger_{quest_id}_defeat",
                    "type": "character_defeat",
                    "target_id": enemy_id,
                }
            ],
            "triggers_met": [False],
            "rewards": {"gold": 5, "exp": 10, "items": [reward_id]},
        },
    )


def _content(
    *,
    quest_id: str,
    giver_id: str,
    enemy_id: str,
    reward_id: str,
    locale: str,
) -> RuntimeContent:
    return RuntimeContent(
        characters={
            giver_id: {
                "id": giver_id,
                "name": render("runtime.seed.giver.name", locale),
            },
            enemy_id: {
                "id": enemy_id,
                "name": render("runtime.seed.enemy.name", locale),
            },
        },
        items={
            reward_id: {
                "id": reward_id,
                "name": render("runtime.seed.reward.name", locale),
                "description": render("runtime.seed.reward.description", locale),
            }
        },
        quests={
            quest_id: {
                "id": quest_id,
                "title": render("runtime.seed.quest.title", locale),
                "summary": render("runtime.seed.quest.summary", locale),
                "triggers": [
                    {
                        "id": f"trigger_{quest_id}_defeat",
                        "name": render("runtime.seed.quest.trigger", locale),
                    }
                ],
            }
        },
    )


def _source(node_id: str) -> dict[str, str]:
    return {"source": "runtime", "source_id": node_id}


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
