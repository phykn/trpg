from typing import Literal

from pydantic import BaseModel, ConfigDict

from src.game.domain.action import Action
from src.game.domain.graph import (
    AddEdgeChange,
    Graph,
    GraphChange,
    GraphEdge,
    SetEdgePropertyChange,
    SetNodePropertyChange,
)
from src.game.domain.quest import quest_triggers, quest_triggers_met
from src.game.rules import RULES
from src.game.rules.dc import compute_required_roll


RollOutcome = Literal["success", "failure", "neutral"]


class GraphRollEffectResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    changes: list[GraphChange]


class GraphRollCheckResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    stat: str
    effective_dc: int
    required_roll: int


def plan_roll_check(
    graph: Graph | None,
    *,
    player_properties: dict[str, object],
    player_id: str | None,
    action: Action,
    base_dc: int,
) -> GraphRollCheckResult:
    stat = _roll_stat(action)
    stats = player_properties.get("stats")
    stat_value = stats.get(stat, 10) if isinstance(stats, dict) else 10
    effective_dc = _effective_roll_dc(base_dc, graph, player_id, action)
    return GraphRollCheckResult(
        stat=stat,
        effective_dc=effective_dc,
        required_roll=compute_required_roll(effective_dc, _int_value(stat_value, 10)),
    )


def plan_roll_graph_effects(
    graph: Graph,
    *,
    player_id: str,
    action: Action,
    grade: str,
    roll_outcome: RollOutcome,
) -> GraphRollEffectResult:
    return GraphRollEffectResult(
        changes=[
            *_plan_roll_relation_changes(
                graph,
                player_id=player_id,
                action=action,
                grade=grade,
                roll_outcome=roll_outcome,
            ),
            *_plan_roll_xp_changes(
                graph,
                player_id=player_id,
                action=action,
                grade=grade,
                roll_outcome=roll_outcome,
            ),
        ]
    )


def plan_roll_quest_trigger(
    graph: Graph,
    *,
    player_id: str,
    action: Action,
) -> tuple[str, str] | None:
    if action.verb == "speak":
        target = _roll_npc_target(graph, player_id, action)
        return ("social_check", target) if target is not None else None
    if action.verb == "transfer" and action.how not in {
        "accept",
        "abandon",
        "equip",
        "trade",
        "steal",
        "unequip",
    }:
        target = _roll_npc_target(graph, player_id, action)
        return ("social_check", target) if target is not None else None
    return None


def _roll_stat(action: Action) -> str:
    if action.verb == "perceive":
        return "mind"
    if action.verb == "speak":
        return "presence"
    if action.verb == "move":
        return "agility"
    if action.verb == "use":
        return "mind"
    if action.verb == "transfer":
        if action.how == "steal":
            return "agility"
        return "presence"
    return "body"


def _effective_roll_dc(
    base_dc: int,
    graph: Graph | None,
    player_id: str | None,
    action: Action,
) -> int:
    if graph is None or player_id is None:
        return base_dc
    target = _roll_npc_target(graph, player_id, action)
    if target is None:
        return base_dc
    affinity = _relation_affinity(graph, target, player_id)
    affinity_band = int(affinity / 10)
    return max(1, min(20, base_dc - affinity_band))


def _plan_roll_relation_changes(
    graph: Graph,
    *,
    player_id: str,
    action: Action,
    grade: str,
    roll_outcome: RollOutcome,
) -> list[GraphChange]:
    target = _roll_npc_target(graph, player_id, action)
    if target is None:
        return []
    delta = _roll_affinity_delta(action, grade, roll_outcome)
    if delta == 0:
        return []

    edge_id = _relation_edge_id(target, player_id)
    edge = graph.edges.get(edge_id)
    if edge is None:
        return [
            AddEdgeChange(
                type="add_edge",
                edge=GraphEdge(
                    id=edge_id,
                    type="relation",
                    from_node_id=target,
                    to_node_id=player_id,
                    properties={"affinity": delta},
                ),
            )
        ]

    affinity = edge.properties.get("affinity")
    current = affinity if isinstance(affinity, int) else 0
    return [
        SetEdgePropertyChange(
            type="set_edge_property",
            edge_id=edge_id,
            path="affinity",
            value=current + delta,
        )
    ]


