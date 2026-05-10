from typing import Any

from src.game.domain.graph import (
    AddEdgeChange,
    Graph,
    GraphChange,
    GraphEdge,
    RemoveEdgeChange,
)
from src.game.domain.graph_query import edges_from, edges_to
from src.game.engines.graph_quest_common import (
    GraphQuestError,
    GraphQuestRewardResult,
    int_value,
    property_change,
    quest_status,
    require_quest,
)


def plan_quest_rewards(
    graph: Graph,
    quest_id: str,
    player_id: str,
) -> GraphQuestRewardResult:
    quest = require_quest(graph, quest_id)
    if quest_status(quest) != "completed":
        raise GraphQuestError(f"quest rewards require completed status: {quest_id}")
    player = graph.nodes.get(player_id)
    if player is None:
        raise GraphQuestError(f"missing player: {player_id}")
    if player.type != "character":
        raise GraphQuestError(f"node is not a character: {player_id}")

    rewards = quest.properties.get("rewards", {})
    reward_data = rewards if isinstance(rewards, dict) else {}
    gold = int_value(reward_data.get("gold"))
    exp = int_value(reward_data.get("exp"))
    item_ids = _reward_item_ids(graph, quest_id, reward_data)

    changes: list[GraphChange] = []
    if gold:
        changes.append(
            property_change(player_id, "gold", int_value(player.properties.get("gold")) + gold)
        )
    if exp:
        changes.append(
            property_change(player_id, "xp_pool", int_value(player.properties.get("xp_pool")) + exp)
        )
    for item_id in item_ids:
        for edge in edges_to(graph, quest_id, "reward_of"):
            if edge.from_node_id == item_id:
                changes.append(RemoveEdgeChange(type="remove_edge", edge_id=edge.id))
        if not _has_carry_edge(graph, player_id, item_id):
            changes.append(
                AddEdgeChange(
                    type="add_edge",
                    edge=GraphEdge(
                        id=f"carries:{player_id}:{item_id}",
                        type="carries",
                        from_node_id=player_id,
                        to_node_id=item_id,
                    ),
                )
            )
    return GraphQuestRewardResult(
        changes=changes,
        quest_id=quest_id,
        player_id=player_id,
        gold=gold,
        exp=exp,
        item_ids=item_ids,
    )


def _reward_item_ids(
    graph: Graph,
    quest_id: str,
    reward_data: dict[str, Any],
) -> list[str]:
    item_ids: list[str] = []
    raw_items = reward_data.get("items", [])
    if isinstance(raw_items, list):
        item_ids.extend(item for item in raw_items if isinstance(item, str))
    item_ids.extend(edge.from_node_id for edge in edges_to(graph, quest_id, "reward_of"))
    return sorted(set(item_ids))


def _has_carry_edge(graph: Graph, player_id: str, item_id: str) -> bool:
    return any(
        edge.to_node_id == item_id for edge in edges_from(graph, player_id, "carries")
    )