def _plan_roll_xp_changes(
    graph: Graph,
    *,
    player_id: str,
    action: Action,
    grade: str,
    roll_outcome: RollOutcome,
) -> list[GraphChange]:
    if roll_outcome != "success":
        return []
    amount = RULES.growth.roll_xp.get(grade, 0)
    if amount <= 0:
        return []
    player = graph.nodes.get(player_id)
    if player is None:
        return []
    key = _roll_xp_award_key(action)
    existing = player.properties.get("xp_award_keys")
    keys = (
        [item for item in existing if isinstance(item, str)]
        if isinstance(existing, list)
        else []
    )
    if key in keys:
        return []

    current_xp = player.properties.get("xp_pool")
    xp_pool = current_xp if isinstance(current_xp, int) else 0
    return [
        SetNodePropertyChange(
            type="set_node_property",
            node_id=player_id,
            path="xp_pool",
            value=xp_pool + amount,
        ),
        SetNodePropertyChange(
            type="set_node_property",
            node_id=player_id,
            path="xp_award_keys",
            value=[*keys, key],
        ),
    ]


def _roll_affinity_delta(
    action: Action,
    grade: str,
    roll_outcome: RollOutcome,
) -> int:
    if roll_outcome == "failure":
        if grade == "critical_failure":
            return -RULES.social.affinity_critical
        return RULES.social.affinity_failure
    if not _is_positive_social_success(action):
        return 0
    if grade == "critical_success":
        return RULES.social.affinity_critical
    return RULES.social.affinity_success


def _roll_xp_award_key(action: Action) -> str:
    return f"roll:{action.verb}:{_action_target(action) or 'none'}"


def _is_positive_social_success(action: Action) -> bool:
    return action.verb == "speak" and action.how in {"friendly", "recruit"}


def _roll_npc_target(
    graph: Graph,
    player_id: str,
    action: Action,
) -> str | None:
    for candidate in _roll_target_candidates(action):
        node = graph.nodes.get(candidate)
        if node is not None and node.type == "character" and candidate != player_id:
            return candidate
    if action.verb == "speak":
        return _unique_active_social_check_target(graph, player_id)
    return None


def _roll_target_candidates(action: Action) -> list[str]:
    if action.verb == "speak":
        return _strings(action.to) + _strings(action.what)
    if action.verb == "transfer":
        return _strings(action.from_) + _strings(action.to) + _strings(action.what)
    return _strings(action.to) + _strings(action.what) + _strings(action.with_)


def _action_target(action: Action) -> str | None:
    for value in (action.what, action.to, action.from_, action.with_):
        strings = _strings(value)
        if strings:
            return strings[0]
    return None


def _unique_active_social_check_target(graph: Graph, player_id: str) -> str | None:
    player_location = _location_of(graph, player_id)
    if player_location is None:
        return None
    targets: set[str] = set()
    for node in graph.nodes.values():
        if node.type != "quest" or node.properties.get("status") != "active":
            continue
        triggers = quest_triggers(node)
        met = quest_triggers_met(node, len(triggers))
        for index, trigger in enumerate(triggers):
            if met[index] is True:
                continue
            if trigger.get("type") != "social_check":
                continue
            target = trigger.get("target")
            if not isinstance(target, str):
                continue
            target_node = graph.nodes.get(target)
            if target_node is None or target_node.type != "character":
                continue
            if _location_of(graph, target) != player_location:
                continue
            targets.add(target)
    if len(targets) != 1:
        return None
    return next(iter(targets))


def _location_of(graph: Graph, node_id: str) -> str | None:
    for edge in graph.edges.values():
        if edge.type == "located_at" and edge.from_node_id == node_id:
            return edge.to_node_id
    return None


def _relation_edge_id(npc_id: str, player_id: str) -> str:
    return f"relation:{npc_id}:{player_id}"


def _relation_affinity(graph: Graph, npc_id: str, player_id: str) -> int:
    edge = graph.edges.get(_relation_edge_id(npc_id, player_id))
    if edge is None:
        return 0
    affinity = edge.properties.get("affinity")
    return affinity if isinstance(affinity, int) else 0


def _int_value(value: object, default: int) -> int:
    return value if isinstance(value, int) else default


def _strings(value: object) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [item for item in value if isinstance(item, str)]
    return []
